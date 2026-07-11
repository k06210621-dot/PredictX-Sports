#!/usr/bin/env python3
"""
手動重跑 7/10 之後（含 7/10）的 NPB 賽事分析，套用 P0+P1 (K/BB 加成)。
只對 actual_result 為 null 的場次生效（不覆蓋已結算結果）。
連 Railway proxy DB（關鍵字參數，避開密碼遮罩）。
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
        SELECT g.game_id::text, g.match_date,
               (ga.analysis_data->'actual_result'->>'is_hit')::boolean AS is_hit
        FROM predictx.games g
        JOIN predictx.teams ht ON g.home_team_id = ht.team_id
        LEFT JOIN predictx.game_analysis ga ON g.game_id = ga.game_id
        WHERE ht.league = 'NPB' AND g.match_date >= '2026-07-10'
        ORDER BY g.match_date, g.game_id
    """)
    rows = cur.fetchall()
    cur.close()
    print(f"=== NPB 7/10+ rerun START {datetime.now().isoformat()} ===")
    print(f"Found {len(rows)} NPB games >= 2026-07-10")

    engine = AnalysisEngine(conn=conn)
    success = skipped = failed = fallback = 0
    for r in rows:
        gid = r['game_id']
        if r['is_hit'] is not None:
            print(f"  [SKIP] {gid[:8]} {r['match_date']} settled")
            skipped += 1
            continue
        try:
            result = engine.analyze_game(gid)
            if not result:
                print(f"  [FAIL] {gid[:8]} no result")
                failed += 1
                continue
            # 偵測是否走 fallback（analysis_engine 在 fallback 時 summary 會含標記）
            summary = str(result.get('summary', ''))
            is_fallback = ('computed fallback' in summary.lower() or
                           'AI output incomplete' in summary)
            saved, _ = save_analysis(conn, gid, result)
            if saved:
                tag = ' [FALLBACK]' if is_fallback else ''
                print(f"  [OK]{tag} {gid[:8]} {r['match_date']} hp={result.get('home_win_probability')} ap={result.get('away_win_probability')}")
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
        time.sleep(1)  # 避免撞 rate limit

    print(f"=== DONE normal={success} fallback={fallback} skipped={skipped} failed={failed} ===")
    conn.close()

if __name__ == '__main__':
    main()
