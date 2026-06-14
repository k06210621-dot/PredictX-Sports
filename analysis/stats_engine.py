
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
import json

DB_CONFIG = {
    "dbname": "sports_db",
    "user": "jero",
    "password": "",
    "host": "localhost",
    "port": 5432
}

class StatsEngine:
    def __init__(self):
        self.conn = psycopg2.connect(**DB_CONFIG)
        self.cur = self.conn.cursor(cursor_factory=RealDictCursor)

    def get_overall_hit_rates(self):
        """
        Calculate hit rate per league.
        """
        # We use JSONB extraction to count hits
        query = """
            SELECT 
                t.league,
                COUNT(*) as total_analyzed,
                COUNT(*) FILTER (WHERE (ga.analysis_data->'actual_result'->>'is_hit')::boolean = true) as total_hits,
                ROUND(
                    (COUNT(*) FILTER (WHERE (ga.analysis_data->'actual_result'->>'is_hit')::boolean = true))::numeric / 
                    NULLIF(COUNT(*), 0), 3
                ) as hit_rate
            FROM predictx.game_analysis ga
            JOIN predictx.games g ON ga.game_id = g.game_id
            JOIN predictx.teams t ON g.home_team_id = t.team_id
            WHERE ga.analysis_data->'actual_result' IS NOT NULL
            GROUP BY t.league
        """
        self_cur = self.conn.cursor(cursor_factory=RealDictCursor)
        self_cur.execute(query)
        results = self_cur.fetchall()
        self_cur.close()
        return results

    def get_hit_rate_trend(self, league=None, limit=50):
        """
        Get hit rate trend by day for the last N games.
        """
        # Subquery to get the last N analyzed games that are settled
        # Then group them by date to calculate daily hit rate.
        
        league_filter = "AND t.league = %s" if league else ""
        params = [league] if league else []
        
        query = f"""
            WITH recent_games AS (
                SELECT 
                    g.match_date,
                    (ga.analysis_data->'actual_result'->>'is_hit')::boolean as is_hit
                FROM predictx.game_analysis ga
                JOIN predictx.games g ON ga.game_id = g.game_id
                JOIN predictx.teams t ON g.home_team_id = t.team_id
                WHERE ga.analysis_data->'actual_result' IS NOT NULL
                {league_filter}
                ORDER BY g.match_date DESC
                LIMIT %s
            )
            SELECT 
                match_date as date,
                COUNT(*) as games_count,
                ROUND(
                    (COUNT(*) FILTER (WHERE is_hit = true))::numeric / 
                    NULLIF(COUNT(*), 0), 3
                ) as daily_hit_rate
            FROM recent_games
            GROUP BY match_date
            ORDER BY match_date ASC
        """
        
        self_cur = self.conn.cursor(cursor_factory=RealDictCursor)
        self_cur.execute(query, params + [limit])
        results = self_cur.fetchall()
        self_cur.close()
        
        # Convert date objects to strings for JSON serialization
        for r in results:
            if isinstance(r['date'], (datetime,)):
                r['date'] = r['date'].strftime('%Y-%m-%d')
            elif hasattr(r['date'], 'strftime'):
                r['date'] = r['date'].strftime('%Y-%m-%d')
                
        return results

    def close(self):
        self.conn.close()

if __name__ == "__main__":
    # Simple test run
    engine = StatsEngine()
    print("--- League Hit Rates ---")
    print(engine.get_overall_hit_rates())
    print("\n--- Trend (Overall, last 50) ---")
    print(engine.get_hit_rate_trend())
    engine.close()
