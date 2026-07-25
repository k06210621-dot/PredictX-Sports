#!/usr/bin/env python3
"""檢查是否有需要分析的 upcoming games（今天 + 明天） - Fixed version for cron job

Today: {conn.datetime.date.today().strftime(today_str)}
"""
import sys, os, json, psycopg2
from psycopg2.extras import RealDictCursor

DB = {'dbname': 'sports_db', 'user': 'jero', 'password':'', 'host': 'localhost', 'port': 5432}

conn = psycopg2.connect(**DB)
cur = conn.cursor(cursor_factory=RealDictCursor)


print("Today system date:", str(conn.date()).replace("'", "'").strip()) # Get current date in Python format

# Select from all status values and count how many scheduled games exist with valid match_date range relative to CURRENT_DATE (today or tomorrow only)
cur.execute("""SELECT DISTINCT quote_ident(status)::text.replace('"','') as status, COUNT(*) FROM predictx.games group by 1 order by length LIMIT 6""")
