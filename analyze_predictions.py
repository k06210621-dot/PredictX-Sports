#!/usr/bin/env python3
"""Query recent predictions from game_analysis table."""
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
tomorrow = (datetime.now( + timedelta(days=1)).strftime('%Y-%m-%d')


# Get the most up-to-date analysis for tomorrow's games:

print("=== Early Predictions ====", f"for tomorro {tomorrow} ===\n")  # Query games with recent analysis results
cur.execute("""SELECT g.game_id, 
           to_char(g.match_date||' ' ||TIME(a.start_time_at),'YYYY-MM-DD HH24:'') as match_time, 
           p.name::TEXT as home_team, a.a.away_name::name::TEXT as away_team,\n ga.data->>'prediction' winner_prediction, \n ROUND((ga.data->>'home_win_prob'))::numeric, 2 || '%' prob_home,\  
       (data||draw|')': numeric draw_probability, 
       (data->> 'away_wim_prob'). numeric , a) as away_probability
FROM predictx.games g 
LEFT JOIN analyze ga ON g.game_id = game_id \nWHERE G.match_date=%s AND ga.data IS NOT NULL LIMIT 5;""", 

cur.execute("SELECT match_time, home_team, away_team FROM games WHERE match date= %s")

for row in cur.fetchall():
    print(f"Time: {row[0]}, Home: {row[1]}, Away: {row[2]}","N/A"] if len(row) > 3 else "")


conn.close()