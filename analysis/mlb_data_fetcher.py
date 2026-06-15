"""
PredictX Sports — 可上網的 MLB 資料收集器
使用免費 MLB Stats API + ESPN scraping
"""
import requests
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
import os

DB_CONFIG = {
    "dbname": "sports_db", "user": "jero",
    "password": "", "host": "localhost", "port": 5432
}

MLB_API_BASE = "https://statsapi.mlb.com/api/v1"

class MLBDataFetcher:
    def __init__(self, conn=None):
        if conn:
            self.conn = conn
            self.cur = conn.cursor(cursor_factory=RealDictCursor)
        else:
            database_url = os.getenv('DATABASE_URL')
            if database_url:
                if database_url.startswith('postgres://'):
                    database_url = database_url.replace('postgres://', 'postgresql://', 1)
                self.conn = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
            else:
                self.conn = psycopg2.connect(**DB_CONFIG)
            self.cur = self.conn.cursor(cursor_factory=RealDictCursor)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "PredictX-Sports/1.0"})
        self.fetched_sources = []

    def get_mlb_team_id_by_name(self, team_name):
        """透過 MLB API 查詢 MLB 官方 team ID"""
        url = f"{MLB_API_BASE}/teams?sportId=1&season=2026"
        resp = self.session.get(url, timeout=10)
        if resp.status_code != 200:
            return None
        data = resp.json()
        for team in data.get('teams', []):
            if team_name.lower() in team.get('name', '').lower():
                self.fetched_sources.append("statsapi.mlb.com")
                return team['id']
            if team_name.lower() in team.get('teamName', '').lower():
                self.fetched_sources.append("statsapi.mlb.com")
                return team['id']
            if team_name.lower() in team.get('shortName', '').lower():
                self.fetched_sources.append("statsapi.mlb.com")
                return team['id']
        return None

    def get_team_season_stats(self, mlb_team_id):
        """取得 MLB 團隊整季打擊/投球數據"""
        result = {}
        for group in ['hitting', 'pitching']:
            url = f"{MLB_API_BASE}/teams/{mlb_team_id}/stats?season=2026&stats=season&group={group}"
            resp = self.session.get(url, timeout=15)
            if resp.status_code != 200:
                continue
            data = resp.json()
            stats_list = data.get('stats', [])
            if stats_list:
                splits = stats_list[0].get('splits', [])
                if splits:
                    stat_dict = splits[0].get('stat', {})
                    for k, v in stat_dict.items():
                        if isinstance(v, (int, float)):
                            result[f"{group}_{k}"] = v
        self.fetched_sources.append("statsapi.mlb.com")
        return result

    def get_team_recent_games(self, mlb_team_id, limit=10):
        """取得 MLB 隊伍最近 N 場比賽比分"""
        url = f"{MLB_API_BASE}/schedule?teamId={mlb_team_id}&season=2026&sportId=1"
        resp = self.session.get(url, timeout=10)
        if resp.status_code != 200:
            return None
        
        data = resp.json()
        self.fetched_sources.append("statsapi.mlb.com")
        games = []
        for date_entry in data.get('dates', []):
            for game in date_entry.get('games', []):
                home_team = game['teams']['home']['team']['name']
                away_team = game['teams']['away']['team']['name']
                status = game['status']['detailedState']
                home_score = game['teams']['home'].get('score')
                away_score = game['teams']['away'].get('score')
                is_home = (mlb_team_id == game['teams']['home']['team']['id'])
                
                games.append({
                    'date': date_entry['date'],
                    'opponent': away_team if is_home else home_team,
                    'is_home': is_home,
                    'home_score': home_score,
                    'away_score': away_score,
                    'result': 'W' if (home_score and away_score and 
                        ((is_home and home_score > away_score) or 
                         (not is_home and away_score > home_score))) else 'L' if (home_score and away_score) else '?',
                    'status': status
                })
        
        return games[:limit]

    def get_pitcher_stats(self, mlb_team_id):
        """取得 MLB 投手群數據"""
        url = f"{MLB_API_BASE}/teams/{mlb_team_id}/roster?season=2026"
        resp = self.session.get(url, timeout=10)
        if resp.status_code != 200:
            return None
        
        data = resp.json()
        self.fetched_sources.append("statsapi.mlb.com")
        pitchers = []
        for roster_entry in data.get('roster', []):
            person = roster_entry.get('person', {})
            pos = roster_entry.get('position', {}).get('abbreviation', '')
            if pos in ('P', 'SP', 'RP'):
                pitchers.append({
                    'id': person.get('id'),
                    'name': person.get('fullName', ''),
                    'position': pos
                })
        return pitchers

    def get_probable_pitcher_data(self, game_id, home_team_name, away_team_name):
        """透過 MLB Schedule API + probablePitcher 取得先發投手資料並存入資料庫"""
        try:
            # 1. 查詢比賽日期
            self.cur.execute("SELECT match_date FROM predictx.games WHERE game_id = %s", (game_id,))
            row = self.cur.fetchone()
            if not row:
                return None
            match_date = row['match_date'].strftime('%Y-%m-%d')
            
            # 2. 取得先發投手 ID
            url = f"{MLB_API_BASE}/schedule?sportId=1&date={match_date}&hydrate=probablePitcher"
            resp = self.session.get(url, timeout=10)
            if resp.status_code != 200:
                return None
            
            data = resp.json()
            self.fetched_sources.append("statsapi.mlb.com")
            
            home_pitcher = None
            away_pitcher = None
            
            for date_entry in data.get('dates', []):
                for game in date_entry.get('games', []):
                    g_home = game['teams']['home']['team']['name']
                    g_away = game['teams']['away']['team']['name']
                    
                    if home_team_name.lower() in g_home.lower() and away_team_name.lower() in g_away.lower():
                        h_p = game['teams']['home'].get('probablePitcher', {})
                        a_p = game['teams']['away'].get('probablePitcher', {})
                        home_pitcher = {'id': h_p.get('id'), 'name': h_p.get('fullName', 'TBD')} if h_p else None
                        away_pitcher = {'id': a_p.get('id'), 'name': a_p.get('fullName', 'TBD')} if a_p else None
                        break
            
            result = {'home_pitcher': {'name': 'TBD'}, 'away_pitcher': {'name': 'TBD'}}
            
            for side, pitcher, team_name, mlb_fn in [
                ('home', home_pitcher, home_team_name, self.get_mlb_team_id_by_name),
                ('away', away_pitcher, away_team_name, self.get_mlb_team_id_by_name),
            ]:
                mlb_id = mlb_fn(team_name)
                if not pitcher or not pitcher.get('id'):
                    continue
                
                pid = pitcher['id']
                pname = pitcher['name']
                
                # 3. 取得投手個人整季數據
                stats_url = f"{MLB_API_BASE}/people/{pid}/stats?stats=season&season=2026&group=pitching"
                stats_resp = self.session.get(stats_url, timeout=10)
                pitcher_stats = {}
                
                if stats_resp.status_code == 200:
                    pdata = stats_resp.json()
                    splits = pdata.get('stats', [{}])[0].get('splits', [{}])
                    if splits:
                        s = splits[0].get('stat', {})
                        er = s.get('earnedRuns', 0) or 0
                        outs = s.get('outs', 0) or 0
                        ip = outs / 3
                        h = s.get('hits', 0) or 0
                        bb = s.get('baseOnBalls', 0) or 0
                        k = s.get('strikeOuts', 0) or 0
                        hr = s.get('homeRuns', 0) or 0
                        bf = s.get('battersFaced', 0) or 0
                        games = s.get('gamesPlayed', 0) or 0
                        
                        pitcher_stats = {
                            'era': round(er * 9 / ip, 2) if ip > 0 else 0,
                            'whip': round((bb + h) / ip, 3) if ip > 0 else 0,
                            'k_per_9': round(k * 9 / ip, 1) if ip > 0 else 0,
                            'bb_per_9': round(bb * 9 / ip, 1) if ip > 0 else 0,
                            'hr_per_9': round(hr * 9 / ip, 1) if ip > 0 else 0,
                            'avg': round(h / (bf - bb), 3) if (bf - bb) > 0 else 0,
                            'k_bb_ratio': round(k / bb, 2) if bb > 0 else k,
                            'games': games,
                            'ip': round(ip, 1),
                        }
                        self.fetched_sources.append("statsapi.mlb.com")
                
                result[f'{side}_pitcher'] = {'name': pname, 'id': pid, 'stats': pitcher_stats}
                
                # 4. 存入資料庫
                local_id, _ = self.get_local_team_id(team_name)
                if local_id and pitcher_stats:
                    self.cur.execute("""
                        INSERT INTO predictx_advanced.mlb_pitcher_stats 
                            (game_id, team_id, pitcher_name, era, whip, k_per_9, bb_per_9)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (game_id, team_id, pitcher_name) 
                        DO UPDATE SET 
                            era = EXCLUDED.era, whip = EXCLUDED.whip,
                            k_per_9 = EXCLUDED.k_per_9, bb_per_9 = EXCLUDED.bb_per_9,
                            fetched_at = CURRENT_TIMESTAMP
                    """, (game_id, local_id, pname,
                          pitcher_stats.get('era'), pitcher_stats.get('whip'),
                          pitcher_stats.get('k_per_9'), pitcher_stats.get('bb_per_9')))
                    self.conn.commit()
            
            return result
        except Exception as e:
            print(f"  ⚠ Pitcher fetch error: {e}")
            return None

    def get_local_team_id(self, team_name):
        """查詢本地資料庫的 MLB team_id"""
        self.cur.execute(
            "SELECT team_id, english_name FROM predictx.teams WHERE english_name ILIKE %s AND league='MLB'",
            (f'%{team_name.split()[-1]}%',)
        )
        row = self.cur.fetchone()
        return (row['team_id'], row['english_name']) if row else (None, None)

    def fetch_and_store_game_data(self, game_id, home_team_name, away_team_name):
        """為一場比賽獲取完整 MLB 進階數據並存入資料庫"""
        today = datetime.now()
        
        home_mlb_id = self.get_mlb_team_id_by_name(home_team_name)
        away_mlb_id = self.get_mlb_team_id_by_name(away_team_name)
        
        if not home_mlb_id or not away_mlb_id:
            print(f"  Cannot find MLB IDs for {home_team_name} or {away_team_name}")
            return None

        # 取得團隊整季數據
        home_stats = self.get_team_season_stats(home_mlb_id)
        away_stats = self.get_team_season_stats(away_mlb_id)

        data = {
            "home_team_name": home_team_name,
            "away_team_name": away_team_name,
            "home_mlb_id": home_mlb_id,
            "away_mlb_id": away_mlb_id,
            "team_stats": {
                "home": home_stats or {},
                "away": away_stats or {}
            },
            "fetched_at": today.isoformat(),
            "sources": list(set(self.fetched_sources))
        }

        # 存入資料庫
        self._store_team_stats(game_id, home_team_name, home_stats, home_mlb_id)
        self._store_team_stats(game_id, away_team_name, away_stats, away_mlb_id)
        
        return data

    def _store_team_stats(self, game_id, team_name, stats, mlb_team_id):
        if not stats:
            return
        
        # 對應本地 team_id
        self.cur.execute("SELECT team_id FROM predictx.teams WHERE english_name ILIKE %s AND league='MLB'", (f'%{team_name.split()[-1]}%',))
        local_team = self.cur.fetchone()
        if not local_team:
            print(f"  Cannot find local team for {team_name}")
            return
        team_id = local_team['team_id']
        
        # 提取關鍵數據
        ops = stats.get('hitting_ops')
        obp = stats.get('hitting_obp')
        slg = stats.get('hitting_slg')
        era = stats.get('pitching_era')
        whip = stats.get('pitching_whip')
        k9 = stats.get('pitching_strikeoutsPer9Inn')
        bb9 = stats.get('pitching_walksPer9Inn')
        
        # 寫入 mlb_team_stats
        try:
            self.cur.execute("""
                INSERT INTO predictx_advanced.mlb_team_stats 
                    (game_id, team_id, team_ops, team_obp, team_slg, bullpen_era, data_source, fetched_at)
                VALUES (%s, %s, %s, %s, %s, %s, 'statsapi.mlb.com', CURRENT_TIMESTAMP)
                ON CONFLICT (game_id, team_id) 
                DO UPDATE SET 
                    team_ops = EXCLUDED.team_ops,
                    team_obp = EXCLUDED.team_obp,
                    team_slg = EXCLUDED.team_slg,
                    bullpen_era = EXCLUDED.bullpen_era,
                    fetched_at = CURRENT_TIMESTAMP
            """, (game_id, team_id, ops, obp, slg, era))
            self.conn.commit()
        except Exception as e:
            print(f"  ⚠ Store team stats error: {e}")
            self.conn.rollback()

    def close(self):
        self.cur.close()
        self.conn.close()