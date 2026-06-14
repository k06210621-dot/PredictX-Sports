"""
PredictX Sports — NBA DataFetcher
使用 nba_api (stats.nba.com) 免費 API 取得即時進階數據
"""
import psycopg2
from psycopg2.extras import RealDictCursor

DB_CONFIG = {
    "dbname": "sports_db", "user": "jero",
    "password": "", "host": "localhost", "port": 5432
}

class NBADataFetcher:
    def __init__(self):
        self.conn = psycopg2.connect(**DB_CONFIG)
        self.cur = self.conn.cursor(cursor_factory=RealDictCursor)
        self.fetched_sources = []

    def get_local_team_id(self, team_name):
        """查詢本地資料庫的 NBA 隊伍 ID"""
        self.cur.execute(
            "SELECT team_id, english_name FROM predictx.teams WHERE english_name ILIKE %s AND league='NBA'",
            (f'%{team_name.split()[-1]}%',)
        )
        row = self.cur.fetchone()
        if row:
            return row['team_id'], row['english_name']
        # 嘗試全名比對
        self.cur.execute(
            "SELECT team_id, english_name FROM predictx.teams WHERE english_name ILIKE %s AND league='NBA'",
            (f'%{team_name}%',)
        )
        row = self.cur.fetchone()
        if row:
            return row['team_id'], row['english_name']
        return None, None

    def fetch_all_team_advanced_stats(self):
        """透過 nba_api 取得全聯盟進階數據"""
        try:
            from nba_api.stats.endpoints import leaguedashteamstats
            adv = leaguedashteamstats.LeagueDashTeamStats(
                season='2025-26',
                measure_type_detailed_defense='Advanced',
                per_mode_detailed='PerGame'
            )
            df = adv.get_data_frames()[0]
            self.fetched_sources.append("stats.nba.com")
            
            stats_map = {}
            for _, row in df.iterrows():
                name = row.get('TEAM_NAME', '')
                stats_map[name] = {
                    'off_rtg': float(row.get('OFF_RATING', 0)),
                    'def_rtg': float(row.get('DEF_RATING', 0)),
                    'net_rating': float(row.get('NET_RATING', 0)),
                    'pace': float(row.get('PACE', 0)),
                    'efg_pct': float(row.get('EFG_PCT', 0)),
                    'ts_pct': float(row.get('TS_PCT', 0)),
                    'ast_pct': float(row.get('AST_PCT', 0)),
                    'reb_pct': float(row.get('REB_PCT', 0)),
                    'tov_pct': float(row.get('TOV_PCT', 0)),
                    'win_pct': float(row.get('W_PCT', 0)),
                    'pts': float(row.get('PTS', 0)),
                    'opp_pts': float(row.get('OPP_PTS', 0)),
                }
            self.fetched_sources.append("stats.nba.com")
            return stats_map
        except Exception as e:
            print(f"  ⚠ NBA API error: {e}")
            return {}

    def fetch_and_store_game_data(self, game_id, home_team_name, away_team_name):
        """為一場 NBA 比賽取得進階數據並存入資料庫"""
        all_stats = self.fetch_all_team_advanced_stats()
        if not all_stats:
            return None

        # 使用 nba_api 的隊伍資料輔助比對
        from nba_api.stats.static import teams
        nba_teams = teams.get_teams()
        
        def match_nba_team(local_name):
            """比對本地隊名與 NBA 官方隊名"""
            # 處理 Team_161061XXXX 格式
            import re
            id_match = re.search(r'161061(\d{4})', local_name)
            if id_match:
                from nba_api.stats.static import teams
                for t in teams.get_teams():
                    if str(t['id']).endswith(id_match.group(1)):
                        return t['full_name']
            # 直接比對
            if local_name in all_stats:
                return local_name
            # 用最後一個詞比對
            parts = local_name.split()[-1].lower()
            for key in all_stats:
                if parts in key.lower():
                    return key
            # 用 nba_api 官方名稱搜尋
            for t in nba_teams:
                tn = t['full_name']
                if parts in tn.lower():
                    return tn
            return None

        home_key = match_nba_team(home_team_name)
        away_key = match_nba_team(away_team_name)

        if not home_key or not away_key:
            print(f"  ⚠ Cannot match NBA teams: {home_team_name} / {away_team_name}")
            print(f"     Matched: home={home_key}, away={away_key}")
            return None

        home_stats = all_stats[home_key]
        away_stats = all_stats[away_key]

        # 存入資料庫
        self._store_team_stats(game_id, home_team_name, home_stats)
        self._store_team_stats(game_id, away_team_name, away_stats)

        return {
            "home_team_name": home_team_name,
            "away_team_name": away_team_name,
            "team_stats": {"home": home_stats, "away": away_stats},
            "sources": list(set(self.fetched_sources))
        }

    def _store_team_stats(self, game_id, team_name, stats):
        local_id, _ = self.get_local_team_id(team_name)
        if not local_id:
            print(f"  ⚠ Cannot find local team: {team_name}")
            return
        self.cur.execute("""
            INSERT INTO predictx_advanced.nba_team_stats 
                (game_id, team_id, off_rtg, def_rtg, net_rating, pace,
                 efg_pct, ts_pct, ast_pct, reb_pct, tov_pct, win_pct, data_source)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'nba_api')
            ON CONFLICT (game_id, team_id) DO UPDATE SET
                off_rtg = EXCLUDED.off_rtg, def_rtg = EXCLUDED.def_rtg,
                net_rating = EXCLUDED.net_rating, pace = EXCLUDED.pace,
                efg_pct = EXCLUDED.efg_pct, ts_pct = EXCLUDED.ts_pct,
                win_pct = EXCLUDED.win_pct, fetched_at = CURRENT_TIMESTAMP
        """, (game_id, local_id, stats['off_rtg'], stats['def_rtg'],
              stats['net_rating'], stats['pace'], stats['efg_pct'],
              stats['ts_pct'], stats['ast_pct'], stats['reb_pct'],
              stats['tov_pct'], stats['win_pct']))
        self.conn.commit()

    def close(self):
        self.cur.close()
        self.conn.close()