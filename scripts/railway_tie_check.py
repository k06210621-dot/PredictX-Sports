#!/usr/bin/env python3
"""在 Railway 端查詢 7/12-7/13 平手場次 (簡化版)"""
import os, sys, json, psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

try:
    DB_URL = os.environ['DATABASE_URL']
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Verify connection
    cur.execute("SELECT current_database(), version();")
    db_info = cur.fetchone()
    sys.stderr.write(f"Connected: {db_info}\n")
    
    # Query games
    cur.execute("""
        SELECT 
            g.game_id::text,
            l.code AS league,
            ht.english_name AS home_team,
            at.english_name AS away_team,
            g.home_team_score,
            g.away_team_score,
            g.status,
            g.match_date::text
        FROM predictx.games g
        JOIN predictx.teams ht ON g.home_team_id = ht.team_id
        JOIN predictx.teams at ON g.away_team_id = at.team_id
        JOIN predictx.leagues l ON ht.league = l.code
        WHERE g.match_date IN ('2026-07-12', '2026-07-13')
        AND l.code IN ('MLB', 'NPB', 'CPBL')
        ORDER BY l.code, g.match_date, g.game_id
    """)
    
    all_rows = cur.fetchall()
    tie_rows = []
    
    for row in all_rows:
        hs = row['home_team_score']
        aws = row['away_team_score']
        if hs is not None and aws is not None and hs == aws:
            tie_rows.append(row)
    
    print(json.dumps({
        'total': len(all_rows),
        'tie_count': len(tie_rows),
        'all_games': [
            {
                'league': g['league'],
                'game_id': g['game_id'],
                'home': g['home_team'],
                'away': g['away_team'],
                'hs': round(float(g['home_team_score']), 1) if g['home_team_score'] else None,
                'aws': round(float(g['away_team_score']), 1) if g['away_team_score'] else None,
                'status': g['status'],
                'date': str(g['match_date']),
                'is_tie': bool(g['home_team_score'] == g['away_team_score'] if g['home_team_score'] is not None and g['away_team_score'] is not None else False)
            }
            for g in all_rows
        ],
        'tie_games': [
            {
                'league': g['league'],
                'game_id': g['game_id'],
                'home': g['home_team'],
                'away': g['away_team'],
                'score': f"{g['home_team_score']} - {g['away_team_score']}",
                'date': str(g['match_date'])
            }
            for g in tie_rows
        ]
    }, indent=2, ensure_ascii=False))
    
    cur.close()
    conn.close()
except Exception as e:
    print(json.dumps({'error': str(e)}))
    sys.exit(1)