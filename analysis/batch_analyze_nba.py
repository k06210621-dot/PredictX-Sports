"""
批次分析最近 50 場 NBA 賽事
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import psycopg2
from psycopg2.extras import RealDictCursor
from analysis_engine import AnalysisEngine

DB_CONFIG = {
    "dbname": "sports_db", "user": "jero",
    "password": "", "host": "localhost", "port": 5432
}

def get_recent_nba_games(limit=50):
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT g.game_id::text, g.match_date,
               ht.english_name AS home_team, at.english_name AS away_team,
               g.home_team_score, g.away_team_score
        FROM predictx.games g
        JOIN predictx.teams ht ON g.home_team_id = ht.team_id
        JOIN predictx.teams at ON g.away_team_id = at.team_id
        WHERE ht.league = 'NBA'
          AND g.status = 'COMPLETED'
          AND g.game_id NOT IN (
              SELECT game_id FROM predictx.game_analysis
          )
        ORDER BY g.match_date DESC
        LIMIT %s
    """, (limit,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def save_analysis(conn, game_id, result):
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO predictx.game_analysis (game_id, analysis_data, updated_at)
            VALUES (%s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (game_id) 
            DO UPDATE SET 
                analysis_data = EXCLUDED.analysis_data,
                updated_at = CURRENT_TIMESTAMP
        """, (game_id, json.dumps(result)))
        conn.commit()
        return True
    except Exception as e:
        print(f"    ❌ Save error: {e}")
        conn.rollback()
        return False
    finally:
        cur.close()

def main():
    games = get_recent_nba_games(50)
    print(f"📊 Found {len(games)} unanalyzed NBA games\n")
    
    if not games:
        print("✅ No games to analyze!")
        return
    
    engine = AnalysisEngine()
    conn = psycopg2.connect(**DB_CONFIG)
    
    success = 0
    for i, game in enumerate(games, 1):
        game_id = game['game_id']
        match_date = game['match_date']
        home = game['home_team']
        away = game['away_team']
        
        print(f"[{i}/{len(games)}] {match_date} — {home} vs {away}...", end=" ")
        
        try:
            result = engine.analyze_game(game_id)
            if result and save_analysis(conn, game_id, result):
                hp = result.get('home_prob', '?')
                conf = result.get('confidence', '?')
                print(f"✅ HP={hp}, Conf={conf}")
                success += 1
            else:
                print("❌ No result")
        except Exception as e:
            print(f"❌ Error: {e}")
    
    engine.close()
    conn.close()
    
    print(f"\n✅ Done! {success}/{len(games)} games analyzed successfully.")

if __name__ == "__main__":
    main()
