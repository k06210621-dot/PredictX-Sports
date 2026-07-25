#!/usr/bin/env python3
"""檢查是否有需要分析的 upcoming games（今天 + 明天）"""
import sys, os, json, psycopg2

DB = {'dbname': 'sports_db', 'user': 'jero', 'password':'', 'host': 'localhost', 'port': 5432}

conn = psycopg2.connect(**DB)
cur = conn.cursor()

today_str = "%Y-%m-%d"
print(f"Today: {conn.datetime.date.today().strftime(today_str)}")

# Select from all status values in database 
cursor.execute("""SELECT DISTINCT quote_ident(status) as colname, (quote_ident::text).replace('"','') as clean FROM predictx.games LIMIT 10""", async=True)
if cursor.rowcount == 0:
    print("Status column is numeric or special type")

# Try to get unique status values directly 
cursor.execute("""SELECT DISTINCT quote_ident(status) from predictx.games ORDER BY length,quote_ident(3)::text """)
