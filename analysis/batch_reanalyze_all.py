#!/usr/bin/env python3
"""
批次重新分析所有賽事 - 分塊執行，強制覆蓋舊分析
使用強化後的 Prompt 與正規化邏輯
"""
import sys, json, psycopg2, time
from psycopg2.extras import RealDictCursor

sys.path.insert(0, '/Users/jero/PredictX Sports/analysis')
from analysis_engine import AnalysisEngine

DB_CONFIG = {
    "dbname": "sports_db", "user": "jero",
    "password": "", "host": "localhost", "port": 5432
}

BATCH_START = int(sys.argv[1]) if len(sys.argv) > 1 else 0

# 查詢近 60 天所有比賽
conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor(cursor_factory=RealDictCursor)
cur.execute("""
    SELECT g.game_id::text, t.league
    FROM predictx.games g
    JOIN predictx.teams t ON g.home_team_id = t.team_id
    WHERE g.match_date >= CURRENT_DATE - INTERVAL '60 days'
    ORDER BY g.match_date DESC
""")
all_games = cur.fetchall()
cur.close()
conn.close()

pending = all_games[BATCH_START:]
print(f"Re-analyzing {len(pending)} games (starting from #{BATCH_START+1})...")

engine = AnalysisEngine()
success = 0
start_time = time.time()

for idx, game in enumerate(pending):
    game_id = game['game_id']
    league = game['league']
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
        
        elapsed = time.time() - start_time
        print(f"  [{BATCH_START+idx+1}/{len(all_games)}] ✓ {league:4s} | conf={result.get('confidence',0):.0f} | home_p={result.get('home_win_probability',0):.3f} ({elapsed:.0f}s)")
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"  [{BATCH_START+idx+1}/{len(all_games)}] ✗ {league:4s} {game_id[:8]}... Error: {e} ({elapsed:.0f}s)")

engine.close()
elapsed = time.time() - start_time
print(f"\nDone! {success}/{len(pending)} games in {elapsed:.0f}s")