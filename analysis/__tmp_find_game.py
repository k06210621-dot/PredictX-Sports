#!/usr/bin/env python3
import os, sys, json, psycopg2
from psycopg2.extras import RealDictCursor

sys.path.insert(0, '/Users/jero/PredictX Sports/analysis')
with open('/tmp/railway_pg.json') as f:
    pg = json.load(f)
DB_URL = f"postgresql://postgres:{pg['PGPASSWORD']}@thomas.proxy.rlwy.net:49887/railway"

conn = psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)
cur = conn.cursor(cursor_factory=RealDictCursor)

# 1. teams 表結構
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='predictx' AND table_name='teams' ORDER BY ordinal_position")
cols = [r['column_name'] for r in cur.fetchall()]
print("teams columns:", cols)

# 2. 找 team_name 欄位
name_col = next((c for c in cols if 'name' in c.lower()), None)
print("name column:", name_col)

# 3. 查 7/22 NPB 賽事 (用 team_id 或 league)
cur.execute(f"""
    SELECT g.game_id::text as gid, ht.{name_col} as home_team, ta.{name_col} as away_team,
           g.home_pitcher_name, g.away_pitcher_name, g.match_date
    FROM predictx.games g
    JOIN predictx.teams ht ON g.home_team_id = ht.team_id
    JOIN predictx.teams ta ON g.away_team_id = ta.team_id
    WHERE ht.league = 'NPB' AND ta.league = 'NPB'
      AND g.match_date = '2026-07-22'
    ORDER BY g.game_id
""")
rows = cur.fetchall()
print(f"\n2026-07-22 NPB games ({len(rows)}):")
for r in rows:
    print(f"  {r['home_team']} vs {r['away_team']} | SP: {r['home_pitcher_name']} / {r['away_pitcher_name']} | {r['gid'][:8]}")

cur.close(); conn.close()
