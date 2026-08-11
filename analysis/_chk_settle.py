#!/usr/bin/env python3
"""查詢 7/12 MLB + WNBA 已完賽場次狀態（app = api_server Flask app，用其 DB 連線）。"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from api_server import app

with app.app_context():
    conn = app.config.get('db_conn')
    cur = conn.cursor()
    
    print("=== MLB 7/12 FINAL with missing settlement ===")
    cur.execute("""
        SELECT game_id::text, home_team, away_team,
               home_team_score, away_team_score,
               ai_is_hit, ai_predicted_score, ai_actual_score,
               status, match_date
        FROM predictx.games
        WHERE league='mlb' AND match_date='2026-07-12'
          AND status='FINAL'
          AND home_team_score IS NOT NULL
        ORDER BY game_id
    """)
    mlb = cur.fetchall()
    print(f"  Found {len(mlb)} FINAL games with score")
    for g in mlb:
        print(f"  {g['home_team']} vs {g['away_team']}  score={g['home_team_score']}-{g['away_team_score']}  ai_is_hit={g['ai_is_hit']}  ai_pred={g['ai_predicted_score']}  ai_act={g['ai_actual_score']}  game_id={g['game_id']}")
    
    print()
    print("=== WNBA 7/12 FINAL with missing settlement ===")
    cur.execute("""
        SELECT game_id::text, home_team, away_team,
               home_team_score, away_team_score,
               ai_is_hit, ai_predicted_score, ai_actual_score,
               status, match_date
        FROM predictx.games
        WHERE league='wnba' AND match_date='2026-07-12'
          AND status='FINAL'
          AND home_team_score IS NOT NULL
        ORDER BY game_id
    """)
    wnba = cur.fetchall()
    print(f"  Found {len(wnba)} FINAL games with score")
    for g in wnba:
        print(f"  {g['home_team']} vs {g['away_team']}  score={g['home_team_score']}-{g['away_team_score']}  ai_is_hit={g['ai_is_hit']}  ai_pred={g['ai_predicted_score']}  ai_act={g['ai_actual_score']}  game_id={g['game_id']}")
    
    cur.close()