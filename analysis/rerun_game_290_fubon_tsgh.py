#!/usr/bin/env python3
"""
手動重跑 Game 290 (Fubon Guardians vs TSG Hawks) 2026-08-26 CPBL 賽事：
1. 刪除 game_analysis 現有資料
2. 重新觸發 analyze_game
3. 寫回 DB
（不觸發推播 — 重跑手動觸發的賽事不應自動推播）
"""
import os
import sys
import json
import psycopg2
from psycopg2.extras import RealDictCursor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analysis_engine import AnalysisEngine

GAME_ID = "27d0d6f8-9866-48ec-9376-29058874e047"


def _norm_url():
    url = os.getenv('DATABASE_URL', '')
    if 'postgres.railway.internal' in url:
        os.environ['DATABASE_URL'] = url.replace(
            'postgres.railway.internal:5432',
            'thomas.proxy.rlwy.net:49887'
        )


def _json_safe(obj):
    """遞迴把 date / datetime / Decimal 物件轉成 JSON 序列化格式"""
    import datetime
    from decimal import Decimal
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(x) for x in obj]
    if isinstance(obj, datetime.datetime):
        return obj.isoformat()
    if isinstance(obj, datetime.date):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    return obj


def main():
    _norm_url()

    conn = psycopg2.connect(os.environ['DATABASE_URL'], cursor_factory=RealDictCursor)
    conn.autocommit = False
    cur = conn.cursor()

    # 1. 查 game + 確認現有分析資料
    cur.execute('''
        SELECT g.game_id, g.match_date, g.status,
               g.home_pitcher_name, g.away_pitcher_name, g.pitcher_updated_at,
               ht.english_name as home_team, at.english_name as away_team,
               ga.analysis_id, ga.created_at, ga.updated_at,
               ga.last_analyzed_pitcher_update
        FROM predictx.games g
        JOIN predictx.teams ht ON g.home_team_id = ht.team_id
        JOIN predictx.teams at ON g.away_team_id = at.team_id
        LEFT JOIN predictx.game_analysis ga ON g.game_id = ga.game_id
        WHERE g.game_id = %s::uuid
    ''', (GAME_ID,))
    game = cur.fetchone()

    if not game:
        print(f"❌ Game {GAME_ID[:8]} 不存在")
        cur.close()
        conn.close()
        return

    print("=" * 60)
    print(f"📌 Game {GAME_ID[:8]}")
    print(f"   {game['home_team']} (主) vs {game['away_team']} (客)")
    print(f"   日期: {game['match_date']} | 狀態: {game['status']}")
    print(f"   先發投手: 主={game['home_pitcher_name']} 客={game['away_pitcher_name']}")
    print(f"   pitcher_updated_at: {game['pitcher_updated_at']}")
    print()

    if game['analysis_id']:
        print(f"🗑️  現有 analysis: ID={game['analysis_id']}")
        print(f"   created: {game['created_at']}")
        print(f"   updated: {game['updated_at']}")
        print(f"   last_analyzed_pitcher_update: {game['last_analyzed_pitcher_update']}")

        # 2. 刪除現有分析資料
        cur.execute("DELETE FROM predictx.game_analysis WHERE game_id = %s::uuid", (GAME_ID,))
        print(f"   ✅ 已刪除 {cur.rowcount} 筆")
    else:
        print("ℹ️  game_analysis 無現有資料，不需刪除")
    cur.close()
    conn.commit()

    # 3. 觸發單場分析（不推播）
    print()
    print("=" * 60)
    print(f"🤖 開始 AI 分析（使用 {os.getenv('CLOUD_LLM_PROVIDER', 'qwen')}/"
          f"{os.getenv('CLOUD_LLM_MODEL', '預設模型')}）...")
    print("=" * 60)

    engine = AnalysisEngine(conn=conn)
    try:
        result = engine.analyze_game(GAME_ID)

        if not result:
            print("\n❌ analyze_game 回傳 None（fallback 完全失敗）")
            return

        # 4. 寫入 DB（與 rerun_one_save 一樣的 save 邏輯，但不推播）
        # 用 last_analyzed_pitcher_update 標記「這次分析是基於哪個 pitcher 狀態」
        cur = conn.cursor()
        cur.execute(
            "SELECT pitcher_updated_at FROM predictx.games WHERE game_id = %s::uuid",
            (GAME_ID,)
        )
        p = cur.fetchone()
        pitcher_ts = p['pitcher_updated_at'] if p else None

        cur.execute(
            """INSERT INTO predictx.game_analysis (game_id, analysis_data, updated_at, last_analyzed_pitcher_update)
               VALUES (%s, %s, CURRENT_TIMESTAMP, %s)
               ON CONFLICT (game_id)
               DO UPDATE SET analysis_data = EXCLUDED.analysis_data,
                             updated_at = CURRENT_TIMESTAMP,
                             last_analyzed_pitcher_update = EXCLUDED.last_analyzed_pitcher_update""",
            (GAME_ID, json.dumps(_json_safe(result)), pitcher_ts)
        )
        conn.commit()
        cur.close()
        print("\n✅ 寫入成功")

        # 5. 顯示結果摘要
        print()
        print("=" * 60)
        print(f"📊 分析結果：{game['home_team']} vs {game['away_team']}")
        print("=" * 60)
        print(f"預測主隊勝率：{result.get('home_win_probability', 'N/A')}")
        print(f"預測客隊勝率：{result.get('away_win_probability', 'N/A')}")
        print(f"信心度：{result.get('confidence', 'N/A')}/10")
        print(f"預測比分：{result.get('predicted_score', 'N/A')}")
        summary = result.get('summary', '')
        if summary:
            print(f"\n📝 摘要（前 300 字）：\n{summary[:300]}...")

        # 雷達圖
        radar = result.get('radar_chart', {})
        if radar:
            print(f"\n📈 雷達圖：")
            for k, v in radar.items():
                if isinstance(v, (int, float)):
                    print(f"  {k}: {v:.2f}")
                else:
                    print(f"  {k}: {v}")
    except Exception as e:
        conn.rollback()
        print(f"\n❌ 分析出錯：{e}")
        import traceback
        traceback.print_exc()
    finally:
        engine.close()
        cur.close() if 'cur' in dir() else None
        conn.close()


if __name__ == '__main__':
    main()
