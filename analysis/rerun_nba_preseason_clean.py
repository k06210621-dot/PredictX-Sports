#!/usr/bin/env python3
"""
NBA 季前賽 10/03-10/09 乾淨重跑 + 結算
=====================================
修正 look-ahead bias 後，對已完賽的季前賽重新產生預測並結算，
以取得可信的準確率。

安全設計：
- save_no_push：只寫 game_analysis，不觸發 APNs 推播（歷史場次不該推播給用戶）
- 逐場處理，單場失敗不影響其他場
- 寫入 ai_prediction_history（settlement_engine 需要）
- 最後統一跑 settlement 結算
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


def _json_default(o):
    """date/datetime/Decimal 都轉為 JSON 可序列化型別（勿用 default=str，Decimal 會被字串化）"""
    if isinstance(o, (datetime.date, datetime.datetime)):
        return o.isoformat()
    if isinstance(o, Decimal):
        return float(o)
    return str(o)


def save_no_push(conn, game_id, result):
    """寫入 game_analysis（不觸發推播）"""
    if not result:
        return False
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT pitcher_updated_at FROM predictx.games WHERE game_id = %s::uuid",
            (game_id,)
        )
        p = cur.fetchone()
        cur.execute(
            """INSERT INTO predictx.game_analysis
                   (game_id, analysis_data, updated_at, last_analyzed_pitcher_update)
               VALUES (%s::uuid, %s::jsonb, CURRENT_TIMESTAMP, %s)
               ON CONFLICT (game_id)
               DO UPDATE SET analysis_data = EXCLUDED.analysis_data,
                             updated_at = CURRENT_TIMESTAMP,
                             last_analyzed_pitcher_update = EXCLUDED.last_analyzed_pitcher_update""",
            (game_id, json.dumps(result, ensure_ascii=False, default=_json_default),
             p['pitcher_updated_at'] if p else None)
        )
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

    # 撈 10/03-10/09 已完賽的 NBA 場次
    cur.execute("""
        SELECT g.game_id::text, g.match_date::text,
               ht.english_name AS home, at.english_name AS away,
               g.home_team_score, g.away_team_score
        FROM predictx.games g
        JOIN predictx.teams ht ON g.home_team_id = ht.team_id
        JOIN predictx.teams at ON g.away_team_id = at.team_id
        WHERE ht.league = 'NBA'
          AND g.match_date BETWEEN '2026-10-03' AND '2026-10-09'
          AND UPPER(g.status) = 'FINAL'
          AND g.home_team_score IS NOT NULL
          AND g.away_team_score IS NOT NULL
        ORDER BY g.match_date, at.english_name
    """)
    games = cur.fetchall()
    cur.close()
    print(f"=== 待重跑 {len(games)} 場 ===")
    for g in games:
        print(f"  {g['match_date']} | {g['away']} @ {g['home']} | {g['away_team_score']}-{g['home_team_score']}")

    # 測試模式：LIMIT=1 只跑第一場
    _limit = os.getenv('GAME_LIMIT')
    if _limit:
        games = games[:int(_limit)]
        print(f"  (測試模式：只跑前 {len(games)} 場)")

    from analysis_engine import AnalysisEngine
    engine = AnalysisEngine(conn=conn)

    ok = 0
    fail = 0
    for i, g in enumerate(games, 1):
        gid = g['game_id']
        label = f"{g['away']} @ {g['home']}"
        print(f"\n[{i}/{len(games)}] {g['match_date']} {label}")
        try:
            res = engine.analyze_game(gid)
            if res:
                saved = save_no_push(conn, gid, res)
                if saved:
                    ok += 1
                    print(f"    ✓ conf={res.get('confidence')} pred={res.get('predicted_score')}")
                else:
                    fail += 1
            else:
                fail += 1
                print("    ✗ 無結果")
        except Exception as e:
            fail += 1
            print(f"    ✗ error: {e}")
            try:
                conn.rollback()
            except Exception:
                pass

    engine.close()
    print(f"\n=== 重跑完成：OK={ok} FAIL={fail} ===")
    conn.close()


if __name__ == '__main__':
    main()
