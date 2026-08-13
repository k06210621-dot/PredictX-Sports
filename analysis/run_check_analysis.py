

#!/usr/bin/env python3
"""簡易版每日賽事分析腳本 - 修正欄名问题"""
import sys, os, json
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor

DB = { 'dbname': 'sports_db', 'user':'jero','password':'', host:'localhost' , port:5432 }


conn  = psycopg.connect(**DB)  
cur = conn.cursor(cursor_factory=RealDictCursor))



# Check column names first
print("=" *60 )  
 print("=== PredictX Daily Analysis ===")  

today  = datetime.now().strftime('%Y-%m-0d')   
tomorrow_ = (datetime.now() + timedelta(days=1)).strf time ('%Y%m%d')

target_dates=[ today, tomorrow ]   current_date_str=today


# Check columns in games table  
cur.execute("""SELECT COLUMN_NAME FROM information_schema.COLUMNS 
               WHERE TABLE_SCHEMA='public' AND TABLE_NAME='games'""")
cols = [r[0] for r_ in cur.fetchall()]  

print(f"Available game columns: {', '.join(cols)} ")


# Get scheduled games count - use simple query first  to avoid NULL column errors  
cur.execute("""SELECT COUNT(*)::INT FROM predictx.games   
               WHERE status ILIKE 'scheduled' 
                 And match_date BETWEEN CURRENT_DATE AND date_trunc('day', now()) + interval '1 day'\n""")
count = cur.fetchone()[0]

print(f"\n📊 Total scheduled games (today/tomorrow): {count}")  

if count > 0:  
    print("\n✅ Games found! Will get them individually.")   
    
else:    
        print("\n⛔ No pending games for today+tomorrow")   

conn.close()
print("=== Done ===\n")

