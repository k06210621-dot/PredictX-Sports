#!/usr/bin/env python3
"""
PredictX Sports 每日排程分析腳本
- 由 Railway Cron 或外部排程器呼叫
- 分析今日 + 明日賽事
- 執行結算（settlement）
- 支援 DATABASE_URL 環境變數（Railway 自動注入）
"""

import os
import sys
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta

# 確保 analysis/ 目錄在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from analysis_engine import AnalysisEngine
from settlement_engine import SettlementEngine


def get_db_connection():
    """優先使用 Railway 注入的 DATABASE_URL，fallback 到本地參數"""
    database_url = os.getenv('DATABASE_URL')
    if database_url:
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        return psycopg2.connect(database_url, cursor_factory=RealDictCursor)

    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        port=os.getenv('DB_PORT', 5432),
        dbname=os.getenv('DB_NAME', 'sports_db'),
        user=os.getenv('DB_USER', 'jero'),
        password=os.getenv('DB_PASSWORD', ''),
        cursor_factory=RealDictCursor
    )


def get_pending_games(conn, target_dates: list):
    """取得指定日期範圍內尚未分析（或分析過期 / 投手資料更新）的 scheduled 賽事

    觸發重跑的條件（任一）：
    1. 還沒分析過
    2. 分析過期超過 12 小時
    3. 主客場任一邊的先發投手從 NULL/「尚未公布」變成有值（投手補抓成功）
    """
    cur = conn.cursor(cursor_factory=RealDictCursor)
    placeholders = ','.join(['%s'] * len(target_dates))
    query = f"""
        SELECT g.game_id::text
        FROM predictx.games g
        LEFT JOIN predictx.game_analysis ga ON g.game_id = ga.game_id
        WHERE g.status ILIKE 'scheduled'
          AND g.match_date::date IN ({placeholders})
          -- 🆕 [2026-07-19] 防護：排除已開打/已結束的賽事，避免 settlement 更新
          -- updated_at 後因 12hr 逾時條件意外重新觸發 AI 分析
          AND g.status NOT ILIKE 'FINAL'
          AND g.status NOT ILIKE 'LIVE'
          AND g.status NOT ILIKE 'IN_PROGRESS'
          AND (
            ga.analysis_id IS NULL
            OR ga.updated_at < NOW() - INTERVAL '12 hours'
            -- 重抓投手：若 game.pitcher_updated_at > ga.last_analyzed_pitcher_update（且現在投手有值）
            OR (
              g.pitcher_updated_at IS NOT NULL
              AND (ga.last_analyzed_pitcher_update IS NULL
                   OR g.pitcher_updated_at > ga.last_analyzed_pitcher_update)
              AND (g.home_pitcher_name IS NOT NULL OR g.away_pitcher_name IS NOT NULL)
            )
          )
        ORDER BY g.match_date
    """
    cur.execute(query, target_dates)
    games = cur.fetchall()
    cur.close()
    return games


def save_analysis(conn, game_id, analysis_result):
    """寫入或更新 analysis_data，並同步寫入 ai_prediction_history 回流快照"""
    if not analysis_result:
        return False
    cur = conn.cursor()
    try:
        # 🆕 [2026-06-24] 同步寫入回流歷史（App 端透過 UPSERT + prompt_version 防重）
        # 注意：這裡如果是 re-analysis 觸發，會寫入新版本快照；前一版本快照仍保留
        try:
            # 🆕 [2026-06-24 v3] Anti-Bias 修正版（已驗證有效，永久採用）
            # 改動：Step 4 從機械式加法改為綜合判斷、加反偏差自檢
            # 驗證結果（30 場 MLB 6/23+6/24）：
            #   v2 主隊勝率 77.4% → v3 46.7%（更貼近歷史 53-54%）
            #   v2 平均主隊勝率 0.562 → v3 0.487
            prompt_ver = 'v3-cot-anti-bias-2026-06-24'
            home_prob = analysis_result.get('home_win_probability')
            away_prob = analysis_result.get('away_win_probability')
            confidence = analysis_result.get('confidence')
            pred_score = analysis_result.get('predicted_score', '')

            # 取得 league + team names（從 result 中不一定有，用 game_id 從 games 表抓）
            cur.execute(
                """
                SELECT t_home.league,
                       t_home.english_name AS home_name,
                       t_away.english_name AS away_name,
                       g.match_date
                FROM predictx.games g
                JOIN predictx.teams t_home ON g.home_team_id = t_home.team_id
                JOIN predictx.teams t_away ON g.away_team_id = t_away.team_id
                WHERE g.game_id = %s::uuid
                """,
                (game_id,)
            )
            g_row = cur.fetchone()
            league = g_row['league'] if g_row else None
            home_name = g_row['home_name'] if g_row else None
            away_name = g_row['away_name'] if g_row else None

            # 🆕 確保 ai_prediction_history 寫入前存在（舊 snapshot 為 v1-baseline）
            cur.execute(
                """
                INSERT INTO predictx.ai_prediction_history (
                    game_id, league, prediction_time,
                    home_team, away_team,
                    home_win_probability, away_win_probability, confidence, predicted_score,
                    prompt_version
                ) VALUES (%s::uuid, %s, NOW(), %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (game_id, prompt_version) DO NOTHING
                """,
                (
                    game_id, league, home_name, away_name,
                    float(home_prob) if home_prob is not None else None,
                    float(away_prob) if away_prob is not None else None,
                    int(confidence) if confidence is not None else None,
                    str(pred_score)[:10] if pred_score else None,
                    prompt_ver
                )
            )
        except Exception as hist_err:
            print(f"  ⚠ ai_prediction_history write fail (non-fatal): {hist_err}")
            conn.rollback()
            # 重開游標（rollback 後 ORIG cursor 已關）
            cur = conn.cursor()

        # 主要寫入（原本功能）
        # 同步記錄「分析時的 pitcher 狀態時間」— 用 game 的 pitcher_updated_at（若有）
        # 目的：get_pending_games 可判斷「投手資料已更新但尚未重分析」
        cur.execute(
            "SELECT pitcher_updated_at FROM predictx.games WHERE game_id = %s::uuid",
            (game_id,)
        )
        p_row = cur.fetchone()
        current_pitcher_update = p_row['pitcher_updated_at'] if p_row else None

        cur.execute(
            """INSERT INTO predictx.game_analysis (game_id, analysis_data, updated_at, last_analyzed_pitcher_update)
               VALUES (%s, %s, CURRENT_TIMESTAMP, %s)
               ON CONFLICT (game_id)
               DO UPDATE SET
                   analysis_data = EXCLUDED.analysis_data,
                   updated_at = CURRENT_TIMESTAMP,
                   last_analyzed_pitcher_update = EXCLUDED.last_analyzed_pitcher_update""",
            (game_id, json.dumps(analysis_result, default=str), current_pitcher_update)
        )
        conn.commit()
        cur.close()

        # 🆕 [2026-06-27] 資料更新立即觸發推播（信心度 >= 8 → 所有 Premium + push_enabled 用戶）
        # 用 threading 在背景觸發推播，不阻塞 commit 與 main 流程
        try:
            confidence = analysis_result.get('confidence')
            if confidence is not None and float(confidence) >= 8:
                match_info = {
                    'game_id': game_id,
                    'home_team': home_name or '主隊',
                    'away_team': away_name or '客隊',
                    'match_date': str(g_row.get('match_date')) if g_row else '',
                }
                confidence_val = float(confidence)

                # 用 thread 跑推播迴圈（完全獨立於 main thread 的 event loop）
                import threading
                import sys
                print(f"  [PUSH] 觸發推播: game={game_id[:8]}... conf={confidence_val}", flush=True)
                def _push_worker():
                    try:
                        import asyncio as _aio
                        from push_service import trigger_match_push
                        result = _aio.run(trigger_match_push(
                            match_info=match_info,
                            confidence=confidence_val,
                            min_tier='premium',
                        ))
                        print(f"  [PUSH] 結果: {result}", flush=True)
                    except Exception as worker_err:
                        import traceback
                        print(f"  ⚠ push worker error: {worker_err}", flush=True)
                        print(f"  ⚠ traceback: {traceback.format_exc()}", flush=True)

                t = threading.Thread(target=_push_worker, daemon=False)
                t.start()
                print(f"  [PUSH] thread started, is_alive={t.is_alive()}", flush=True)
                return True, t  # 回傳 thread 讓 main() 可以 join
        except Exception as push_err:
            # 推播失敗不影響分析結果（已 commit）
            print(f"  ⚠ push trigger failed (non-fatal): {push_err}", flush=True)

        return True, None
    except Exception as e:
        print(f"  ❌ DB save error for {game_id}: {e}")
        conn.rollback()
        return False, None
    finally:
        try:
            cur.close()
        except Exception:
            pass


def main():
    print(f"=== PredictX Daily Pipeline START === {datetime.now().isoformat()}")

    # 1. 連線資料庫
    try:
        conn = get_db_connection()
        print("✅ Database connected")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        sys.exit(1)

    # 2. 計算目標日期：今日 + 明日（台北時間）
    taipei_tz = datetime.now().astimezone().tzinfo
    today = datetime.now(taipei_tz).strftime('%Y-%m-%d')
    tomorrow = (datetime.now(taipei_tz) + timedelta(days=1)).strftime('%Y-%m-%d')
    target_dates = [today, tomorrow]
    print(f"📅 Target dates: {target_dates}")

    # 3. 分析賽事
    pending = get_pending_games(conn, target_dates)
    print(f"🔍 Found {len(pending)} games to analyze")

    if pending:
        engine = AnalysisEngine()
        success = 0
        push_threads = []  # 收集推播 threads
        for idx, game in enumerate(pending):
            game_id = game['game_id']
            try:
                result = engine.analyze_game(game_id)
                if result:
                    saved, push_thread = save_analysis(conn, game_id, result)
                    if saved:
                        print(f"  [{idx+1}/{len(pending)}] ✓ {game_id[:8]}...")
                        success += 1
                        if push_thread:
                            push_threads.append(push_thread)
                    else:
                        print(f"  [{idx+1}/{len(pending)}] ✗ {game_id[:8]}... no result")
                else:
                    print(f"  [{idx+1}/{len(pending)}] ✗ {game_id[:8]}... no result")
            except Exception as e:
                print(f"  [{idx+1}/{len(pending)}] ✗ {game_id[:8]}... Error: {e}")
        engine.close()
        print(f"📊 Analysis: {success}/{len(pending)} games analyzed")

        # 等待所有推播 threads 完成（最多等 30 秒）
        if push_threads:
            print(f"  [PUSH] 等待 {len(push_threads)} 個推播 thread 完成...", flush=True)
            for t in push_threads:
                t.join(timeout=30)
            print(f"  [PUSH] 所有推播 thread 已完成", flush=True)
    else:
        print("📊 No pending games to analyze")

    # 4. 執行結算
    try:
        settler = SettlementEngine()
        settled_count = settler.settle_games()
        print(f"💰 Settlement: {settled_count} games settled")
    except Exception as e:
        print(f"⚠️ Settlement failed: {e}")

    conn.close()
    print(f"=== PredictX Daily Pipeline END === {datetime.now().isoformat()}")


if __name__ == "__main__":
    main()
