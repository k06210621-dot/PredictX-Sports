#!/usr/bin/env python3
"""單場 minimax-m3 重跑+結算（一次 railway run 跑一場，避免中途截斷）"""
import os, sys, json, psycopg2
from psycopg2.extras import RealDictCursor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ['CLOUD_LLM_PROVIDER'] = 'nvidia'
os.environ['CLOUD_LLM_MODEL'] = 'minimaxai/minimax-m3'

from analysis_engine import AnalysisEngine
from settlement_engine import SettlementEngine

GAME_PREFIX = os.getenv('GAME_PREFIX')
LEAGUE = os.getenv('LEAGUE', 'NPB')
TARGET_DATE = os.getenv('TARGET_DATE', '2026-06-20')

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
    cur = engine.conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('''
        SELECT g.game_id::text
        FROM predictx.games g
        JOIN predictx.teams th ON g.home_team_id = th.team_id
        WHERE th.league = %s AND g.match_date = %s
          AND g.game_id::text LIKE %s
    ''', (LEAGUE, TARGET_DATE, GAME_PREFIX + '%'))
    gid = cur.fetchone()
    cur.close()
    if not gid:
        print(f"找不到 {GAME_PREFIX} 場次")
        engine.close()
        return
    full_id = gid['game_id']
    print(f"重跑單場: {full_id[:8]}")

    res = engine.analyze_game(full_id)
    if res:
        ok = save_no_push(engine.conn, full_id, res)
        print(f"  寫入 {'✓' if ok else '✗'} conf={res.get('confidence')}")
    else:
        print("  ✗ 無結果 (fallback)")
    engine.close()

    # 結算這場
    settler = SettlementEngine()
    cur = settler.conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('''
        SELECT g.game_id::text, g.home_team_score, g.away_team_score, ga.analysis_data
        FROM predictx.games g
        JOIN predictx.game_analysis ga ON g.game_id = ga.game_id
        WHERE g.game_id::text LIKE %s
    ''', (GAME_PREFIX + '%',))
    r = cur.fetchone()
    cur.close()
    if r:
        settler._settle_win_loss(r['game_id'], float(r['home_team_score']), float(r['away_team_score']), r['analysis_data'])
        settler.conn.commit()
    settler.close()
    print("單場完成")

if __name__ == '__main__':
    main()
