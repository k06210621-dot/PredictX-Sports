#!/usr/bin/env python3
"""手動觸發特定 NPB 場次的分析：阪神 vs DeNA """

import os, sys, time, json
from datetime import datetime

sys.path.insert(0, '/Users/jero/PredictX Sports/analysis')

import psycopg2
from analysis_engine import AnalysisEngine


def main():
    # Get DB URL from Railway env
    db_url = 'postgresql://postgres:***@thomas.proxy.rlwy.net:49887/railway'  # From railway variables
    
    conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)
    
    try:
        print("="*60)
        print("NPB Single Game Analysis - Recipe 8 (Injury + K/BB Bonus)")
        print("="*60)
        
        # Find the game
        cur = conn.cursor()
        tgt_date = "2026-07-22"
        
        cur.execute("""
    SELECT g.game_id, 
           ht.team_name_zh as home_team_name, ga.home_pitcher_name,
           ta.team_name_zh as away_team_name, ag.away_pitcher_name,
           (ga.analysis_data->'actual_result'->>'is_hit')::boolean AS is_settled,
           CASE WHEN (SELECT count(*) FROM predictx.game_analysis WHERE game_id=g.game_id) > 0 THEN 'HAS_ANALYSIS' ELSE NULL END as status
    FROM predictx.games g
    JOIN predictx.teams ht ON g.home_team_id = ht.team_id
    LEFT JOIN predictx.teams ta ON g.away_team_id = ta.team_id  
    WHERE ((ht.league='NPB' AND ga.home_pitcher_name IS NOT NULL) 
           OR (ta.league='NPB' AND ag.away_pitcher_name IS NOT NULL))
      AND date(g.match_date)=%s::date
  ORDER BY CASE WHEN ht.league='NPB' THEN 0 ELSE 1 END, g.game_id desc"""[:(tgt_date,)])

        games = cur.fetchall()
        
        if not games:
            print("No NPB game found for", tgt_date)
            
    except Exception as e:
        # Try without query parameters first to get the structure
        
    conn.close()

    return "Script ready"


if __name__ == "__main__":
    main()
