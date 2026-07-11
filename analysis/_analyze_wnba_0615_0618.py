#!/usr/bin/env python3
"""
手動分析 6/15-6/18 新增的 WNBA 賽事。
連 Railway proxy DB，逐場跑 analyze_game + save_analysis。
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

from analysis_engine import AnalysisEngine
from run_analysis import save_analysis

def _get_db_connection():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL 環境變數未設定")
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    return psycopg2.connect(db_url, cursor_factory=RealDictCursor)

def main():
    conn = _get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT g.game_id::text, g.match_date, g.status,
               g.home_team_score, g.away_team_score
        FROM predictx.games g
        JOIN predictx.teams ht ON g.home_team_id = ht.team_id
        LEFT JOIN predictx.game_analysis ga ON g.game_id = ga.game_id
        WHERE ht.league = 'WNBA'
          AND g.match_date BETWEEN '2026-06-15' AND '2026-06-18'
          AND ga.analysis_id IS NULL
        ORDER BY g.match_date, g.game_id
    """)
    rows = cur.fetchall()
    cur.close()
    print(f"=== WNBA 6/15-6/18 analysis START {datetime.now().isoformat()} ===")
    print(f"Found {len(rows)} games to analyze")

    engine = AnalysisEngine(conn=conn)
    success = failed = 0
    for r in rows:
        gid = r['game_id']
        try:
            result = engine.analyze_game(gid)
            if not result:
                print(f"  [FAIL] {gid[:8]} {r['match_date']} no result")
                failed += 1
                continue
            saved, _ = save_analysis(conn, gid, result)
            if saved:
                print(f"  [OK] {gid[:8]} {r['match_date']} hp={result.get('home_win_probability')} ap={result.get('away_win_probability')}")
                success += 1
            else:
                print(f"  [FAIL] {gid[:8]} save False")
                failed += 1
        except Exception as e:
            print(f"  [ERR] {gid[:8]}: {str(e)[:150]}")
            failed += 1
        time.sleep(1)

    print(f"=== DONE success={success} failed={failed} ===")
    conn.close()

if __name__ == '__main__':
    main()
