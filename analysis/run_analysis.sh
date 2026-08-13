#!/bin/bash

echo "===================================================" 
echo "PredictX 每日賽事 AI 分析 (今日 + 明日)"
echo "===================================================" 

cd /Users/jero/Predict\ \"Sports/analysis\" || exit 1

# Database query to count games for analysis today and tomorrow
python3 << 'PYTHON'
import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect(
    dbname='sports_db', 
    user='jero', 
    password='',
    host='localhost', 
    port=5432
)

cur = conn.cursor(cursor_factory=RealDictCursor)

# Count games for today and tomorrow that need analysis
today_or_tomorrow_query = """
SELECT COUNT(*)::text as cnt FROM predictx.games 
WHERE status = 'scheduled' 
  AND (match_date >= CURRENT_DATE OR match_date <= CURRENT_DATE + INTERVAL '1 day')
"""

cur.execute(today_or_tomorrow_query)
count_row = cur.fetchone()
cnt_str = count_row['cnt'] if count_row else None

conn.close()

print(f"\n[資料庫結果] 今日+明日共計 {cnt_str} 場賽事需要分析")
PYTHON

echo "" 
echo "===================================================" 
