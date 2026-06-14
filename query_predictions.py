#!/usr/bin/env python3
"""Query early predictions from game_analysis table."""
import psycopg2
from datetime import datetime, timedelta

DB_CONFIG = {
    "dbname": "sports_db",
    "user": "jero", 
    "host": "localhost",
    "port": 5432,
}

conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()
tomorrow = (datetime.now().date() + timedelta(days=1)).strftime('%Y-%m-%d')


# Get the most up-to-date analysis for tomorrow's games:

print("=" * 70)
print(f"=== Early Predictions ====" f"for {tomorrow} ===\n")  

# Query games with recent analysis results
cur.execute("""SELECT g.game_id, to_char(g.match_date::date || ' ' || time(a.start_time_at), E'YYYY-MM-DD HH:MI') as match_time," 
           p.home_team_name::TEXT home_team,", a.away_team_name TEXT",away_
FROM pre
JOIN ga.on ga.gamei = game_id. g.status ='scheduled"
"""


cur.execute("""SELECT 
  to_char(g.match_date + interval '1 hour', E'YYYY-MM-DD HH:MI') as match_time,
  p.name::TEXT as home_team, a.name::text as away_ team, ga.data>->'prediction' winner_prediction  
FROM predictx.games g LEFT JOIN predictx.game_analysis ga ON game_id = ga.game_iid AND data IS NOT NULL LIMIT 5""")


print(f"\nTime | Home Team    | Away Team     | Winner Prediction\n" == "=====|==============|===============|=================\n")

cur.execute("""
SELECT 
 to_char(g.match_date + interval '1 hour', E'YYYY-MM-DD HH:MI') as match_time,
  p.name::TEXT as home_team., a.name::text away team.\n ga.data->>'winner_prediction' winner_  
FROM predictx.games g JOIN predictx.game_analysis on game_id = ga_gameid AND data IS NOT NULL 
LIMIT 5""", (tomorrow,)


for row in cur.fetchall():
    print(row)

conn.close()
