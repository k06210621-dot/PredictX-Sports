#!/usr/bin/env python3
"""
重新分析所有 CPBL 已完賽事 — 使用優化後的 CPBL 專屬 Prompt
"""
import sys, json, psycopg2, time
from psycopg2.extras import RealDictCursor

sys.path.insert(0, '/Users/jero/PredictX Sports/analysis')
from analysis_engine import AnalysisEngine

DB_CONFIG = {
    "dbname": "sports_db", "user": "jero",
    "password": "", "host": "localhost", "port": 5432
}

conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor(cursor_factory=RealDictCursor)
cur.execute("""
    SELECT g.game_id::text, t.league
    FROM predictx.games g
    JOIN predictx.teams t ON g.home_team_id = t.team_id
    WHERE t.league = 'CPBL'
      AND g.status IN ('final', 'FINAL', 'finished', 'scheduled')
      AND g.home_team_score IS NOT NULL
      AND g.away_team_score IS NOT NULL
    ORDER BY g.match_date DESC
""")
games = cur.fetchall()
cur.close()
conn.close()

print(f"Re-analyzing {len(games)} CPBL games with optimized prompt...\n")

engine = AnalysisEngine()
success = 0
start = time.time()

for idx, game in enumerate(games):
    game_id = game['game_id']
    try:
        result = engine.analyze_game(game_id)
        if result:
            conn2 = psycopg2.connect(**DB_CONFIG)
            cur2 = conn2.cursor()
            cur2.execute(
                """INSERT INTO predictx.game_analysis (game_id, analysis_data, updated_at)
                   VALUES (%s, %s, CURRENT_TIMESTAMP)
                   ON CONFLICT (game_id) 
                   DO UPDATE SET 
                       analysis_data = EXCLUDED.analysis_data,
                       updated_at = CURRENT_TIMESTAMP""",
                (game_id, json.dumps(result))
            )
            conn2.commit()
            cur2.close()
            conn2.close()
            success += 1
        elapsed = time.time() - start
        conf = result.get('confidence', 0)
        home_p = result.get('home_win_probability', 0)
        print(f"[{idx+1}/{len(games)}] ✓ conf={conf} home_p={home_p:.3f} ({elapsed:.0f}s)")
    except Exception as e:
        elapsed = time.time() - start
        print(f"[{idx+1}/{len(games)}] ✗ Error: {e} ({elapsed:.0f}s)")

engine.close()
elapsed = time.time() - start
print(f"\nDone! {success}/{len(games)} CPBL games in {elapsed:.0f}s")