#!/usr/bin/env python3
"""臨時腳本：對 2026-06-14 的 6 場 NPB 重新跑分析 + 結算"""
import os, sys, json, threading
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from analysis_engine import AnalysisEngine
from settlement_engine import SettlementEngine

TARGET_DATE = '2026-06-14'
LEAGUE = 'NPB'

def get_target_game_ids(engine):
    cur = engine.conn.cursor()
    cur.execute("""
        SELECT g.game_id::text
        FROM predictx.games g
        JOIN predictx.teams th ON g.home_team_id = th.team_id
        WHERE th.league = %s AND g.match_date = %s
        ORDER BY g.game_id
    """, (LEAGUE, TARGET_DATE))
    ids = [r['game_id'] for r in cur.fetchall()]
    cur.close()
    return ids

def save_analysis(conn, game_id, result):
    from run_analysis import save_analysis as _save
    return _save(conn, game_id, result)

def _normalize_db_url():
    url = os.getenv('DATABASE_URL', '')
    if 'postgres.railway.internal' in url:
        url = url.replace('postgres.railway.internal:5432', 'thomas.proxy.rlwy.net:49887')
        os.environ['DATABASE_URL'] = url

def main():
    _normalize_db_url()
    engine = AnalysisEngine()
    game_ids = get_target_game_ids(engine)
    print(f"找到 {len(game_ids)} 場 NPB {TARGET_DATE} 待重跑")

    success = 0
    push_threads = []
    for idx, gid in enumerate(game_ids):
        try:
            res = engine.analyze_game(gid)
            if res:
                saved, t = save_analysis(engine.conn, gid, res)
                if saved:
                    print(f"  [{idx+1}/{len(game_ids)}] ✓ {gid[:8]}... conf={res.get('confidence')}")
                    success += 1
                    if t:
                        push_threads.append(t)
                else:
                    print(f"  [{idx+1}/{len(game_ids)}] ✗ {gid[:8]}... save failed")
            else:
                print(f"  [{idx+1}/{len(game_ids)}] ✗ {gid[:8]}... no result (fallback)")
        except Exception as e:
            print(f"  [{idx+1}/{len(game_ids)}] ✗ {gid[:8]}... error: {e}")

    engine.close()
    print(f"分析完成: {success}/{len(game_ids)}")

    # 等待推播
    for t in push_threads:
        t.join(timeout=30)

    # 結算
    settler = SettlementEngine()
    n = settler.settle_games(re_settle_all=True)
    settler.close()
    print(f"結算完成: {n} 場")

if __name__ == '__main__':
    main()
