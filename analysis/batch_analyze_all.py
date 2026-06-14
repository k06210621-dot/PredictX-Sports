#!/usr/bin/env python3
"""
批次分析所有缺少 analysis_data 的比賽
強制寫入新分析結果，包含 Step 5 source_quality
"""
import sys, json, psycopg2
from psycopg2.extras import RealDictCursor

sys.path.insert(0, '/Users/jero/PredictX Sports/analysis')
from analysis_engine import AnalysisEngine

DB_CONFIG = {
    "dbname": "sports_db", "user": "jero",
    "password": "", "host": "localhost", "port": 5432
}

# 找出所有沒有 analysis_data 或 data 為空的比賽
conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor(cursor_factory=RealDictCursor)
cur.execute("""
    SELECT g.game_id::text
    FROM predictx.games g
    LEFT JOIN predictx.game_analysis ga ON g.game_id = ga.game_id
    WHERE ga.analysis_data IS NULL 
       OR ga.analysis_data->>'home_win_probability' IS NULL
       OR ga.analysis_data->>'home_win_probability' = ''
    ORDER BY g.match_date DESC
""")
pending = cur.fetchall()
cur.close()
conn.close()

print(f"Found {len(pending)} games needing analysis")

engine = AnalysisEngine()
success = 0
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
            print(f"  [{idx+1}/{len(pending)}] ✓ {game_id[:8]}... | source_quality: {result.get('source_quality', {}).get('score')}")
        else:
            print(f"  [{idx+1}/{len(pending)}] ✗ {game_id[:8]}... analysis returned None")
    except Exception as e:
        print(f"  [{idx+1}/{len(pending)}] ✗ {game_id[:8]}... Error: {e}")

engine.close()
print(f"\nDone! {success}/{len(pending)} games analyzed successfully.")