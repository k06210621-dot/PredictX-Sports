#!/usr/bin/env python3
"""驗證 Tigers vs Astros AI 分析是否已正確寫入"""
import os, sys, json, psycopg2
from psycopg2.extras import RealDictCursor

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

game_id = '61b6b115-be70-4743-a8de-2be2a7d2a2bd'

cur = conn.cursor()
cur.execute(
    """SELECT analysis_data, created_at, updated_at
       FROM predictx.game_analysis
       WHERE game_id = %s""",
    (game_id,)
)
result = cur.fetchone()

if result:
    print("✅ 找到分析記錄")
    print(f"建立時間: {result['created_at']}")
    print(f"更新時間: {result['updated_at']}")
    print("\n分析內容:")
    print(json.dumps(result['analysis_data'], indent=2, ensure_ascii=False))
else:
    print("❌ 未找到分析記錄")

cur.close()
conn.close()