import psycopg2
from psycopg2.extras import RealDictCursor

DB_CONFIG = {
    "dbname": "sports_db",
    "user": "jero",
    "password": "",
    "host": "localhost",
    "port": 5432
}

def test_query(target_date=None):
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    if target_date:
        query = """
            SELECT g.game_id 
            FROM predictx.games g
            LEFT JOIN predictx.game_analysis ga ON g.game_id = ga.game_id
            WHERE g.status = 'SCHEDULED' 
              AND g.match_date = %s
              AND (ga.analysis_id IS NULL OR ga.updated_at < NOW() - INTERVAL '12 hours')
        """
        cur.execute(query, (target_date,))
    else:
        query = """
            SELECT g.game_id 
            FROM predictx.games g
            LEFT JOIN predictx.game_analysis ga ON g.game_id = ga.game_id
            WHERE g.status = 'SCHEDULED' 
              AND g.match_date = CURRENT_DATE
              AND (ga.analysis_id IS NULL OR ga.updated_at < NOW() - INTERVAL '12 hours')
        """
        cur.execute(query)
    
    results = cur.fetchall()
    print(f"Found {len(results)} games to analyze for target_date={target_date}")
    for row in results:
        print(f"  Game ID: {row['game_id']}")
    
    cur.close()
    conn.close()
    return results

if __name__ == "__main__":
    print("Testing for tomorrow (2026-06-09):")
    test_query("2026-06-09")
    
    print("\nTesting for today (2026-06-08):")
    test_query("2026-06-08")
    
    print("\nTesting for default (no date):")
    test_query()