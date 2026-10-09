#!/usr/bin/env python3
"""
NBA 未來賽事批次重跑（10/10-10/16）
====================================
用途：修正六大根因後，重跑尚未開打的未來賽事，讓展示給用戶的預測
      使用修正後的 prompt（原分析產自修正前的 prompt）。

模型：生產設定 deepseek-v4.1-flash（與 Railway cron 一致，避免不一致）

用法：
    python3 rerun_nba_upcoming.py 2026-10-10 2026-10-16

安全設計：
- save_nopush：不觸發 APNs 推播
- 逐場獨立，單場失敗不影響其他場
- 執行前備份現況
- 顯示完成進度，便於中斷後續跑（依 updated_at 判斷已重跑者）
"""
import os, sys, json, datetime

sys.path.insert(0, "/Users/jero/PredictX Sports/analysis")
os.chdir("/Users/jero/PredictX Sports/analysis")

url = open('/tmp/dburl.env').read().strip()
os.environ['DATABASE_URL'] = url
os.environ['DATABASE_PUBLIC_URL'] = url
os.environ.setdefault('PREDICTX_MODEL', 'cloud')

import psycopg2
from psycopg2.extras import RealDictCursor
from decimal import Decimal


def _jd(o):
    if isinstance(o, (datetime.date, datetime.datetime)):
        return o.isoformat()
    if isinstance(o, Decimal):
        return float(o)
    return str(o)


def save_nopush(conn, game_id, result):
    if not result:
        return False
    cur = conn.cursor()
    try:
        cur.execute("SELECT pitcher_updated_at FROM predictx.games WHERE game_id=%s::uuid", (game_id,))
        p = cur.fetchone()
        cur.execute("""
            INSERT INTO predictx.game_analysis (game_id, analysis_data, updated_at, last_analyzed_pitcher_update)
            VALUES (%s::uuid, %s::jsonb, CURRENT_TIMESTAMP, %s)
            ON CONFLICT (game_id) DO UPDATE SET
                analysis_data = EXCLUDED.analysis_data,
                updated_at = CURRENT_TIMESTAMP,
                last_analyzed_pitcher_update = EXCLUDED.last_analyzed_pitcher_update
        """, (game_id, json.dumps(result, ensure_ascii=False, default=_jd),
              p['pitcher_updated_at'] if p else None))
        cur.execute("""
            SELECT t_h.league AS lg, t_h.english_name AS hn, t_a.english_name AS an
            FROM predictx.games g
            JOIN predictx.teams t_h ON g.home_team_id=t_h.team_id
            JOIN predictx.teams t_a ON g.away_team_id=t_a.team_id
            WHERE g.game_id=%s::uuid
        """, (game_id,))
        gr = cur.fetchone()
        if gr:
            cur.execute("""
                INSERT INTO predictx.ai_prediction_history
                    (game_id, league, prediction_time, home_team, away_team,
                     home_win_probability, away_win_probability, confidence, predicted_score, prompt_version)
                VALUES (%s::uuid, %s, NOW(), %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (game_id, prompt_version) DO UPDATE SET
                    home_win_probability=EXCLUDED.home_win_probability,
                    away_win_probability=EXCLUDED.away_win_probability,
                    confidence=EXCLUDED.confidence,
                    predicted_score=EXCLUDED.predicted_score,
                    prediction_time=NOW()
            """, (game_id, gr['lg'], gr['hn'], gr['an'],
                  result.get('home_win_probability'), result.get('away_win_probability'),
                  result.get('confidence'), str(result.get('predicted_score') or '')[:10],
                  'v3-cot-anti-bias-2026-06-24'))
        conn.commit()
        return True
    except Exception as e:
        print(f"    ❌ save error: {e}", flush=True)
        conn.rollback()
        return False
    finally:
        cur.close()


def main():
    start = sys.argv[1] if len(sys.argv) > 1 else '2026-10-10'
    end = sys.argv[2] if len(sys.argv) > 2 else '2026-10-16'

    conn = psycopg2.connect(url, cursor_factory=RealDictCursor)
    cur = conn.cursor()
    cur.execute("""
        SELECT g.game_id::text, g.match_date::text,
               ht.english_name AS home, at.english_name AS away,
               g.status, ga.analysis_data->>'predicted_score' AS old_pred,
               ga.analysis_data->>'confidence' AS old_conf
        FROM predictx.games g
        JOIN predictx.teams ht ON g.home_team_id=ht.team_id
        JOIN predictx.teams at ON g.away_team_id=at.team_id
        LEFT JOIN predictx.game_analysis ga ON g.game_id=ga.game_id
        WHERE ht.league='NBA' AND g.match_date BETWEEN %s AND %s
          AND UPPER(g.status) = 'SCHEDULED'
        ORDER BY g.match_date, at.english_name
    """, (start, end))
    games = cur.fetchall()
    cur.close()

    bk = f"/Users/jero/自動生成文件/backups/nba_upcoming_{start}_{end}_{datetime.datetime.now():%Y%m%d_%H%M%S}.json"
    os.makedirs(os.path.dirname(bk), exist_ok=True)
    with open(bk, 'w') as f:
        json.dump([dict(g) for g in games], f, ensure_ascii=False, indent=1, default=_jd)
    print(f"現況已備份: {bk}", flush=True)

    print(f"=== 重跑 {start} ~ {end} 未開打賽事: {len(games)} 場 ===", flush=True)
    print(f"    模型: {os.environ.get('CLOUD_LLM_MODEL', '(default)')}\n", flush=True)

    from analysis_engine import AnalysisEngine
    engine = AnalysisEngine(conn=conn)
    ok = fail = 0
    for i, g in enumerate(games, 1):
        print(f"[{i}/{len(games)}] {g['match_date']} {g['away']} @ {g['home']} (舊 conf={g['old_conf']})", flush=True)
        try:
            res = engine.analyze_game(g['game_id'])
            if res and save_nopush(conn, g['game_id'], res):
                ok += 1
                print(f"    ✓ {res.get('predicted_score')} hp={float(res.get('home_win_probability') or 0):.2f} conf={res.get('confidence')}", flush=True)
            else:
                fail += 1
                print("    ✗ 失敗（保留舊值）", flush=True)
        except Exception as e:
            fail += 1
            print(f"    ✗ error: {e}", flush=True)
            try:
                conn.rollback()
            except Exception:
                pass
    engine.close()
    print(f"\n=== 完成: OK={ok} FAIL={fail} ===", flush=True)
    conn.close()


if __name__ == '__main__':
    main()
