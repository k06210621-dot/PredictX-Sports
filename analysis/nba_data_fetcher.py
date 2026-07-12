"""
PredictX Sports — NBA DataFetcher
使用 nba_api (stats.nba.com) 免費 API 取得即時進階數據
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor

DB_CONFIG = {
    "dbname": "sports_db", "user": "jero",
    "password": "", "host": "localhost", "port": 5432
}

class NBADataFetcher:
    def __init__(self, conn=None):
        """若 conn=None，自己建 DB 連線；若 conn 外部傳入，使用外部 conn（close() 不會關閉）"""
        self.conn = None
        self.cur = None
        self._conn_external = False
        if conn:
            self.conn = conn
            self.cur = conn.cursor(cursor_factory=RealDictCursor)
            self._conn_external = True
        else:
            try:
                database_url = os.getenv('DATABASE_URL')
                if database_url:
                    if database_url.startswith('postgres://'):
                        database_url = database_url.replace('postgres://', 'postgresql://', 1)
                    self.conn = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
                else:
                    self.conn = psycopg2.connect(**DB_CONFIG)
                self.cur = self.conn.cursor(cursor_factory=RealDictCursor)
            except Exception:
                pass
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

    def get_top_players(self, team_name, top_n=5):
        """取得 NBA 指定球隊前 N 名球員（依 PTS 排序）

        Args:
            team_name: NBA 官方隊名（如 'Los Angeles Lakers'）
            top_n: 取前 N 名（預設 5）

        Returns:
            list of dict: [{name, pts, reb, ast, fg_pct, fg3_pct, games_played}, ...]
            若抓取失敗回傳空陣列
        """
        try:
            from nba_api.stats.endpoints import leaguedashplayerstats
            from nba_api.stats.static import teams
            
            # 先找到球隊 ID
            nba_teams = teams.get_teams()
            team_id = None
            for t in nba_teams:
                if team_name.lower() in t['full_name'].lower():
                    team_id = t['id']
                    break
            
            if not team_id:
                return []
            
            # 抓取球員數據（只抓指定球隊）
            players = leaguedashplayerstats.LeagueDashPlayerStats(
                season='2025-26',
                team_id_nullable=team_id,
                per_mode_detailed='PerGame'
            )
            
            df = players.get_data_frames()[0]
            self.fetched_sources.append("stats.nba.com")
            
            result = []
            for _, row in df.iterrows():
                player_name = row.get('PLAYER_NAME', '')
                pts = float(row.get('PTS', 0) or 0)
                reb = float(row.get('REB', 0) or 0)
                ast = float(row.get('AST', 0) or 0)
                fg_pct = float(row.get('FG_PCT', 0) or 0)
                fg3_pct = float(row.get('FG3_PCT', 0) or 0)
                games_played = int(row.get('GP', 0) or 0)
                
                result.append({
                    'name': player_name,
                    'position': row.get('POSITION', ''),  # 可能為空
                    'pts': round(pts, 1),
                    'reb': round(reb, 1),
                    'ast': round(ast, 1),
                    'fg_pct': round(fg_pct, 3) if fg_pct > 0 else None,
                    'fg3_pct': round(fg3_pct, 3) if fg3_pct > 0 else None,
                    'games_played': games_played,
                })
            
            # 依 PTS 排序（降冪）
            result.sort(key=lambda x: x['pts'], reverse=True)
            
            return result[:top_n]
            
        except Exception as e:
            print(f"  ⚠ NBA get_top_players error: {e}")
            return []

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

        # 🆕 主力球員數據（前 5 名得分手）
        home_top5 = self.get_top_players(home_key, top_n=5) or []
        away_top5 = self.get_top_players(away_key, top_n=5) or []

        # 存入資料庫
        self._store_team_stats(game_id, home_team_name, home_stats)
        self._store_team_stats(game_id, away_team_name, away_stats)

        return {
            "home_team_name": home_team_name,
            "away_team_name": away_team_name,
            "team_stats": {"home": home_stats, "away": away_stats},
            "top_players": {"home": home_top5, "away": away_top5},  # 🆕 新增
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
        """關閉 fetcher 持有的資源。

        若 conn 是外部傳入（共用），不關閉 conn（conn 由 pool 管理），
        只關閉 fetcher 內部的 cursor 以免污染呼叫端的 cursor。
        """
        self._conn_external = getattr(self, '_conn_external', False)
        if not self._conn_external:
            try:
                if self.cur:
                    self.cur.close()
            except Exception:
                pass
            try:
                if self.conn:
                    self.conn.close()
            except Exception:
                pass