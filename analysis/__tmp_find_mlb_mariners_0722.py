#!/usr/bin/env python3
import json, psycopg2
from psycopg2.extras import RealDictCursor

with open('/tmp/railway_pg.json') as f:
    pg = json.load(f)
DB_URL = f"postgresql://postgres:{pg['PGPASSWORD']}@thomas.proxy.rlwy.net:49887/railway"

conn = psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)
cur = conn.cursor(cursor_factory=RealDictCursor)

cur.execute("""
    SELECT g.game_id::text gid, ht.english_name home, ta.english_name away,
           g.match_date, g.home_pitcher_name, g.away_pitcher_name
    FROM predictx.games g
    JOIN predictx.teams ht ON g.home_team_id = ht.team_id
    JOIN predictx.teams ta ON g.away_team_id = ta.team_id
    WHERE ht.league = 'MLB' AND ta.league = 'MLB'
      AND g.match_date IN ('2026-07-21','2026-07-22')
      AND (
        (ht.english_name ILIKE '%Mariners%' AND ta.english_name ILIKE '%Reds%')
        OR (ht.english_name ILIKE '%Reds%' AND ta.english_name ILIKE '%Mariners%')
      )
    ORDER BY g.match_date, g.game_id
""")
rows = cur.fetchall()
print(f"Found {len(rows)} candidate games:")
for r in rows:
    print(f"  {r['match_date']} | {r['home']} vs {r['away']} | SP: {r['home_pitcher_name']} / {r['away_pitcher_name']} | {r['gid']}")

cur.close(); conn.close()
