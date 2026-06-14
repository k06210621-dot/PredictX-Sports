"""
NBA 賽程匯入腳本
從 nba_api (stats.nba.com) 取得 2025-26 賽季所有比賽，寫入 predictx.games
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

DB_CONFIG = {
    "dbname": "sports_db", "user": "jero",
    "password": "", "host": "localhost", "port": 5432
}

# nba_api 縮寫 → 本地資料庫 english_name 對照
NBA_TEAM_MAP = {
    "ATL": "Atlanta Hawks",
    "BOS": "Boston Celtics",
    "BKN": "Brooklyn Nets",
    "CHA": "Charlotte Hornets",
    "CHI": "Chicago Bulls",
    "CLE": "Cleveland Cavaliers",
    "DAL": "Dallas Mavericks",
    "DEN": "Denver Nuggets",
    "DET": "Detroit Pistons",
    "GSW": "Golden State Warriors",
    "HOU": "Houston Rockets",
    "IND": "Indiana Pacers",
    "LAC": "Los Angeles Clippers",
    "LAL": "Los Angeles Lakers",
    "MEM": "Memphis Grizzlies",
    "MIA": "Miami Heat",
    "MIL": "Milwaukee Bucks",
    "MIN": "Minnesota Timberwolves",
    "NOP": "New Orleans Pelicans",
    "NYK": "New York Knicks",
    "OKC": "Oklahoma City Thunder",
    "ORL": "Orlando Magic",
    "PHI": "Philadelphia 76ers",
    "PHX": "Phoenix Suns",
    "POR": "Portland Trail Blazers",
    "SAC": "Sacramento Kings",
    "SAS": "San Antonio Spurs",
    "TOR": "Toronto Raptors",
    "UTA": "Utah Jazz",
    "WAS": "Washington Wizards",
}

def get_league_id():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT league_id FROM predictx.leagues WHERE code = 'NBA'")
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row['league_id'] if row else None

def get_team_map(conn):
    """建立 english_name → (team_id, team_code) 對照"""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT team_id, english_name, team_code FROM predictx.teams WHERE league = 'NBA'")
    rows = cur.fetchall()
    cur.close()
    return {r['english_name']: (r['team_id'], r['team_code']) for r in rows}

def import_nba_schedule():
    from nba_api.stats.endpoints import leaguegamefinder
    import pandas as pd
    
    league_id = get_league_id()
    if not league_id:
        print("❌ Cannot find NBA league in database")
        return
    
    print(f"📡 Fetching NBA 2025-26 schedule from stats.nba.com...")
    finder = leaguegamefinder.LeagueGameFinder(season_nullable='2025-26', league_id_nullable='00')
    df = finder.get_data_frames()[0]
    
    # 取主隊視角的記錄（MATCHUP 含 "vs."）
    home_games = df[df['MATCHUP'].str.contains('vs.', na=False)].copy()
    print(f"📊 Total games found: {len(home_games)}")
    
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    team_map = get_team_map(conn)
    
    # 檢查缺少的隊伍
    missing_teams = set()
    for _, row in home_games.iterrows():
        matchup = row['MATCHUP']
        parts = matchup.split(' vs. ')
        if len(parts) != 2:
            continue
        home_abbr = parts[0].strip()
        away_abbr = parts[1].strip()
        
        home_name = NBA_TEAM_MAP.get(home_abbr)
        away_name = NBA_TEAM_MAP.get(away_abbr)
        
        if home_name and home_name not in team_map:
            missing_teams.add(f"{home_name} ({home_abbr})")
        if away_name and away_name not in team_map:
            missing_teams.add(f"{away_name} ({away_abbr})")
    
    if missing_teams:
        print(f"⚠️  Missing teams in DB: {', '.join(sorted(missing_teams))}")
        print("   These games will be skipped.")
    
    # 匯入賽程
    imported = 0
    skipped = 0
    errors = 0
    
    for _, row in home_games.iterrows():
        matchup = row['MATCHUP']
        parts = matchup.split(' vs. ')
        if len(parts) != 2:
            continue
        
        home_abbr = parts[0].strip()
        away_abbr = parts[1].strip()
        game_date = row['GAME_DATE']
        home_pts = row.get('PTS')
        away_pts = None  # 需要從另一筆記錄取得
        
        home_name = NBA_TEAM_MAP.get(home_abbr)
        away_name = NBA_TEAM_MAP.get(away_abbr)
        
        if not home_name or not away_name:
            skipped += 1
            continue
        
        home_info = team_map.get(home_name)
        away_info = team_map.get(away_name)
        
        if not home_info or not away_info:
            skipped += 1
            continue
        
        home_id = home_info[0]
        away_id = away_info[0]
        
        # 從 df 找客隊分數（同一場比賽客隊視角的 PTS）
        away_row = df[(df['GAME_ID'] == row['GAME_ID']) & (df['TEAM_ABBREVIATION'] == away_abbr)]
        if len(away_row) > 0:
            away_pts = away_row.iloc[0].get('PTS')
        
        # 判斷狀態
        if pd.notna(home_pts):
            status = 'COMPLETED'
        else:
            status = 'SCHEDULED'
        
        try:
            cur.execute("""
                INSERT INTO predictx.games 
                    (season, match_date, status, home_team_id, away_team_id, 
                     home_team_score, away_team_score, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                ON CONFLICT (season, match_date, home_team_id, away_team_id) 
                DO UPDATE SET
                    status = EXCLUDED.status,
                    home_team_score = EXCLUDED.home_team_score,
                    away_team_score = EXCLUDED.away_team_score,
                    updated_at = NOW()
            """, (2026, game_date, status, home_id, away_id,
                  float(home_pts) if pd.notna(home_pts) else None,
                  float(away_pts) if pd.notna(away_pts) else None))
            imported += 1
        except Exception as e:
            print(f"  ❌ Error importing {home_name} vs {away_name}: {e}")
            errors += 1
    
    conn.commit()
    cur.close()
    conn.close()
    
    print(f"\n✅ Import complete!")
    print(f"   Imported: {imported}")
    print(f"   Skipped (missing team): {skipped}")
    print(f"   Errors: {errors}")

if __name__ == "__main__":
    import_nba_schedule()
