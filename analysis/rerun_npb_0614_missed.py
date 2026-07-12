#!/usr/bin/env python3
"""針對 2026-06-14 NPB 命中失敗的 3 場重新分析（不觸發推播）"""
import os, sys, json, psycopg2
from psycopg2.extras import RealDictCursor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from analysis_engine import AnalysisEngine
from settlement_engine import SettlementEngine

TARGET_DATE = '2026-06-14'
LEAGUE = 'NPB'

def _norm_url():
    url = os.getenv('DATABASE_URL', '')
    if 'postgres.railway.internal' in url:
        os.environ['DATABASE_URL'] = url.replace('postgres.railway.internal:5432', 'thomas.proxy.rlwy.net:49887')

def get_missed_game_ids(engine):
    """抓該日期 league 中 is_hit=False 的 game_id"""
    cur = engine.conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('''
        SELECT g.game_id::text,
               ga.analysis_data->'actual_result'->>'is_hit' as is_hit
        FROM predictx.games g
        JOIN predictx.game_analysis ga ON g.game_id = ga.game_id
        JOIN predictx.teams th ON g.home_team_id = th.team_id
        WHERE th.league = %s AND g.match_date = %s
    ''', (LEAGUE, TARGET_DATE))
    ids = [r['game_id'] for r in cur.fetchall() if str(r['is_hit']).lower() == 'false']
    cur.close()
    return ids

def save_no_push(conn, game_id, result):
    """寫入 analysis_data 但不觸發推播（重跑已結束比賽用）"""
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
    ids = get_missed_game_ids(engine)
    print(f"找到 {len(ids)} 場命中失敗待重跑: {[i[:8] for i in ids]}")

    for idx, gid in enumerate(ids):
        try:
            res = engine.analyze_game(gid)
            if res:
                ok = save_no_push(engine.conn, gid, res)
                print(f"  [{idx+1}/{len(ids)}] {'✓' if ok else '✗'} {gid[:8]}... conf={res.get('confidence')}")
            else:
                print(f"  [{idx+1}/{len(ids)}] ✗ {gid[:8]}... no result (fallback)")
        except Exception as e:
            print(f"  [{idx+1}/{len(ids)}] ✗ {gid[:8]}... error: {e}")
    engine.close()

    # 重結算這 3 場
    settler = SettlementEngine()
    cur = settler.conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('''
        SELECT g.game_id::text, g.home_team_score, g.away_team_score, ga.analysis_data
        FROM predictx.games g
        JOIN predictx.game_analysis ga ON g.game_id = ga.game_id
        JOIN predictx.teams th ON g.home_team_id = th.team_id
        WHERE th.league = %s AND g.match_date = %s
          AND g.home_team_score IS NOT NULL AND g.away_team_score IS NOT NULL
    ''', (LEAGUE, TARGET_DATE))
    rows = [r for r in cur.fetchall() if r['game_id'] in ids]
    cur.close()
    for r in rows:
        settler._settle_win_loss(r['game_id'], float(r['home_team_score']), float(r['away_team_score']), r['analysis_data'])
    settler.conn.commit()
    settler.close()
    print("重跑+結算完成")

if __name__ == '__main__':
    main()
