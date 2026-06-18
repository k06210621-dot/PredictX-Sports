#!/usr/bin/env python3
"""補跑 6/16 剩餘 7 場 MLB 分析"""
import os, sys, json, psycopg2
from psycopg2.extras import RealDictCursor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analysis_engine import AnalysisEngine

# 連線
database_url = os.getenv('DATABASE_URL')
if database_url:
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    conn = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
else:
    conn = psycopg2.connect(
        dbname='sports_db', user='jero', password='',
        host='localhost', port=5432, cursor_factory=RealDictCursor
    )

game_ids = [
    '6892c9ec-822a-4a9c-ac5c-39c7a2a5c138',
    '36e2afaf-ef80-4a87-aa25-0f40dd0d42eb',
    '585a737d-eae6-47c5-a6d1-deb549141c88',
    '5689ad79-316f-4b14-8407-fc5a80d50254',
    'f77f2337-d8c7-4220-bb57-81adc58d8ee0',
    'a5d1a949-caba-4bb4-b815-5685054cef73',
    '3254029b-ee51-4515-852f-41cf4b90055f',
]

engine = AnalysisEngine(conn=conn)
success = 0
for gid in game_ids:
    try:
        result = engine.analyze_game(gid)
        if result:
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO predictx.game_analysis (game_id, analysis_data, updated_at)
                   VALUES (%s, %s, CURRENT_TIMESTAMP)
                   ON CONFLICT (game_id)
                   DO UPDATE SET analysis_data = EXCLUDED.analysis_data, updated_at = CURRENT_TIMESTAMP""",
                (gid, json.dumps(result))
            )
            conn.commit()
            cur.close()
            success += 1
            print(f"  ✓ {gid[:8]}...")
        else:
            print(f"  ✗ {gid[:8]}... no result")
    except Exception as e:
        print(f"  ✗ {gid[:8]}... Error: {e}")
        conn.rollback()

engine.close()
conn.close()
print(f"\n✅ 完成: {success}/{len(game_ids)} 場")
