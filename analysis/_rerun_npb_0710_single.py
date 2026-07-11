#!/usr/bin/env python3
"""手動重跑 2026-07-10 的 NPB 賽事分析（套用 P0+P1 K/BB 加成）。"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

from analysis_engine import AnalysisEngine
from run_analysis import save_analysis

DB = dict(host='thomas.proxy.rlwy.net', port=49887, user='postgres',
          password='REDACTED', dbname='railway')
TARGET_DATE = '2026-07-10'

def main():
    conn = psycopg2.connect(cursor_factory=RealDictCursor, **DB)
    cur = conn.cursor()
    cur.execute("""
        SELECT g.game_id::text, g.match_date,
               (ga.analysis_data->'actual_result'->>'is_hit')::boolean AS is_hit
        FROM predictx.games g
        JOIN predictx.teams ht ON g.home_team_id = ht.team_id
        LEFT JOIN predictx.game_analysis ga ON g.game_id = ga.game_id
        WHERE ht.league = 'NPB' AND g.match_date = %s
        ORDER BY g.game_id
    """, (TARGET_DATE,))
    rows = cur.fetchall()
    cur.close()
    print(f"=== NPB {TARGET_DATE} rerun START {datetime.now().isoformat()} ===")
    print(f"Found {len(rows)} NPB games")

    engine = AnalysisEngine(conn=conn)
    success = skipped = failed = fallback = 0
    for r in rows:
        gid = r['game_id']
        if r['is_hit'] is not None:
            print(f"  [SKIP] {gid[:8]} settled")
            skipped += 1
            continue
        try:
            result = engine.analyze_game(gid)
            if not result:
                print(f"  [FAIL] {gid[:8]} no result")
                failed += 1
                continue
            summary = str(result.get('summary', ''))
            is_fallback = ('computed fallback' in summary.lower() or
                           'AI output incomplete' in summary)
            saved, _ = save_analysis(conn, gid, result)
            if saved:
                tag = ' [FALLBACK-no-K/BB]' if is_fallback else ''
                print(f"  [OK]{tag} {gid[:8]} hp={result.get('home_win_probability')} ap={result.get('away_win_probability')}")
                if is_fallback:
                    fallback += 1
                else:
                    success += 1
            else:
                print(f"  [FAIL] {gid[:8]} save False")
                failed += 1
        except Exception as e:
            print(f"  [ERR] {gid[:8]}: {str(e)[:150]}")
            failed += 1
        time.sleep(1)

    print(f"=== DONE normal={success} fallback={fallback} skipped={skipped} failed={failed} ===")
    conn.close()

if __name__ == '__main__':
    main()
