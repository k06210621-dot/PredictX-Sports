#!/usr/bin/env python3
"""
NBA 季前賽 10/03-10/08「失敗場次」重跑（修正 P0 根因後）
========================================================
修正內容：
  P0-1 NBA 進階數據全零 → 改用上季(2025-26)數據 + 標示
  P0-2 季前賽主場優勢提示（實測主場勝率僅 43.5%，非 60%）
  P0-3 五五波硬編碼 0.58 → 季前賽期間中性 0.50

只重跑上一輪 is_hit=False 的 11 場，供與原結果對比。
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


def save_analysis_nopush(conn, game_id, result):
    """寫入 game_analysis + ai_prediction_history（不推播）"""
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
        # 同步回流歷史
        cur.execute("""
            SELECT t_h.league AS league,
                   t_h.english_name AS home_name,
                   t_a.english_name AS away_name
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
            """, (game_id, gr['league'], gr['home_name'], gr['away_name'],
                  result.get('home_win_probability'), result.get('away_win_probability'),
                  result.get('confidence'), str(result.get('predicted_score') or '')[:10],
                  'v3-cot-anti-bias-2026-06-24'))
        conn.commit()
        return True
    except Exception as e:
        print(f"    ❌ save error: {e}")
        conn.rollback()
        return False
    finally:
        cur.close()


def main():
    conn = psycopg2.connect(url, cursor_factory=RealDictCursor)
    cur = conn.cursor()
    # 撈上一輪失敗的場次
    cur.execute("""
        SELECT g.game_id::text, g.match_date::text,
               ht.english_name AS home, at.english_name AS away,
               g.home_team_score AS hs, g.away_team_score AS a_s,
               ga.analysis_data->>'predicted_score' AS old_pred,
               ga.analysis_data->>'home_win_probability' AS old_hp
        FROM predictx.games g
        JOIN predictx.teams ht ON g.home_team_id=ht.team_id
        JOIN predictx.teams at ON g.away_team_id=at.team_id
        JOIN predictx.game_analysis ga ON g.game_id=ga.game_id
        WHERE ht.league='NBA' AND g.match_date BETWEEN '2026-10-03' AND '2026-10-08'
          AND ga.analysis_data->'actual_result'->>'is_hit' = 'false'
        ORDER BY g.match_date, at.english_name
    """)
    games = cur.fetchall()
    cur.close()
    print(f"=== 待重跑失敗場次: {len(games)} 場 ===")
    for g in games:
        print(f"  {g['match_date']} | {g['away']} @ {g['home']} | 實際 {g['a_s']}-{g['hs']} | 原預測 {g['old_pred']} (hp={float(g['old_hp']):.2f})")

    from analysis_engine import AnalysisEngine
    engine = AnalysisEngine(conn=conn)
    ok = fail = 0
    for i, g in enumerate(games, 1):
        gid = g['game_id']
        print(f"\n[{i}/{len(games)}] {g['match_date']} {g['away']} @ {g['home']}")
        try:
            res = engine.analyze_game(gid)
            if res and save_analysis_nopush(conn, gid, res):
                ok += 1
                print(f"    ✓ conf={res.get('confidence')} pred={res.get('predicted_score')} hp={res.get('home_win_probability')}")
            else:
                fail += 1
                print("    ✗ 失敗")
        except Exception as e:
            fail += 1
            print(f"    ✗ error: {e}")
            try:
                conn.rollback()
            except Exception:
                pass
    engine.close()
    print(f"\n=== 重跑完成: OK={ok} FAIL={fail} ===")
    conn.close()


if __name__ == '__main__':
    main()
