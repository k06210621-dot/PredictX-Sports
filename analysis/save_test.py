#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/jero/PredictX Sports/analysis')
from analysis_engine import AnalysisEngine
import json
import psycopg2

DB_CONFIG = {
    "dbname": "sports_db",
    "user": "jero",
    "password": "",
    "host": "localhost",
    "port": 5432
}

engine = AnalysisEngine()
game_id = '9ca5a0d1-14e4-473c-820a-fd2d10f6915d'
result = engine.analyze_game(game_id)

if result:
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO predictx.game_analysis (game_id, analysis_data, updated_at)
           VALUES (%s, %s, CURRENT_TIMESTAMP)
           ON CONFLICT (game_id) 
           DO UPDATE SET 
               analysis_data = EXCLUDED.analysis_data,
               updated_at = CURRENT_TIMESTAMP""",
        (game_id, json.dumps(result))
    )
    conn.commit()
    cur.close()
    conn.close()
    print("SUCCESS: Analysis saved to database!")
    print("source_quality:", result.get('source_quality'))
else:
    print("FAIL: Analysis returned None")
engine.close()