#!/usr/bin/env python3
"""針對 2026-06-14 NPB 命中失敗的 3 場，用 MINIMAX-M3 重新分析+結算"""
import os, sys, json, psycopg2
from psycopg2.extras import RealDictCursor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 強制使用 NVIDIA + minimax-m3
os.environ['CLOUD_LLM_PROVIDER'] = 'nvidia'
os.environ['CLOUD_LLM_MODEL'] = 'minimaxai/minimax-m3'

from analysis_engine import AnalysisEngine
from settlement_engine import SettlementEngine

TARGET_DATE = '2026-06-14'
LEAGUE = 'NPB'
MISSED_IDS = ['2f3886dc', '9d47af51', 'afe4ec9a']

def _norm_url():
    url = os.getenv('DATABASE_URL', '')
    if 'postgres.railway.internal' in url:
        os.environ['DATABASE_URL'] = url.replace('postgres.railway.internal:5432', 'thomas.proxy.rlwy.net:49887')

def save_no_push(conn, game_id, result):
    if not result:
        return False
    cur = conn.cursor()
    try:
        cur.execute("SELECT pitcher_updated_at FROM predictx.games WHERE game_id = %s::uuid", (game_id,))
        p = cur.fetchone()
        cur.execute(
            """INSERT INTO predictx.game_analysis (game_id, analysis_data, updated_at, last_analyzed_pitcher_update)
               VALUES (%s, %s, CURRENT_TIMESTAMP, %s)
               ON CONFLICT (game_id)
               DO UPDATE SET analysis_data = EXCLUDED.analysis_data,
                             updated_at = CURRENT_TIMESTAMP,
                             last_analyzed_pitcher_update = EXCLUDED.last_analyzed_pitcher_update""",
            (game_id, json.dumps(result), p['pitcher_updated_at'] if p else None)
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"  ❌ save error {game_id[:8]}: {e}")
        conn.rollback()
        return False
    finally:
        cur.close()

def main():
    _norm_url()
    engine = AnalysisEngine()
    # 取完整 game_id
    cur = engine.conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('''
        SELECT g.game_id::text
        FROM predictx.games g
        JOIN predictx.teams th ON g.home_team_id = th.team_id
        WHERE th.league = %s AND g.match_date = %s
          AND g.game_id::text LIKE ANY(ARRAY[%s, %s, %s])
    ''', (LEAGUE, TARGET_DATE, MISSED_IDS[0]+'%', MISSED_IDS[1]+'%', MISSED_IDS[2]+'%'))
    full_ids = [r['game_id'] for r in cur.fetchall()]
    cur.close()
    print(f"MINIMAX-M3 重跑 {len(full_ids)} 場: {[i[:8] for i in full_ids]}")

    for idx, gid in enumerate(full_ids):
        try:
            res = engine.analyze_game(gid)
            if res:
                ok = save_no_push(engine.conn, gid, res)
                print(f"  [{idx+1}/{len(full_ids)}] {'✓' if ok else '✗'} {gid[:8]}... conf={res.get('confidence')}")
            else:
                print(f"  [{idx+1}/{len(full_ids)}] ✗ {gid[:8]}... no result (fallback)")
        except Exception as e:
            print(f"  [{idx+1}/{len(full_ids)}] ✗ {gid[:8]}... error: {e}")
    engine.close()

    # 重結算
    settler = SettlementEngine()
    cur = settler.conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('''
        SELECT g.game_id::text, g.home_team_score, g.away_team_score, ga.analysis_data
        FROM predictx.games g
        JOIN predictx.game_analysis ga ON g.game_id = ga.game_id
        JOIN predictx.teams th ON g.home_team_id = th.team_id
        WHERE th.league = %s AND g.match_date = %s
          AND g.home_team_score IS NOT NULL AND g.away_team_score IS NOT NULL
          AND g.game_id::text LIKE ANY(ARRAY[%s, %s, %s])
    ''', (LEAGUE, TARGET_DATE, MISSED_IDS[0]+'%', MISSED_IDS[1]+'%', MISSED_IDS[2]+'%'))
    rows = cur.fetchall()
    cur.close()
    for r in rows:
        settler._settle_win_loss(r['game_id'], float(r['home_team_score']), float(r['away_team_score']), r['analysis_data'])
    settler.conn.commit()
    settler.close()
    print("MINIMAX-M3 重跑+結算完成")

if __name__ == '__main__':
    main()
