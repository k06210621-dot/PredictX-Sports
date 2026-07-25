#!/usr/bin/env python3
import psycopg2
from datetime import date, timedelta

DB = {
    'dbname': 'sports_db', 
    'user': 'jero', 
    'password': '',
    'host': 'localhost', 
    'port': 5432}

conn = psycopg2.connect(**DB)
cur = conn.cursor()

today = date.today().isoformat()
tomorrow = (date.today() + timedelta(days=1)).isoformat()

print(f"Today ({today}) games:")
cur.execute("SELECT COUNT(*) FROM predictx.games g WHERE DATE(g.match_date)='%s' AND status='scheduled'" % today)
count_today = cur.fetchone()[0]
if count_today > 0:
    print(count_today, 'games found today')
else:
    print('No games scheduled today')

print(f"\nTomorrow ({tomorrow}) games:")
cur.execute("SELECT COUNT(*) FROM predictx.games g WHERE DATE(g.match_date)='%s' AND status='scheduled'" % tomorrow)
count_tomorrow = cur.fetchone()[0]
if count_tomorrow > 0:
    print(count_tomorrow, 'games found tomorrow')
else:
    print('No games scheduled tomorrow')

print(f"\nTotal pending analysis:")
cur.execute("SELECT COUNT(*) FROM predictx.games g LEFT JOIN predictx.game_analysis ga ON g.game_id = ga.game_id WHERE (g.match_date='%s' OR g.match_date='%s') AND status='scheduled' AND (ga.analysis_data IS NULL)" % (today, tomorrow))
print(cur.fetchone()[0], 'games need analysis today or tomorrow')

cur.close()
conn.close()
