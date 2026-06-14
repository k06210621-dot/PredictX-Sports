#!/usr/bin/env python3
"""
批次分析剩餘比賽 - 分塊執行，避免 timeout
執行方式: python3 batch_analyze_remaining.py [batch_size=50]
"""
import sys, json, psycopg2, time
from psycopg2.extras import RealDictCursor

sys.path.insert(0, '/Users/jero/PredictX Sports/analysis')
from analysis_engine import AnalysisEngine

DB_CONFIG = {
    "dbname": "sports_db", "user": "jero",
    "password": "", "host": "localhost", "port": 5432
}

BATCH_SIZE = int(sys.argv[1]) if len(sys.argv) > 1 else 50

# 查詢缺少分析的比賽
conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor(cursor_factory=RealDictCursor)
cur.execute("""
    SELECT g.game_id::text
    FROM predictx.games g
    LEFT JOIN predictx.game_analysis ga ON g.game_id = ga.game_id
    WHERE ga.analysis_data IS NULL 
       OR ga.analysis_data->>'home_win_probability' IS NULL
       OR ga.analysis_data->>'home_win_probability' = ''
       OR jsonb_typeof(ga.analysis_data->'home_win_probability') != 'number'
    ORDER BY g.match_date DESC
    LIMIT %s
""", (BATCH_SIZE,))
pending = cur.fetchall()
cur.close()
conn.close()

print(f"Batch processing {len(pending)} games...")

engine = AnalysisEngine()
success = 0
start_time = time.time()

for idx, game in enumerate(pending):
    game_id = game['game_id']
    try:
        result = engine.analyze_game(game_id)
        if result:
            conn2 = psycopg2.connect(**DB_CONFIG)
            cur2 = conn2.cursor()
            cur2.execute(
                """INSERT INTO predictx.game_analysis (game_id, analysis_data, updated_at)
                   VALUES (%s, %s, CURRENT_TIMESTAMP)
                   ON CONFLICT (game_id) 
                   DO UPDATE SET 
                       analysis_data = EXCLUDED.analysis_data,
                       updated_at = CURRENT_TIMESTAMP""",
                (game_id, json.dumps(result))
            )
            conn2.commit()
            cur2.close()
            conn2.close()
            success += 1
        elapsed = time.time() - start_time
        print(f"  [{idx+1}/{len(pending)}] ✓ {game_id[:8]}... ({elapsed:.0f}s elapsed)")
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"  [{idx+1}/{len(pending)}] ✗ {game_id[:8]}... Error: {e} ({elapsed:.0f}s elapsed)")

engine.close()
elapsed = time.time() - start_time
print(f"\nDone! {success}/{len(pending)} games in {elapsed:.0f}s ({elapsed/max(success,1):.1f}s per game)")