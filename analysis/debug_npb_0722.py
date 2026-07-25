#!/usr/bin/env python3
import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

# Setup
sys.path.insert(0, '/Users/jero/PredictX Sports/analysis')

# Read PG credentials from temp file (written by railway variable list)
import json
with open('/tmp/railway_pg.json') as f:
    pg = json.load(f)
PGPW = pg['PGPASSWORD']

# Construct proxy DB URL
DB_URL = f"postgresql://postgres:{PGPW}@thomas.proxy.rlwy.net:49887/railway"

# Set LLM env
os.environ['CLOUD_LLM_PROVIDER'] = 'nvidia'
os.environ['CLOUD_LLM_MODEL'] = 'minimaxai/minimax-m3'
os.environ['CLOUD_LLM_URL'] = 'https://integrate.api.nvidia.com/v1/chat/completions'

def main():
    print(f"Connecting to DB (proxy)...")
    conn = psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)
    
    print("Searching for 阪神虎 vs 橫濱 DeNA 海灣之星 on 2026-07-22...")
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT g.game_id::text as game_id,
               ht.team_name_zh as home_team,
               ta.team_name_zh as away_team,
               g.home_pitcher_name,
               g.away_pitcher_name,
               g.match_date
        FROM predictx.games g
        JOIN predictx.teams ht ON g.home_team_id = ht.team_id
        JOIN predictx.teams ta ON g.away_team_id = ta.team_id
        WHERE ht.league = 'NPB' 
          AND ta.league = 'NPB'
          AND g.match_date = %s
          AND (ht.team_name_zh LIKE '%%虎%%' AND ta.team_name_zh LIKE '%%海灣%%'
               OR ht.team_name_zh LIKE '%%阪神%%' AND ta.team_name_zh LIKE '%%DeNA%%')
        LIMIT 1
    """, ('2026-07-22',))
    
    game = cur.fetchone()
    if not game:
        print("❌ Game not found! Checking all NPB games on 2026-07-22...")
        cur.execute("""
            SELECT ht.team_name_zh as home_team, 
                   ta.team_name_zh as away_team,
                   g.home_pitcher_name,
                   g.away_pitcher_name,
                   g.game_id::text as game_id
            FROM predictx.games g
            JOIN predictx.teams ht ON g.home_team_id = ht.team_id
            JOIN predictx.teams ta ON g.away_team_id = ta.team_id
            WHERE ht.league = 'NPB' 
              AND g.match_date = %s
            ORDER BY g.game_id
        """, ('2026-07-22',))
        games = cur.fetchall()
        if games:
            print(f"Found {len(games)} NPB games on 2026-07-22:")
            for g in games:
                print(f"  - {g['home_team']} vs {g['away_team']} (ID: {g['game_id'][:8]}...)")
        else:
            print("No NPB games found on 2026-07-22")
        cur.close()
        conn.close()
        return
    
    print(f"✅ Found: {game['home_team']} vs {game['away_team']}")
    print(f"   Game ID: {game['game_id']}")
    print(f"   Date: {game['match_date']}")
    print(f"   Home Pitcher: {game['home_pitcher_name'] or 'TBD'}")
    print(f"   Away Pitcher: {game['away_pitcher_name'] or 'TBD'}")
    
    print("\n🤖 Initializing Analysis Engine...")
    from analysis_engine import AnalysisEngine
    engine = AnalysisEngine(conn=conn)
    
    print(f"🔍 Analyzing game {game['game_id'][:8]}... (using minimax-m3)")
    try:
        result = engine.analyze_game(game['game_id'])
        
        if result:
            print("\n" + "="*60)
            print("📊 ANALYSIS COMPLETE")
            print("="*60)
            
            home_prob = result.get('home_win_probability', 0)
            away_prob = result.get('away_win_probability', 0)
            confidence = result.get('confidence', 0)
            
            print(f"預測勝率 - 主隊: {home_prob:.1%} | 客隊: {away_prob:.1%}")
            print(f"信心度: {confidence}/10")
            
            pred_score = result.get('predicted_score', 'N/A')
            print(f"預測比分: {pred_score}")
            
            summary = result.get('summary', '')
            if summary:
                print(f"\n📝 分析摘要:")
                print(summary if len(summary) <= 400 else summary[:400] + "...")
            
            key_factors = result.get('key_factors', [])
            if key_factors:
                print(f"\n🔑 關鍵因素:")
                if isinstance(key_factors, list):
                    for i, factor in enumerate(key_factors[:5], 1):
                        print(f"  {i}. {factor}")
                else:
                    print(f"  {key_factors}")
            
            radar = result.get('radar_chart', {})
            if radar:
                print(f"\n📈 雷達圖 (六維特徵):")
                for k, v in radar.items():
                    if isinstance(v, (int, float)):
                        print(f"  {k}: {v:.2f}")
                    else:
                        print(f"  {k}: {v}")
            
            if '[傷兵校正]' in summary:
                print(f"\n✅ 偵測到傷兵調整 (Recipe 8) 已應用")
            if '[投手參數校正]' in summary:
                print(f"✅ 偵測到投手參數校正 (Recipe 6) 已應用")
                
            print("\n" + "="*60)
            print("✅ Analysis finished successfully")
        else:
            print("❌ Analysis returned no result")
            
    except Exception as e:
        print(f"❌ Error during analysis: {e}")
        import traceback
        traceback.print_exc()
    finally:
        engine.close()
        cur.close()
        conn.close()

if __name__ == '__main__':
    main()