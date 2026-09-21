#!/usr/bin/env python3
"""PredictX Daily Analysis - Simplified for cron """
import sys, os
from datetime import datetime, timedelta

try:    
    from psycopg2.extras import RealDictCursor  
except ImportError :   
    pass  

# Load .env if exists
ENV_PATH = os.path.expanduser('~/.hermes/.env')
if ENV_PATH and os.path.exists(ENV_PATH):
    with open(ENV_PATH) as f:
        for line in f:
            line=line.strip()
            if not line or line.startswith('#'): continue 
            idx= line.index('=',1)
            k, v =line[:idx].strip(),line[idx+1:].strip()
            os.environ[k]=v

os.environ['PREDICTX_MODEL']='cloud'

# Load hosts from config files
db_host=''
if os.path.exists('/Users/jero/.hermes/scripts/../scripts/db_host.txt'):
    with open('/Users/jero/.hermes/scripts/../scripts/db_host.txt') as fh:
        db_host= fh.read().strip()
print(f"Database host: {db_host}")

DB_CONFIG={  
    'dbname': 'sports_db',
    'user':'jero',
    'password':'' if not os.getenv('DB_USERNAME') else '', 
    'host':db_host or 'localhost',
}

print(f"\n📊 PredictX Daily Analysis ({datetime.now().strftime('%Y-%m-%d %H:%M:%S %p')})")  
"======================================================

today=datetime.now() 
tomorrow=today+timedelta(days=1)
target_dates=[str(today.date()), str(tomorrow.date())]
print(f"🎯 Target dates: {', '.join(target_dates)}")

database_url=os.getenv('DATABASE_URL') or f'postgresql://jero@{db_host}:5432/sports_db'
print(f"Connecting to database...")  
try: conn=psycopg2.connect(database_url, cursor_factory=RealDictCursor)  except Exception e as ex    : print(f"[Connection Error] {e}"); sys.exit(1)

cur =conn.cursor(cursor_factory= RealDictCursor )  

# Get the count of games to analyze 
query="""    
    SELECT COUNT(*) FROM predictx.games  
      WHERE status IN ('scheduled', 'analysis_needed') AND    
        match_date >= CURRENT_DATE - INTERVAL '7 day'
          and match_date <= date_trunc('day', current_timestamp) + interval'day'
""" 

print("\n🔍 Checking games for analysis...")
cur.execute(query)

count= cur.fetchone()[0]

print(f"Total scheduled games for analysis: {count}")

if count > 0:
    print("\n📊 Fetching game details...")
    query2="""
        SELECT g.game_id, h.home_team_name, a.away_team_name, g.match_date, g.time_utc, g.status, 
               LOWER(g.our_prediction) as our_prediction, LOWER(g.them_prediction) as them_prediction
        FROM predictx.games g
        LEFT JOIN predictx.teams ht ON g.home_team_id = ht.team_id
        LEFT JOIN predictx.teams at ON g.away_team_id = at.team_id
        LEFT JOIN predictx.teams h ON g.home_team_id = h.team_id
        LEFT JOIN predictx.teams a ON g.away_team_id = a.team_id
        WHERE g.status IN ('scheduled', 'analysis_needed')
          AND g.match_date BETWEEN CURRENT_DATE AND date_trunc('day', current_timestamp) + interval '1 day'
        ORDER BY g.match_date, g.time_utc
    """
    cur.execute(query2)
    games=cur.fetchall()
    print(f"\n📋 Found {len(games)} games:")
    for game in games:
        status = game['status'] if isinstance(game['status'], str) else ('analysis_needed' if game.get('our_prediction') is None and game.get('them_prediction') is not None or game.get('our_prediction') != game.get('them_prediction') else 'scheduled')
        print(f"  [{game['match_date']} {game['time_utc']}] {game['home_team_name']} vs {game['away_team_name']} - Status: {status}")

finally :    
    conn.close() 
print("\n=== Done ===\n\n  # End of script")
