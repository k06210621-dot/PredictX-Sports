import os
import json
import time
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
import requests

# --- 配置區 ---
DB_CONFIG = {
    "dbname": "sports_db",
    "user": "jero",
    "password": "",
    "host": "localhost",
    "port": 5432
}

MODEL_CONFIGS = {
    "qwen3.5:9b": {"model": "qwen3.5:9b", "timeout": 120, "num_predict": 512},
    "qwen:latest": {"model": "qwen:latest", "timeout": 60, "num_predict": 4096},
}

OLLAMA_URL = "http://localhost:11434/api/generate"

# --- 雲端 LLM 配置（支援 NVIDIA / OpenRouter / Groq / Ollama Cloud）---
CLOUD_LLM_PROVIDER = os.environ.get("CLOUD_LLM_PROVIDER", "nvidia")

if CLOUD_LLM_PROVIDER == "openrouter":
    CLOUD_LLM_URL = "https://openrouter.ai/api/v1/chat/completions"
    CLOUD_LLM_MODEL = os.environ.get("CLOUD_LLM_MODEL", "meta-llama/llama-3.3-70b-instruct:free")
    CLOUD_LLM_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
elif CLOUD_LLM_PROVIDER == "groq":
    CLOUD_LLM_URL = "https://api.groq.com/openai/v1/chat/completions"
    CLOUD_LLM_MODEL = os.environ.get("CLOUD_LLM_MODEL", "llama-3.3-70b-versatile")
    CLOUD_LLM_API_KEY = os.environ.get("GROQ_API_KEY", "")
elif CLOUD_LLM_PROVIDER == "ollama":
    CLOUD_LLM_URL = "https://api.ollama.com/api/chat"
    CLOUD_LLM_MODEL = os.environ.get("CLOUD_LLM_MODEL", "deepseek-v4-flash")
    CLOUD_LLM_API_KEY = os.environ.get("OLLAMA_API_KEY", "")
else:
    CLOUD_LLM_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
    CLOUD_LLM_MODEL = "deepseek-ai/deepseek-v4-flash"
    CLOUD_LLM_API_KEY = os.environ.get("NVIDIA_API_KEY", "")

# 備援 LLM 配置（當主要 LLM 失敗時使用）
FALLBACK_LLM_URL = "https://api.ollama.com/api/chat"
FALLBACK_LLM_MODEL = "deepseek-v4-flash"
FALLBACK_LLM_API_KEY = os.environ.get("OLLAMA_API_KEY", "")

# 可透過環境變數 PREDICTX_MODEL 切換模型
# qwen:latest (4B, ~6s/場) | qwen3.5:9b (9B, ~200s/場，預設) | cloud (雲端 LLM)
MODEL_NAME = os.environ.get("PREDICTX_MODEL", "qwen3.5:9b")
USE_CLOUD = MODEL_NAME == "cloud"

class AnalysisEngine:
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
        self.source_registry = {
            "official_api": 5.0,
            "sports_data_platform": 4.0,
            "news_media": 3.0,
            "social_community": 1.0
        }
        self.used_sources = []

    def log_source(self, source_type):
        if source_type in self.source_registry:
            self.used_sources.append(source_type)

    def calculate_source_score(self):
        if not self.used_sources:
            return 0.0
        scores = [self.source_registry[s] for s in self.used_sources]
        return round(sum(scores) / len(scores), 2)

    def _reconcile_predicted_score(self, predicted_score, home_prob, away_prob, league=""):
        """
        校正 predicted_score，確保與勝率一致。

        規則：
        - home_prob > away_prob → home 分數必須 > away 分數
        - away_prob > home_prob → away 分數必須 > home 分數
        - 勝率差距大 → 分數差距也應明顯（2-3 分以上）

        棒球/籃球典型比分範圍：1-12 分
        - 棒球：低分（1-9），強弱差距 1-3 分
        - 籃球：高分（80-130），強弱差距 5-15 分
        """
        import re

        # 不同聯盟的合理分數範圍
        score_ranges = {
            "MLB": (2, 9),    # 棒球單隊常見 2-9 分
            "NBA": (95, 135), # 籃球單隊常見 95-135 分
            "NPB": (2, 9),
            "CPBL": (2, 9),
        }
        lo, hi = score_ranges.get((league or "").upper(), (2, 9))

        # 解析 LLM 給的 predicted_score（如 "5-3"）
        original_score = None
        if predicted_score:
            m = re.search(r'(\d+)\s*[-－–]\s*(\d+)', str(predicted_score))
            if m:
                original_score = (int(m.group(1)), int(m.group(2)))

        # 決定誰是 favorite（勝率高者）
        prob_diff = abs(home_prob - away_prob)
        if prob_diff < 0.05:
            # 差距 < 5% 視為五五波，不校正（保留 LLM 原始預測）
            return predicted_score or f"{lo}-{lo}"

        home_favorite = home_prob > away_prob

        # 解析原比分為 (home, away)
        if original_score is None:
            # LLM 沒給有效比分，從範圍中位數開始
            mid = (lo + hi) // 2
            original_score = (mid, mid)
        h_score, a_score = original_score

        # 修正方向：favorite 必須贏
        if home_favorite and h_score <= a_score:
            # home 應該贏但沒贏 → 調高 home（如果太低則加 1），或調低 away
            if h_score == a_score:
                h_score = min(h_score + 1, hi)
            else:
                # 翻轉：max +1 → favorite, min → underdog
                new_fav = max(h_score, a_score) + 1
                new_und = min(h_score, a_score)
                if home_favorite:
                    h_score, a_score = new_fav, new_und
                else:
                    h_score, a_score = new_und, new_fav
        elif (not home_favorite) and a_score <= h_score:
            if h_score == a_score:
                a_score = min(a_score + 1, hi)
            else:
                new_fav = max(h_score, a_score) + 1
                new_und = min(h_score, a_score)
                if home_favorite:
                    h_score, a_score = new_fav, new_und
                else:
                    h_score, a_score = new_und, new_fav
        # 確保在範圍內
        h_score = max(lo, min(hi, h_score))
        a_score = max(lo, min(hi, a_score))

        # 差距加強（如果原本差距太小）
        favorite_score = h_score if home_favorite else a_score
        underdog_score = a_score if home_favorite else h_score
        if favorite_score - underdog_score < 1 and prob_diff > 0.1:
            underdog_score = max(lo, favorite_score - 2)
            if home_favorite:
                h_score, a_score = favorite_score, underdog_score
            else:
                h_score, a_score = underdog_score, favorite_score

        return f"{h_score}-{a_score}"

    def get_team_recent_form(self, team_id, league, limit=10):
        """
        獲取隊伍最近 N 場比賽的戰績與得失分
        分離主場/客場戰績以利 AI 預測（主場勝率棒球 ~54%、NBA ~60%）
        """
        query = """
            SELECT g.match_date, g.home_team_score, g.away_team_score, g.status,
                   ht.chinese_name as home_name, at.chinese_name as away_name,
                   CASE
                       WHEN g.home_team_id = %s THEN 'home'
                       ELSE 'away'
                   END as side,
                   g.game_id
            FROM predictx.games g
            JOIN predictx.teams ht ON g.home_team_id = ht.team_id
            JOIN predictx.teams at ON g.away_team_id = at.team_id
            WHERE (g.home_team_id = %s OR g.away_team_id = %s)
              AND g.status IN ('final', 'FINAL')
              AND g.home_team_score IS NOT NULL
              AND g.away_team_score IS NOT NULL
            ORDER BY g.match_date DESC
            LIMIT %s
        """
        self.cur.execute(query, (team_id, team_id, team_id, limit))
        self.log_source("official_api")
        games = self.cur.fetchall()

        results = []
        wins = 0
        total_goals_for = 0.0
        total_goals_against = 0.0

        # 主客場分離統計
        home_games = 0
        home_wins = 0
        home_goals_for = 0.0
        home_goals_against = 0.0
        away_games = 0
        away_wins = 0
        away_goals_for = 0.0
        away_goals_against = 0.0

        for g in games:
            if g['side'] == 'home':
                gf = g['home_team_score']
                ga = g['away_team_score']
            else:
                gf = g['away_team_score']
                ga = g['home_team_score']

            total_goals_for += float(gf) if gf else 0
            total_goals_against += float(ga) if ga else 0

            is_win = False
            if gf is not None and ga is not None:
                if float(gf) > float(ga):
                    result = "W"
                    wins += 1
                    is_win = True
                elif float(gf) < float(ga):
                    result = "L"
                else:
                    result = "D"
            else:
                result = "?"

            # 主客場分流累積
            if g['side'] == 'home':
                home_games += 1
                home_goals_for += float(gf) if gf else 0
                home_goals_against += float(ga) if ga else 0
                if is_win:
                    home_wins += 1
            else:
                away_games += 1
                away_goals_for += float(gf) if gf else 0
                away_goals_against += float(ga) if ga else 0
                if is_win:
                    away_wins += 1

            results.append({
                "date": str(g['match_date']),
                "opponent": g['away_name'] if g['side'] == 'home' else g['home_name'],
                "result": result,
                "score": f"{gf}-{ga}" if gf is not None and ga is not None else "N/A",
                "side": g['side']  # 🆕 標註主客場
            })

        return {
            "recent_games": results,
            "win_loss": f"{wins}-{len(results)-wins}",
            "win_rate": round(wins / len(results), 2) if results else 0,
            "avg_goals_for": round(total_goals_for / len(results), 1) if results else 0,
            "avg_goals_against": round(total_goals_against / len(results), 1) if results else 0,
            "goal_diff": round((total_goals_for - total_goals_against) / len(results), 1) if results else 0,
            # 🆕 主客場分離數據（讓 AI prompt 注入後能更精準預測）
            "home_record": {
                "games": home_games,
                "wins": home_wins,
                "losses": home_games - home_wins,
                "win_rate": round(home_wins / home_games, 2) if home_games else 0,
                "avg_for": round(home_goals_for / home_games, 1) if home_games else 0,
                "avg_against": round(home_goals_against / home_games, 1) if home_games else 0,
            },
            "away_record": {
                "games": away_games,
                "wins": away_wins,
                "losses": away_games - away_wins,
                "win_rate": round(away_wins / away_games, 2) if away_games else 0,
                "avg_for": round(away_goals_for / away_games, 1) if away_games else 0,
                "avg_against": round(away_goals_against / away_games, 1) if away_games else 0,
            },
        }

    def get_historical_matchup(self, home_team_id, away_team_id, recent_limit=5):
        """
        獲取兩隊對陣歷史 (從已結束的比賽中統計)
        - 總體 H2H 勝率
        - 最近 N 場對戰明細（含日期、比分、勝負）
        """
        query = """
            SELECT
                COUNT(*) as total_played,
                SUM(CASE WHEN g.home_team_id = %s AND g.home_team_score > g.away_team_score THEN 1 ELSE 0 END) as home_wins,
                SUM(CASE WHEN g.away_team_id = %s AND g.away_team_score > g.home_team_score THEN 1 ELSE 0 END) as away_wins,
                AVG(g.home_team_score)::numeric(5,2) as avg_home_score,
                AVG(g.away_team_score)::numeric(5,2) as avg_away_score
            FROM predictx.games g
            WHERE ((g.home_team_id = %s AND g.away_team_id = %s)
                OR (g.home_team_id = %s AND g.away_team_id = %s))
              AND g.status IN ('final', 'FINAL')
              AND g.home_team_score IS NOT NULL
        """
        self.cur.execute(query, (home_team_id, away_team_id, home_team_id, away_team_id, away_team_id, home_team_id))
        row = self.cur.fetchone()

        result = None
        if row and row['total_played'] and row['total_played'] > 0:
            result = {
                "total_played": row['total_played'],
                "home_wins": row['home_wins'] or 0,
                "away_wins": row['away_wins'] or 0,
                "avg_home_score": float(row['avg_home_score'] or 0) if row['avg_home_score'] else 0,
                "avg_away_score": float(row['avg_away_score'] or 0) if row['avg_away_score'] else 0,
                "home_win_rate": round((row['home_wins'] or 0) / row['total_played'], 2),
                "away_win_rate": round((row['away_wins'] or 0) / row['total_played'], 2),
                "recent_matchups": []  # 🆕 初始化
            }

        # 🆕 額外查詢最近 N 場對戰明細（即使無總體資料，也嘗試回傳 recent_matchups）
        recent_query = """
            SELECT
                g.match_date,
                g.home_team_id,
                g.away_team_id,
                g.home_team_score,
                g.away_team_score,
                th.english_name as home_en,
                ta.english_name as away_en
            FROM predictx.games g
            JOIN predictx.teams th ON g.home_team_id = th.team_id
            JOIN predictx.teams ta ON g.away_team_id = ta.team_id
            WHERE ((g.home_team_id = %s AND g.away_team_id = %s)
                OR (g.home_team_id = %s AND g.away_team_id = %s))
              AND g.status IN ('final', 'FINAL')
              AND g.home_team_score IS NOT NULL
              AND g.away_team_score IS NOT NULL
            ORDER BY g.match_date DESC
            LIMIT %s
        """
        self.cur.execute(recent_query, (home_team_id, away_team_id, away_team_id, home_team_id, recent_limit))
        recent_rows = self.cur.fetchall()

        recent_list = []
        for r in recent_rows:
            # 判斷本次比賽中，這場主隊（傳入參數）vs 對方是誰
            # 若當前 home_team_id 是 r['home_team_id']，表示當前主隊在這場是 home
            this_is_home = (r['home_team_id'] == home_team_id)
            home_en = r['home_en']
            away_en = r['away_en']
            hs = r['home_team_score']
            a_s = r['away_team_score']

            if hs > a_s:
                winner = 'home'
                winner_label = home_en
            elif a_s > hs:
                winner = 'away'
                winner_label = away_en
            else:
                winner = 'tie'
                winner_label = 'tie'

            recent_list.append({
                'date': str(r['match_date']),
                'match': f"{home_en} {hs} - {a_s} {away_en}",
                'winner': winner,
                'winner_label': winner_label,
                # 給 prompt 用：本次對戰的 home_team（我們要預測的）當時是 home 還是 away
                'this_team_side': 'home' if this_is_home else 'away',
            })

        if result is not None:
            result['recent_matchups'] = recent_list
            return result

        # 若無總體資料但有 recent_matchups，回傳簡化結構
        if recent_list:
            return {
                'total_played': 0,
                'home_wins': 0,
                'away_wins': 0,
                'avg_home_score': 0,
                'avg_away_score': 0,
                'home_win_rate': 0,
                'away_win_rate': 0,
                'recent_matchups': recent_list,
            }

        return None

    def get_league_standings(self, team_id):
        """
        獲取隊伍在聯盟中的排名（直接從 games 表計算）
        """
        self.cur.execute("SELECT league FROM predictx.teams WHERE team_id = %s", (team_id,))
        team = self.cur.fetchone()
        if not team:
            return None
        
        league = team['league']
        
        query = """
            WITH team_games AS (
                SELECT 
                    t.team_id, t.english_name,
                    SUM(CASE 
                        WHEN (g.home_team_id = t.team_id AND g.home_team_score > g.away_team_score)
                             OR (g.away_team_id = t.team_id AND g.away_team_score > g.home_team_score)
                        THEN 1 ELSE 0 END) as wins,
                    SUM(CASE 
                        WHEN (g.home_team_id = t.team_id AND g.home_team_score < g.away_team_score)
                             OR (g.away_team_id = t.team_id AND g.away_team_score < g.home_team_score)
                        THEN 1 ELSE 0 END) as losses,
                    SUM(CASE WHEN g.home_team_id = t.team_id THEN g.home_team_score ELSE g.away_team_score END) as goals_for,
                    SUM(CASE WHEN g.home_team_id = t.team_id THEN g.away_team_score ELSE g.home_team_score END) as goals_against,
                    COUNT(*) as games_played
                FROM predictx.teams t
                JOIN predictx.games g ON (g.home_team_id = t.team_id OR g.away_team_id = t.team_id)
                WHERE t.league = %s AND g.status IN ('final', 'FINAL')
                GROUP BY t.team_id, t.english_name
            )
            SELECT *, 
                   ROUND(wins::numeric / NULLIF(games_played, 0), 3) as win_pct
            FROM team_games
            ORDER BY win_pct DESC
        """
        self.cur.execute(query, (league,))
        standings = self.cur.fetchall()
        
        for idx, row in enumerate(standings):
            if row['team_id'] == team_id:
                return {
                    "rank": idx + 1,
                    "total_teams": len(standings),
                    "wins": row['wins'],
                    "losses": row['losses'],
                    "games_played": row['games_played'],
                    "win_pct": float(row['win_pct']) if row['win_pct'] else 0.0,
                    "goals_for": int(row['goals_for']),
                    "goals_against": int(row['goals_against']),
                    "goal_diff": int(row['goals_for'] - row['goals_against'])
                }
        
        return None

    def get_game_features(self, game_id):
        """
        從資料庫提取單場比賽的所有分析特徵（強化版）
        對 MLB 賽事自動上網擷取即時進階數據
        """
        features = {}
        
        # 1. 基礎比賽資訊與隊伍名稱
        query_game = """
            SELECT g.*, 
                   ht.chinese_name as home_team_name,
                   ht.english_name as home_team_en,
                   at.chinese_name as away_team_name,
                   at.english_name as away_team_en,
                   ht.league as home_league,
                   at.league as away_league
            FROM predictx.games g
            JOIN predictx.teams ht ON g.home_team_id = ht.team_id
            JOIN predictx.teams at ON g.away_team_id = at.team_id
            WHERE g.game_id = %s
        """
        self.cur.execute(query_game, (game_id,))
        game = self.cur.fetchone()
        if not game:
            return None
        
        features['game_info'] = game
        league = game['home_league']
        features['league'] = league
        
        home_team_id = game['home_team_id']
        away_team_id = game['away_team_id']
        
        # 2. 兩隊近期戰績 (Recent Form)
        features['home_recent_form'] = self.get_team_recent_form(home_team_id, league, 5)
        features['away_recent_form'] = self.get_team_recent_form(away_team_id, league, 5)
        
        # 3. 對陣歷史
        features['historical_matchup'] = self.get_historical_matchup(home_team_id, away_team_id)
        
        # 4. 聯盟排名
        features['home_standings'] = self.get_league_standings(home_team_id)
        features['away_standings'] = self.get_league_standings(away_team_id)
        self.log_source("official_api")  # 遊戲基本資料
        self.log_source("official_api")  # 兩隊近期戰績 (2x)
        self.log_source("official_api")
        self.log_source("official_api")  # 對陣歷史
        self.log_source("official_api")  # 聯盟排名 (2x)
        
        # 5. 對 MLB 賽事：上網抓取即時進階數據
        if league and league.upper() == 'MLB':
            try:
                from mlb_data_fetcher import MLBDataFetcher
                fetcher = MLBDataFetcher(conn=self.conn)
                home_name = game['home_team_en']
                away_name = game['away_team_en']
                mlb_data = fetcher.fetch_and_store_game_data(game_id, home_name, away_name)
                if mlb_data:
                    features['mlb_advanced'] = mlb_data
                    for _ in mlb_data.get('sources', []):
                        self.log_source("official_api")
                    print(f"  📡 MLB live data: {len(mlb_data['team_stats']['home'])} home + {len(mlb_data['team_stats']['away'])} away stats")
                
                # 先發投手資料
                pitcher_data = fetcher.get_probable_pitcher_data(game_id, home_name, away_name)
                if pitcher_data:
                    features['mlb_pitchers'] = pitcher_data
                    # 🆕 [fix] 安全取得 pitcher，避免 None TypeError
                    hp = pitcher_data.get('home_pitcher') or {}
                    ap = pitcher_data.get('away_pitcher') or {}
                    if hp.get('stats'):
                        print(f"  ⚾ Home SP: {hp.get('name', 'TBD')} (ERA={hp['stats']['era']}, K/9={hp['stats']['k_per_9']})")
                    elif hp.get('name'):
                        print(f"  ⚾ Home SP: {hp['name']} (stats 尚未公布)")
                    if ap.get('stats'):
                        print(f"  ⚾ Away SP: {ap.get('name', 'TBD')} (ERA={ap['stats']['era']}, K/9={ap['stats']['k_per_9']})")
                    elif ap.get('name'):
                        print(f"  ⚾ Away SP: {ap['name']} (stats 尚未公布)")
                fetcher.close()
            except Exception as e:
                print(f"  ⚠ MLB data fetch error: {e}")
                self.conn.rollback()
        
        # 6. 對 NBA 賽事：上網抓取即時進階數據
        if league and league.upper() == 'NBA':
            try:
                from nba_data_fetcher import NBADataFetcher
                fetcher = NBADataFetcher()
                home_name = game['home_team_en']
                away_name = game['away_team_en']
                nba_data = fetcher.fetch_and_store_game_data(game_id, home_name, away_name)
                if nba_data:
                    features['nba_advanced'] = nba_data
                    for _ in nba_data.get('sources', []):
                        self.log_source("official_api")
                    print(f"  📡 NBA live data: OffRtg diff = {abs(nba_data['team_stats']['home']['off_rtg'] - nba_data['team_stats']['away']['off_rtg']):.1f}")
                fetcher.close()
            except Exception as e:
                print(f"  ⚠ NBA data fetch error: {e}")
        
        # 7. 整合天氣資料（MLB 與 NBA）
        if league and league.upper() in ('MLB', 'NBA'):
            try:
                from weather_fetcher import WeatherFetcher
                wf = WeatherFetcher()
                home_name = game['home_team_en']
                weather = wf.fetch_and_store_weather(game_id, home_name, league)
                if weather:
                    features['weather'] = weather
                    self.log_source("news_media")
                    print(f"  🌤 Weather: {weather['temperature_c']}°C, {weather['condition']}, wind={weather['wind_speed_kmh']}km/h")
                wf.close()
            except Exception as e:
                print(f"  ⚠ Weather fetch error: {e}")
                self.conn.rollback()
        
        # 8. NPB 即時數據（從 baseball-data.com 爬取）
        if league and league.upper() == 'NPB':
            try:
                from npb_data_fetcher import NPBDataFetcher
                fetcher = NPBDataFetcher()
                home_name = game['home_team_en']
                away_name = game['away_team_en']
                npb_data = fetcher.fetch_and_store_game_data(game_id, home_name, away_name)
                if npb_data:
                    features['npb_advanced'] = npb_data
                    for _ in npb_data.get('sources', []):
                        self.log_source("official_api")
                    print(f"  🏯 NPB live data: standings + batting + pitching")
                
                # NPB 先發投手輪值資料
                try:
                    home_starters = fetcher.get_top_starters(home_name, 5)
                    away_starters = fetcher.get_top_starters(away_name, 5)
                    if home_starters or away_starters:
                        features['npb_starters'] = {
                            'home': home_starters or [],
                            'away': away_starters or [],
                        }
                        hs = len(home_starters or [])
                        as_ = len(away_starters or [])
                        print(f"  🏯 NPB starters: {home_name} top {hs}, {away_name} top {as_}")
                except Exception as e:
                    print(f"  ⚠ NPB starter fetch error: {e}")
                
                fetcher.close()
            except Exception as e:
                print(f"  ⚠ NPB data fetch error: {e}")
        
        # 9. CPBL 球員資料（從 stats.cpbl.com.tw）
        if league and league.upper() == 'CPBL':
            try:
                from cpbl_data_fetcher import CPBLDataFetcher
                fetcher = CPBLDataFetcher()
                home_name = game['home_team_en']
                away_name = game['away_team_en']
                cpbl_data = fetcher.fetch_and_store_game_data(game_id, home_name, away_name)
                if cpbl_data:
                    features['cpbl_advanced'] = cpbl_data
                    print(f"  🏆 CPBL player data: {len(cpbl_data.get('players', {}).get('home', []))} home + {len(cpbl_data.get('players', {}).get('away', []))} away players, {len(cpbl_data.get('hitting_leaders', {}).get('home', []))} hitters")
                
                # CPBL 投手個人資料（從 sportify.tw）
                try:
                    all_pitchers = fetcher.get_cpbl_pitchers_from_sportify()
                    if all_pitchers:
                        features['cpbl_pitchers'] = all_pitchers
                        hp = all_pitchers.get(home_name, [])
                        ap = all_pitchers.get(away_name, [])
                        print(f"  🏆 CPBL pitchers: {home_name} {len(hp)} pitchers, {away_name} {len(ap)} pitchers")
                except Exception as e:
                    print(f"  ⚠ CPBL pitcher fetch error: {e}")
                
                fetcher.close()
            except Exception as e:
                print(f"  ⚠ CPBL data fetch error: {e}")
        
        # 10. FIFA 隊伍排名資料（從 ESPN API）
        if league and league.upper() == 'FIFA':
            try:
                from fifa_data_fetcher import FIFADataFetcher
                fetcher = FIFADataFetcher()
                home_name = game['home_team_en']
                away_name = game['away_team_en']
                home_rank = fetcher.get_team_ranking(home_name)
                away_rank = fetcher.get_team_ranking(away_name)
                if home_rank or away_rank:
                    features['fifa_rankings'] = {
                        'home': home_rank or {'standing': 'N/A', 'record': 'N/A'},
                        'away': away_rank or {'standing': 'N/A', 'record': 'N/A'},
                    }
                    print(f"  ⚽ FIFA rankings: {home_name}={home_rank.get('standing', 'N/A') if home_rank else 'N/A'}, {away_name}={away_rank.get('standing', 'N/A') if away_rank else 'N/A'}")
            except Exception as e:
                print(f"  ⚠ FIFA ranking fetch error: {e}")
        
        return features

    def generate_win_probability_prompt(self, features):
        """
        構建勝率預測的 Prompt（強化版：注入真實數據）
        """
        game = features['game_info']
        home_team = game['home_team_name']
        away_team = game['away_team_name']
        league = features['league']
        
        def format_form(form):
            if not form or not form['recent_games']:
                return "無近期比賽數據"
            lines = [f"戰績: {form['win_loss']}, 勝率: {form['win_rate']}"]
            lines.append(f"場均得分: {form['avg_goals_for']}, 場均失分: {form['avg_goals_against']}, 淨勝差: {form['goal_diff']}")
            # 🆕 主客場分離數據（讓 AI 區分主客表現）
            hr = form.get('home_record', {})
            ar = form.get('away_record', {})
            if hr.get('games', 0) > 0:
                lines.append(f"主場戰績: {hr['wins']}-{hr['losses']}（勝率 {hr['win_rate']*100:.0f}%, 場均 {hr['avg_for']:.1f}/{hr['avg_against']:.1f}）")
            if ar.get('games', 0) > 0:
                lines.append(f"客場戰績: {ar['wins']}-{ar['losses']}（勝率 {ar['win_rate']*100:.0f}%, 場均 {ar['avg_for']:.1f}/{ar['avg_against']:.1f}）")
            games_str = ", ".join([f"{g['result']} vs {g['opponent']}({g['score']})" for g in form['recent_games']])
            lines.append(f"最近比賽: {games_str}")
            return "\n    ".join(lines)
        
        home_form = format_form(features['home_recent_form'])
        away_form = format_form(features['away_recent_form'])
        
        def format_matchup(m):
            if not m:
                return "無對陣歷史數據"
            lines = [f"總計交手 {m['total_played']} 次, "
                     f"主隊勝 {m['home_wins']} 次({m['home_win_rate']*100:.0f}%), "
                     f"客隊勝 {m['away_wins']} 次({m['away_win_rate']*100:.0f}%), "
                     f"場均比分 {m['avg_home_score']}-{m['avg_away_score']}"]
            # 🆕 加入最近 N 場對戰明細（讓 LLM 看出近期對戰趨勢）
            recent = m.get('recent_matchups', [])
            if recent:
                lines.append("\n最近對戰明細：")
                for r in recent:
                    lines.append(f"  {r['date']}: {r['match']} (贏家: {r['winner_label']})")
            return "\n".join(lines)
        
        matchup = format_matchup(features['historical_matchup'])
        
        # MLB 即時進階數據（從 statsapi.mlb.com 線上取得）
        mlb_advanced = features.get('mlb_advanced', {})
        if mlb_advanced:
            home_adv = mlb_advanced['team_stats']['home']
            away_adv = mlb_advanced['team_stats']['away']
            
            def calc_era(er, outs):
                return round(er * 9 / (outs / 3), 2) if outs > 0 else 0
            def calc_avg(h, ab):
                return round(h / ab, 3) if ab > 0 else 0
            def calc_obp(h, bb, hbp, sf, ab):
                denom = ab + bb + hbp + sf
                return round((h + bb + hbp) / denom, 3) if denom > 0 else 0
            def calc_slg(tb, ab):
                return round(tb / ab, 3) if ab > 0 else 0
            def calc_ops(obp, slg):
                return round(obp + slg, 3)
            def calc_whip(bb, h, ip):
                return round((bb + h) / ip, 3) if ip > 0 else 0
            
            ha = {k.lower(): v for k, v in home_adv.items()}
            aa = {k.lower(): v for k, v in away_adv.items()}
            
            h_era = calc_era(ha.get('pitching_earnedruns', 0), ha.get('pitching_outs', 0))
            a_era = calc_era(aa.get('pitching_earnedruns', 0), aa.get('pitching_outs', 0))
            h_whip = calc_whip(ha.get('pitching_baseonballs', 0), ha.get('pitching_hits', 0), ha.get('pitching_outs', 0) / 3)
            a_whip = calc_whip(aa.get('pitching_baseonballs', 0), aa.get('pitching_hits', 0), aa.get('pitching_outs', 0) / 3)
            h_avg = calc_avg(ha.get('hitting_hits', 0), ha.get('hitting_atbats', 0))
            a_avg = calc_avg(aa.get('hitting_hits', 0), aa.get('hitting_atbats', 0))
            h_obp = calc_obp(ha.get('hitting_hits', 0), ha.get('hitting_baseonballs', 0),
                           ha.get('hitting_hitbypitch', 0), ha.get('hitting_sacflies', 0), ha.get('hitting_atbats', 0))
            a_obp = calc_obp(aa.get('hitting_hits', 0), aa.get('hitting_baseonballs', 0),
                           aa.get('hitting_hitbypitch', 0), aa.get('hitting_sacflies', 0), aa.get('hitting_atbats', 0))
            h_slg = calc_slg(ha.get('hitting_totalbases', 0), ha.get('hitting_atbats', 0))
            a_slg = calc_slg(aa.get('hitting_totalbases', 0), aa.get('hitting_atbats', 0))
            h_ops = calc_ops(h_obp, h_slg)
            a_ops = calc_ops(a_obp, a_slg)
            h_hr = ha.get('hitting_homeruns', 0)
            a_hr = aa.get('hitting_homeruns', 0)
            h_k9 = round(ha.get('pitching_strikeouts', 0) * 9 / (ha.get('pitching_outs', 0) / 3), 2) if ha.get('pitching_outs', 0) > 0 else 0
            a_k9 = round(aa.get('pitching_strikeouts', 0) * 9 / (aa.get('pitching_outs', 0) / 3), 2) if aa.get('pitching_outs', 0) > 0 else 0
            
            mlb_advanced_section = f"""===== MLB 即時進階數據（來源：statsapi.mlb.com）=====
主隊 {home_team}:
  團隊打擊: AVG={h_avg:.3f}, OBP={h_obp:.3f}, SLG={h_slg:.3f}, OPS={h_ops:.3f}, HR={h_hr}
  團隊投球: ERA={h_era:.2f}, WHIP={h_whip:.3f}, K/9={h_k9:.1f}

客隊 {away_team}:
  團隊打擊: AVG={a_avg:.3f}, OBP={a_obp:.3f}, SLG={a_slg:.3f}, OPS={a_ops:.3f}, HR={a_hr}
  團隊投球: ERA={a_era:.2f}, WHIP={a_whip:.3f}, K/9={a_k9:.1f}"""
        else:
            mlb_advanced_section = ""
        
        # 先發投手資料
        pitchers = features.get("mlb_pitchers", {})
        if pitchers and pitchers.get("home_pitcher", {}).get("stats"):
            hp = pitchers["home_pitcher"]
            ap = pitchers["away_pitcher"]

            # 🆕 格式化「最近 3 場」表現
            def format_recent_games(pitcher_data, team_label):
                recent = pitcher_data.get("recent_stats")
                if not recent or not recent.get("games"):
                    return ""
                games = recent['games']
                summary = recent['summary']
                lines = [f"\n  📊 最近 {summary['count']} 場表現: {summary['wins']}W-{summary['losses']}L, "
                         f"ERA={summary['era']}, WHIP={summary['whip']}, K/9={summary['k_per_9']}"]
                for g in games:
                    lines.append(f"    {g['date']} vs {g['opponent']}: {g['ip']}局, "
                                 f"{g['er']}ER, {g['h']}H, {g['bb']}BB, {g['k']}K, "
                                 f"ERA={g['era']} ({g['decision']})")
                return "\n".join(lines)

            h_recent_str = format_recent_games(hp, "主隊")
            a_recent_str = format_recent_games(ap, "客隊")

            # 🆕 [fix] 安全取得 stats 欄位（投手可能 TBD）
            def safe_get_stats(pitcher):
                stats = pitcher.get("stats") or {}
                return {
                    'era': stats.get('era', 0),
                    'whip': stats.get('whip', 0),
                    'k_per_9': stats.get('k_per_9', 0),
                    'bb_per_9': stats.get('bb_per_9', 0),
                    'k_bb_ratio': stats.get('k_bb_ratio', 0),
                    'avg': stats.get('avg', 0),
                    'ip': stats.get('ip', 0),
                }
            h_stats = safe_get_stats(hp)
            a_stats = safe_get_stats(ap)

            mlb_advanced_section += f"""

===== 先發投手對決（來源：statsapi.mlb.com）=====
主隊先發: {hp["name"]}
  本季 ERA={h_stats['era']:.2f}, WHIP={h_stats['whip']:.3f}, K/9={h_stats['k_per_9']:.1f}, BB/9={h_stats['bb_per_9']:.1f}
  K/BB={h_stats['k_bb_ratio']:.2f}, 對手打擊率={h_stats['avg']:.3f}, 本季投球={h_stats['ip']}局{h_recent_str}

客隊先發: {ap["name"]}
  本季 ERA={a_stats['era']:.2f}, WHIP={a_stats['whip']:.3f}, K/9={a_stats['k_per_9']:.1f}, BB/9={a_stats['bb_per_9']:.1f}
  K/BB={a_stats['k_bb_ratio']:.2f}, 對手打擊率={a_stats['avg']:.3f}, 本季投球={a_stats['ip']}局{a_recent_str}

💡 分析指引：投手「最近 3 場」表現比「整季」更具預測力。請特別注意：
- 最近 3 場 ERA 與整季 ERA 的差距（升溫或降溫中）
- 若最近 3 場被打爆（ERA > 6），即使整季很好，下場也應降低其球隊勝率
- 若最近 3 場極佳（ERA < 2.0），即使整季普通，也應提升其球隊勝率"""

        # 🆕 Bullpen 疲勞指數
        bullpen = pitchers.get("bullpen_fatigue", {})
        if bullpen:
            def format_bullpen(side, label):
                data = bullpen.get(side, {})
                if not data:
                    return ""
                lines = [f"\n  {label}（{data.get('team_name', '')}）: 近 3 天投手群總投球 {data['total_ip_last_3_days']} 局, "
                         f"疲勞等級: {data['fatigue_label']}"]
                for gd in data.get('game_details', []):
                    lines.append(f"    {gd['date']}: {gd['pitchers_count']} 位投手, 共 {round(gd['total_outs']/3, 1)} 局")
                return "\n".join(lines)

            h_bullpen = format_bullpen('home', '主隊牛棚')
            a_bullpen = format_bullpen('away', '客隊牛棚')

            mlb_advanced_section += f"""

===== Bullpen 疲勞指數（近 3 天）=====
{h_bullpen}
{a_bullpen}

💡 牛棚疲勞分析指引：
- 牛棚疲勞會顯著增加後段比賽失分率：高度疲勞（>15 局）後段失分率可能增加 20-30%
- 若客隊牛棚疲勞較高，主隊在後段（7-9 局）應有明顯優勢
- 若主隊牛棚疲勞但客隊正常，主隊勝率應下調（後段守不住）"""
        else:
            mlb_advanced_section = ""
        
        # NBA 即時進階數據（從 stats.nba.com 線上取得）
        nba_advanced = features.get('nba_advanced', {})
        if nba_advanced:
            h = nba_advanced['team_stats']['home']
            a = nba_advanced['team_stats']['away']
            nba_advanced_section = f"""===== NBA 即時進階數據（來源：stats.nba.com）=====
主隊 {home_team}:
  進攻效率(OffRtg): {h['off_rtg']:.1f}, 防守效率(DefRtg): {h['def_rtg']:.1f}, 淨效率(Net): {h['net_rating']:.1f}
   Pace: {h['pace']:.1f}, EFG%: {h['efg_pct']:.3f}, TS%: {h['ts_pct']:.3f}, 勝率: {h['win_pct']:.3f}

客隊 {away_team}:
  進攻效率(OffRtg): {a['off_rtg']:.1f}, 防守效率(DefRtg): {a['def_rtg']:.1f}, 淨效率(Net): {a['net_rating']:.1f}
   Pace: {a['pace']:.1f}, EFG%: {a['efg_pct']:.3f}, TS%: {a['ts_pct']:.3f}, 勝率: {a['win_pct']:.3f}"""
        else:
            nba_advanced_section = ""
        
        # 天氣資料
        weather_data = features.get('weather', {})
        if weather_data:
            weather_section = f"""===== 球場天氣（來源：wttr.in）=====
城市: {weather_data['city']}
天氣: {weather_data['condition']}
溫度: {weather_data['temperature_c']}°C
風速: {weather_data['wind_speed_kmh']} km/h ({weather_data['wind_direction']})
濕度: {weather_data['humidity_pct']}%
降雨: {weather_data['precip_mm']}mm"""
        else:
            weather_section = ""
        
        # NPB 即時數據（從 baseball-data.com 爬取）
        npb_data = features.get('npb_advanced', {})
        if npb_data:
            h_stand = npb_data['standings']['home']
            a_stand = npb_data['standings']['away']
            h_bat = npb_data['batting']['home']
            a_bat = npb_data['batting']['away']
            h_pitch = npb_data['pitching']['home']
            a_pitch = npb_data['pitching']['away']
            
            h_avg = h_bat.get('avg', 0)
            a_avg = a_bat.get('avg', 0)
            h_hr = h_bat.get('hr', 0)
            a_hr = a_bat.get('hr', 0)
            h_wpct = h_stand.get('win_pct', '.500')
            a_wpct = a_stand.get('win_pct', '.500')
            h_pwpct = h_pitch.get('win_pct', 0.5)
            a_pwpct = a_pitch.get('win_pct', 0.5)
            
            npb_section = f"""===== NPB 即時數據（來源：baseball-data.com）=====
主隊 {home_team}:
  排名: {h_stand.get('rank', '?')}位, 戰績: {h_stand.get('wins', '0')}W-{h_stand.get('losses', '0')}L-{h_stand.get('ties', '0')}D
  團隊打擊: AVG={h_avg}, HR={h_hr}
  團隊投球: {h_pitch.get('wins', 0)}W-{h_pitch.get('losses', 0)}L, Win%={h_pwpct:.3f}

客隊 {away_team}:
  排名: {a_stand.get('rank', '?')}位, 戰績: {a_stand.get('wins', '0')}W-{a_stand.get('losses', '0')}L-{a_stand.get('ties', '0')}D
  團隊打擊: AVG={a_avg}, HR={a_hr}
  團隊投球: {a_pitch.get('wins', 0)}W-{a_pitch.get('losses', 0)}L, Win%={a_pwpct:.3f}"""

            # 🆕 注入 Park Factor（球場修正）
            pf = npb_data.get('park_factor')
            home_park = npb_data.get('home_park')
            if pf is not None:
                park_interp = "投手戰" if pf < 0.95 else ("打擊戰" if pf > 1.05 else "中性")
                npb_section += f"""

===== 球場修正係數 =====
主場球場: {home_park or '未知'}
Park Factor: {pf:.2f} ({park_interp})
{'提示：主場球場投手戰，主隊投手有微幅優勢' if pf < 0.95 else ''}
{'提示：主場球場打擊戰，主隊打者有微幅優勢' if pf > 1.05 else ''}"""
        else:
            npb_section = ""
        
        # NPB 先發投手輪值資料
        npb_starters = features.get("npb_starters", {})
        if npb_starters and (npb_starters.get("home") or npb_starters.get("away")):
            def fmt_starters(starters):
                if not starters:
                    return "無先發投手數據"
                result_lines = []
                for sp in starters:
                    name = sp.get('name', '?')
                    era = sp.get('era', 0)
                    whip = sp.get('whip', 0)
                    k9 = sp.get('k_per_9', 0)
                    bb9 = sp.get('bb_per_9', 0)
                    w = sp.get('wins', 0)
                    l = sp.get('losses', 0)
                    ip = sp.get('ip', 0)
                    result_lines.append(
                        f"    #{len(result_lines)+1} {name}: ERA={era:.2f}, WHIP={whip:.3f}, "
                        f"K/9={k9:.1f}, BB/9={bb9:.1f}, "
                        f"{w}W-{l}L, {ip}局"
                    )
                return "\n".join(result_lines)
            
            h_start = fmt_starters(npb_starters.get("home", []))
            a_start = fmt_starters(npb_starters.get("away", []))
            npb_section += f"""
            
===== NPB 先發投手輪值（來源：baseball-data.com）=====
主隊 {home_team} 輪值投手：
{h_start}

客隊 {away_team} 輪值投手：
{a_start}"""
        def format_standings(s):
            if not s:
                return "無排名數據"
            return f"第 {s['rank']}/{s['total_teams']} 名, {s['wins']}勝{s['losses']}敗, 勝率 {s['win_pct']:.3f}, 得分 {s['goals_for']}, 失分 {s['goals_against']}, 淨勝分 {s['goal_diff']:+d}"
        
        home_standings = format_standings(features['home_standings'])
        away_standings = format_standings(features['away_standings'])
        
        league_dimensions = {
            "MLB": ["球隊整體戰力", "打線火力", "先發投手", "牛棚表現", "主客場因素", "近期狀態"],
            "NPB": ["球隊整體戰力", "打線火力", "先發投手", "牛棚表現", "主客場因素", "近期狀態"],
            "CPBL": ["球隊整體戰力", "打線火力", "先發投手", "牛棚表現", "主客場因素", "近期狀態"],
            "NBA": ["團隊整體戰力", "進攻效率", "防守強度", "籃板能力", "關鍵球處理", "近期狀態"],
            "FIFA": ["整體戰術實力", "前場進攻", "中場掌控", "後防穩定", "門將表現", "近期狀態"]
        }
        
        league_upper = league.upper() if league else ""
        current_dims = ["整體戰力", "進攻能力", "防守能力", "戰術執行", "環境因素", "近期狀態"]
        for key, dims in league_dimensions.items():
            if key in league_upper:
                current_dims = dims
                break

        # 🆕 通用主場優勢提示（CPBL 已有，補 MLB/NBA/NPB）
        league_upper_check = (league or "").upper()
        home_advantage_note = ""
        if "NBA" in league_upper_check:
            home_advantage_note = "\n- NBA 主場優勢極為顯著：歷史主場勝率約 60%。對實力接近的對戰，主場球隊勝率應明顯 > 0.5。"
        elif "MLB" in league_upper_check:
            home_advantage_note = "\n- MLB 主場優勢約 53-54%。在五五波對戰中，主隊有統計上的小幅優勢，請勿系統性傾向客隊。"
        elif "NPB" in league_upper_check:
            home_advantage_note = "\n- NPB 主場優勢約 53%。對實力接近的對戰，主隊有小幅優勢。"
        # CPBL 已在 cpbl_analysis_guide 中有「主場勝率約 55-60%」提示

        # CPBL 專屬分析指引 + 球員/戰績數據
        cpbl_analysis_guide = ""
        if league and league.upper() == 'CPBL':
            cpbl_spec = "===== CPBL 分析指引 =====\n"
            cpbl_spec += "中華職棒特色：\n"
            cpbl_spec += "- 洋將（外籍投手）對戰局影響極大，先發洋投通常佔優勢\n"
            cpbl_spec += "- 中職打者對新洋投適應期約 1-2 場\n"
            cpbl_spec += "- 牛棚穩定度是關鍵勝負因素\n"
            cpbl_spec += "- 主場優勢明顯（中職主場勝率約 55-60%）\n"
            cpbl_spec += "- 近期團隊打擊狀況（近5場平均得分）比整季數據更具參考價值\n"
            cpbl_spec += "- 中職比賽節奏快，比分差距通常不大\n"
            cpbl_spec += "- 請特別關注兩隊近5場得失分差（淨勝分）\n"
            cpbl_spec += "- 對戰組合的歷史交手紀錄（H2H）在中職有較高參考價值"

            cpbl_data = features.get('cpbl_advanced', {})
            if cpbl_data:
                if cpbl_data.get('players'):
                    h_ps = cpbl_data['players']['home']
                    a_ps = cpbl_data['players']['away']
                    h_names = ", ".join([p['name'] for p in h_ps[:8]])
                    a_names = ", ".join([p['name'] for p in a_ps[:8]])
                    cpbl_spec += f"\n玩家名單 — 主隊 {home_team}（{len(h_ps)}人）: {h_names} | 客隊 {away_team}（{len(a_ps)}人）: {a_names}"

                h_stand = cpbl_data.get('standings', {}).get('home', {})
                a_stand = cpbl_data.get('standings', {}).get('away', {})
                h_pitch = cpbl_data.get('pitching', {}).get('home', {})
                a_pitch = cpbl_data.get('pitching', {}).get('away', {})
                h_bat = cpbl_data.get('batting', {}).get('home', {})
                a_bat = cpbl_data.get('batting', {}).get('away', {})

                if h_stand and h_stand.get('win_pct'):
                    cpbl_spec += f"\n團隊數據（來源：cpbl.com.tw）:"
                    cpbl_spec += f"\n主隊 {home_team}: 第{h_stand['rank']}名, {h_stand['wl_record']}, 勝率{h_stand['win_pct']}"
                    cpbl_spec += f" | Team ERA={h_pitch.get('era','?')}, SO={h_pitch.get('so','?')}, HR={h_bat.get('hr','?')}"
                    cpbl_spec += f"\n客隊 {away_team}: 第{a_stand['rank']}名, {a_stand['wl_record']}, 勝率{a_stand['win_pct']}"
                    cpbl_spec += f" | Team ERA={a_pitch.get('era','?')}, SO={a_pitch.get('so','?')}, HR={a_bat.get('hr','?')}"

                hitters = cpbl_data.get('hitting_leaders', {})
                if hitters and hitters.get('home'):
                    top_h = hitters['home'][0]
                    top_a = hitters['away'][0] if hitters.get('away') else None
                    cpbl_spec += f"\n打擊榜 — {home_team} 最佳: {top_h['name']} ({top_h['avg']}, {top_h['hr']}HR)"
                    if top_a:
                        cpbl_spec += f" | {away_team} 最佳: {top_a['name']} ({top_a['avg']}, {top_a['hr']}HR)"

                        # CPBL 投手個人資料（從 sportify.tw）
            cpbl_pitchers = features.get('cpbl_pitchers', {})
            if cpbl_pitchers:
                cpbl_spec += "\n\n===== CPBL 投手數據（來源：sportify.tw）====="
                h_ps = cpbl_pitchers.get(home_team, [])
                a_ps = cpbl_pitchers.get(away_team, [])
                if h_ps:
                    cpbl_spec += "\n主隊 %s 投手群：" % home_team
                    for i, p in enumerate(h_ps, 1):
                        line = "\n  #%d %s: ERA=%.2f, WHIP=%.3f, K/9=%.1f, BB/9=%.1f, %dW-%dL, %.1f局" % (
                            i, p['name'], p['era'], p['whip'], p['k_per_9'], p['bb_per_9'], p['wins'], p['losses'], p['ip'])
                        cpbl_spec += line
                if a_ps:
                    cpbl_spec += "\n客隊 %s 投手群：" % away_team
                    for i, p in enumerate(a_ps, 1):
                        line = "\n  #%d %s: ERA=%.2f, WHIP=%.3f, K/9=%.1f, BB/9=%.1f, %dW-%dL, %.1f局" % (
                            i, p['name'], p['era'], p['whip'], p['k_per_9'], p['bb_per_9'], p['wins'], p['losses'], p['ip'])
                        cpbl_spec += line

            cpbl_analysis_guide = "\n===== " + cpbl_spec + "\n\n請根據以上 CPBL 特性，結合提供的數據進行分析。\n"

        # FIFA Over/Under 2.5 指令
        fifa_ou_instruction = ""
        fifa_ou_field = ""
        fifa_rankings_section = ""
        if league and league.upper() == "FIFA":
            fifa_ou_instruction = "6. **Over/Under 2.5 預測**：請根據總進球數趨勢，判斷本場總進球數是否超過 2.5 球。"
            fifa_ou_field = ', "over_under_2_5": true'
            # FIFA 隊伍排名資料
            fifa_rank = features.get('fifa_rankings', {})
            if fifa_rank:
                h = fifa_rank.get('home', {})
                a = fifa_rank.get('away', {})
                fifa_rankings_section = f"===== FIFA 隊伍排名（來源：ESPN）=====\n主隊 {home_team}: {h.get('standing', 'N/A')}, 戰績 {h.get('record', 'N/A')}\n客隊 {away_team}: {a.get('standing', 'N/A')}, 戰績 {a.get('record', 'N/A')}\n"
        
        prompt = f'''
你是一位專業運動分析師。請根據以下提供的真實數據，對 {home_team} vs {away_team} 這場 {league} 比賽進行量化分析。

比賽資訊：
- 聯賽: {league}
- 主場: {home_team}
- 客場: {away_team}

===== 主隊 {home_team} =====
聯盟排名: {home_standings}
{home_form}

===== 客隊 {away_team} =====
聯盟排名: {away_standings}
{away_form}

===== 對陣歷史 =====
{matchup}

{mlb_advanced_section}
{nba_advanced_section}
{npb_section}
{weather_section}
{cpbl_analysis_guide}
{home_advantage_note}
{fifa_rankings_section}

請完成以下分析：
1. 對比兩隊的近期表現與實力差距
2. 參考聯盟排名評估優劣勢
3. 為以下維度進行 0-10 評分: {json.dumps(current_dims, ensure_ascii=False)}
4. 給出勝率與預測比分
5. **信心指數 (confidence) 必須是 1-10 的整數**。請依下列標準精確評估：
   - **1-3**: 數據嚴重不足或兩隊實力極為接近，勝率可能僅 50-55%。請誠實給低分。
   - **4-5**: 有基本數據但仍有重大不確定因素，預期命中率 55-60%。
   - **6**: 數據明確顯示一方略佔優（主場優勢、近期狀態等），預期命中率 60-65%。
   - **7**: 數據顯示一方明顯佔優（投手對位、打線強度等差異顯著），預期命中率 70-75%。
   - **8**: 數據強烈支持一方（投手實力差距大、戰績懸殊），預期命中率 80-85%。
   - **9**: 極高把握（如 ace 對弱投、戰績懸殊且近期狀態都好），預期命中率 85-90%。
   - **10**: 史詩級優勢，幾乎確定（例如最強 ace 對最弱打線），僅限極少數情況使用。
   - **重要：信心 7 必須真正「明顯佔優」才給**，不要因為「想讓用戶相信」而過度自信。{fifa_ou_instruction}

**重要規則（請嚴格遵守）：**
- home_win_probability 和 away_win_probability 的總和必須等於 1.0
- 不允許回傳 0.5/0.5 這種五五波，請根據數據做出明確判斷
- 如果主隊有優勢，home_win_probability 應 > 0.5（例如 0.55-0.75）
- 如果客隊有優勢，home_win_probability 應 < 0.5（例如 0.25-0.45）
- 🆕 **請勿系統性傾向客隊**：歷史數據顯示「主隊在主場有統計顯著優勢」（詳見上方主場優勢提示）。當兩隊實力接近、數據不明時，請給主隊略高的勝率（例如 0.52-0.55），而非傾向客隊。
- 預測比分必須是具體數字，不能是 "N/A" 或空值

請嚴格按照以下 JSON 格式輸出，**只輸出 JSON**，不要有任何其他文字：
{{ 
  "home_win_probability": 0.0, 
  "away_win_probability": 0.0, 
  "confidence": 0, 
  "key_factors": ["因素1", "因素2", "因素3"], 
  "summary": "分析摘要（至少30字）",
  "predicted_score": "預測比分"{fifa_ou_field},
  "radar_chart": {{
    "categories": {json.dumps(current_dims, ensure_ascii=False)},
    "home_team": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    "away_team": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
  }}
}}
請只輸出這個 JSON，不要有任何其他文字或說明。
'''
        return prompt

    def call_ollama(self, prompt):
        """調用 AI 模型獲取 JSON 結果（支援本地 Ollama 與雲端）"""
        if USE_CLOUD:
            time.sleep(5)
            return self._call_cloud(prompt)
        else:
            return self._call_local_ollama(prompt)

    def _call_cloud(self, prompt):
        """調用雲端 LLM 含 retry，失敗時自動切換到備援 LLM"""
        # 先試主要 LLM
        result = self._try_llm(CLOUD_LLM_URL, CLOUD_LLM_MODEL, CLOUD_LLM_API_KEY, prompt)
        if result:
            return result
        # 主要 LLM 失敗，試備援（Ollama Cloud）
        if FALLBACK_LLM_API_KEY and FALLBACK_LLM_URL != CLOUD_LLM_URL:
            print("  ⚠ Primary LLM failed, trying fallback (Ollama Cloud)...")
            return self._try_llm(FALLBACK_LLM_URL, FALLBACK_LLM_MODEL, FALLBACK_LLM_API_KEY, prompt)
        return None

    def _try_llm(self, url, model, api_key, prompt):
        """嘗試呼叫一個 LLM 端點"""
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "你是一位頂尖的運動賽事分析師，擁有 20 年球評經驗，為 ESPN/NHK/Sportify 等知名媒體擔任過賽事評論員。你的風格是深入淺出、引用具體數據、語氣專業且有熱情，分析如同電視轉播的賽前分析節目。請根據提供的數據進行深度分析，並嚴格按照要求的 JSON 格式輸出。只輸出 JSON，不要有任何其他文字。"},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.5,
            "max_tokens": 8192,
            "stream": False
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        for attempt in range(3):
            try:
                response = requests.post(url, json=payload, headers=headers, timeout=120)
                if response.status_code == 429:
                    import time as t; t.sleep(10 * (2 ** attempt))
                    continue
                response.raise_for_status()
                data = response.json()
                if "choices" in data:
                    c = data["choices"][0].get("message", {}).get("content", "").strip()
                elif "message" in data:
                    c = data["message"].get("content", "").strip()
                else:
                    c = ""
                if not c:
                    return None
                return self._parse_json_response(c)
            except Exception as e:
                if attempt < 2:
                    import time as t; t.sleep(5 * (2 ** attempt))
                    continue
                return None
        return None
    
    def _parse_json_response(self, text):
        """解析 AI 回傳的 JSON（包含嵌套結構與中文鍵名處理）"""
        try:
            result = json.loads(text)
        except json.JSONDecodeError:
            # 嘗試從文字中提取 JSON 區塊
            import re
            start = text.find('{')
            if start >= 0:
                depth = 0
                end = start
                for i, c in enumerate(text[start:], start=start):
                    if c == '{':
                        depth += 1
                    elif c == '}':
                        depth -= 1
                        if depth == 0:
                            end = i + 1
                            break
                try:
                    result = json.loads(text[start:end])
                except json.JSONDecodeError:
                    print("Could not parse response as JSON")
                    print(f"  Raw (first 200): {text[:200]}")
                    return None
            else:
                print("Could not parse response (no JSON found)")
                print(f"  Raw (first 200): {text[:200]}")
                return None
        
        # 處理嵌套結構
        if isinstance(result, dict):
            for key in ['result', 'analysis', 'output', 'prediction']:
                if key in result and isinstance(result[key], dict):
                    nested = result[key]
                    if any(k in nested for k in ['home_win_probability', 'home_team', 'summary']):
                        result = nested
                        break
        
        # 中文鍵名映射
        if isinstance(result, dict):
            cn_map = {
                "主隊勝率": "home_win_probability",
                "客隊勝率": "away_win_probability",
                "信心指數": "confidence",
                "關鍵因素": "key_factors",
                "分析摘要": "summary",
                "預測比分": "predicted_score",
                "主隊雷達": "home_team",
                "客隊雷達": "away_team",
                "雷達維度": "categories",
                "主隊總分": "home_total_score",
                "客隊總分": "away_total_score",
                "home_wins_probability": "home_win_probability",
                "away_wins_probability": "away_win_probability",
            }
            for old_k, new_k in cn_map.items():
                if old_k in result:
                    result[new_k] = result.pop(old_k)
            
            # 補齊缺失欄位
            for field in ['home_win_probability', 'away_win_probability', 'confidence', 'summary', 'predicted_score']:
                if field not in result:
                    result[field] = 0.0 if field in ['home_win_probability', 'away_win_probability', 'confidence'] else ''
            if 'key_factors' not in result:
                result['key_factors'] = [result['summary'][:20]] if result.get('summary') else []
            if 'radar_chart' not in result:
                result['radar_chart'] = {"categories": [], "home_team": [], "away_team": []}
        
        return result

    def _call_local_ollama(self, prompt):
        """調用本地 Ollama"""
        is_9b = '9b' in MODEL_NAME.lower()
        payload = {
            "model": MODEL_NAME,
            "prompt": prompt,
            "stream": False,
            "num_predict": 8192 if is_9b else 4096,
        }
        timeout_sec = 300 if is_9b else 60
        try:
            response = requests.post(OLLAMA_URL, json=payload, timeout=timeout_sec)
            response.raise_for_status()
            raw = response.json()
            
            text_to_parse = None
            
            thinking_text = raw.get('thinking', '').strip()
            if thinking_text:
                text_to_parse = thinking_text
            
            if not text_to_parse:
                response_text = raw.get('response', '').strip()
                if response_text:
                    text_to_parse = response_text
            
            if not text_to_parse:
                print("Ollama returned empty response")
                return None
            
            try:
                result = json.loads(text_to_parse)
            except json.JSONDecodeError:
                # 嘗試從文字中提取 JSON 區塊（支援巢狀大括號）
                import re
                # 找到第一個 { 和匹配的 }
                start = text_to_parse.find('{')
                if start >= 0:
                    depth = 0
                    end = start
                    for i, c in enumerate(text_to_parse[start:], start=start):
                        if c == '{':
                            depth += 1
                        elif c == '}':
                            depth -= 1
                            if depth == 0:
                                end = i + 1
                                break
                    json_str = text_to_parse[start:end]
                    try:
                        result = json.loads(json_str)
                    except json.JSONDecodeError:
                        print("Could not parse Ollama response")
                        print(f"  Raw (first 300): {text_to_parse[:300]}")
                        return None
                else:
                    print("Could not parse Ollama response (no JSON found)")
                    print(f"  Raw (first 300): {text_to_parse[:300]}")
                    return None
            
            # 處理嵌套結構
            if isinstance(result, dict):
                for key in ['result', 'analysis', 'output', 'prediction']:
                    if key in result and isinstance(result[key], dict):
                        nested = result[key]
                        if any(k in nested for k in ['home_win_probability', 'home_team', 'summary']):
                            result = nested
                            break
            
            # 中文鍵名映射
            if isinstance(result, dict):
                cn_map = {
                    "主隊勝率": "home_win_probability",
                    "客隊勝率": "away_win_probability",
                    "信心指數": "confidence",
                    "關鍵因素": "key_factors",
                    "分析摘要": "summary",
                    "預測比分": "predicted_score",
                    "主隊雷達": "home_team",
                    "客隊雷達": "away_team",
                    "雷達維度": "categories",
                    "主隊總分": "home_total_score",
                    "客隊總分": "away_total_score",
                    "home_wins_probability": "home_win_probability",
                    "away_wins_probability": "away_win_probability",
                }
                for old_k, new_k in cn_map.items():
                    if old_k in result:
                        result[new_k] = result.pop(old_k)
                
                # 補齊缺失欄位
                for field in ['home_win_probability', 'away_win_probability', 'confidence', 'summary', 'predicted_score']:
                    if field not in result:
                        result[field] = 0.0 if field in ['home_win_probability', 'away_win_probability', 'confidence'] else ''
                if 'key_factors' not in result:
                    result['key_factors'] = [result['summary'][:20]] if result.get('summary') else []
                if 'radar_chart' not in result:
                    result['radar_chart'] = {"categories": [], "home_team": [], "away_team": []}
                if 'home_total_score' not in result:
                    result['home_total_score'] = 0.0
                if 'away_total_score' not in result:
                    result['away_total_score'] = 0.0
            
            return result
            
        except Exception as e:
            print(f"Ollama API Error: {e}")
            return None

    def analyze_game(self, game_id):
        print(f"Analyzing game {game_id}...")
        self.used_sources = []  # Step 5: 重置來源追蹤
        try:
            features = self.get_game_features(game_id)
        except Exception as e:
            print(f"  ⚠ get_game_features error: {e}")
            self.conn.rollback()
            return None
        if not features:
            return None
        prompt = self.generate_win_probability_prompt(features)
        result = self.call_ollama(prompt)
        
        # 驗證結果完整性
        if result and isinstance(result, dict):
            required_fields = ['summary', 'key_factors', 'home_win_probability', 
                             'away_win_probability', 'confidence', 'radar_chart']
            has_all = all(f in result for f in required_fields)
            has_summary = bool(result.get('summary'))
            
            if has_all and has_summary:
                # 檢測是否為 AI 模板垃圾（0.0 值或佔位文字）
                hp_raw = float(result.get("home_win_probability", 0.0))
                ap_raw = float(result.get("away_win_probability", 0.0))
                summary = (result.get("summary") or "")
                is_template = (
                    (hp_raw == 0.0 and ap_raw == 0.0)
                    or "分析摘要" in summary[:10]
                    or "因素1" in summary
                )
                if is_template:
                    print("  AI returned template, using computed fallback")
                    return None  # 走 fallback 路徑
                # Step 5: 加入來源可信度評分
                source_score = self.calculate_source_score()
                result["source_quality"] = {
                    "score": source_score,
                    "sources": list(self.used_sources)
                }
                
                # Step 4: 數值範圍驗證與正規化
                home_prob = float(result.get("home_win_probability", 0.0))
                away_prob = float(result.get("away_win_probability", 0.0))
                
                # 強制正規化：確保 home + away = 1.0
                total = home_prob + away_prob
                if total > 0:
                    home_prob = home_prob / total
                    away_prob = away_prob / total
                else:
                    home_prob = 0.5
                    away_prob = 0.5
                
                # 防止 0.5/0.5 五五波：根據主場優勢統計微調
                # 🆕 主場優勢基準：棒球 ~53-54%、NBA ~60%、CPBL ~55-60%、NPB ~53%
                # 五五波時應預設主隊略佔優（home 0.52-0.55），而非客隊
                if abs(home_prob - 0.5) < 0.01 and abs(away_prob - 0.5) < 0.01:
                    # 用 league 判斷主場優勢強度
                    lg = (features.get('league') or '').upper()
                    home_advantage_map = {
                        'NBA': 0.58,   # NBA 主場勝率約 60%
                        'CPBL': 0.55,  # CPBL 主場勝率約 55-60%
                        'MLB': 0.54,   # MLB 主場勝率約 53-54%
                        'NPB': 0.54,   # NPB 主場勝率約 53%
                    }
                    home_prob = home_advantage_map.get(lg, 0.53)  # 預設 53% (一般主場優勢)
                    away_prob = 1.0 - home_prob
                
                result["home_win_probability"] = round(home_prob, 4)
                result["away_win_probability"] = round(away_prob, 4)

                # 信心指數標準化: 若 Ollama 回傳 0~1 分數則轉換為 1~10 評分
                raw_conf = float(result.get("confidence", 0.0))
                if raw_conf <= 1.0:
                    # 0-1 -> 1-10 映射: 0.0->1, 0.5->5, 1.0->10
                    normalized_conf = max(1, round(raw_conf * 10))
                else:
                    normalized_conf = max(1, min(10, round(raw_conf)))
                result["confidence"] = normalized_conf

                # 🆕 信心度-勝率一致性檢查
                # 若信心度顯示「明顯佔優」(>= 7)，但勝率差距 < 10% (prob_diff < 0.10)
                # 表示信心度過度自信，自動加大勝率差距至符合該信心度的合理範圍
                prob_diff = abs(home_prob - away_prob)
                min_prob_diff_map = {
                    1: 0.00, 2: 0.00, 3: 0.00,
                    4: 0.04, 5: 0.06,    # 信心 4-5：至少有 4-6% 差距
                    6: 0.08,             # 信心 6：至少 8% 差距
                    7: 0.15,             # 信心 7：至少 15% 差距（明顯佔優）
                    8: 0.20,             # 信心 8：至少 20% 差距
                    9: 0.25,             # 信心 9：至少 25% 差距
                    10: 0.30,            # 信心 10：至少 30% 差距
                }
                min_diff = min_prob_diff_map.get(normalized_conf, 0.0)
                if prob_diff + 0.005 < min_diff:  # 🆕 加 0.005 容忍度避免浮點數問題
                    # 強制加大差距：把 favorite 提升到 (0.5 + min_diff/2 + 0.01)，underdog 對應降低
                    if home_prob > away_prob:
                        home_prob = min(0.85, 0.5 + min_diff / 2 + 0.01)
                        away_prob = 1.0 - home_prob
                    elif away_prob > home_prob:
                        away_prob = min(0.85, 0.5 + min_diff / 2 + 0.01)
                        home_prob = 1.0 - away_prob
                    result["home_win_probability"] = round(home_prob, 4)
                    result["away_win_probability"] = round(away_prob, 4)

                # 🆕 校正 predicted_score：確保與勝率一致
                # 若 home_prob > away_prob → home_score 應 > away_score，反之亦然
                # 避免「勝率 65% 但預測比分輸球」這類矛盾
                result["predicted_score"] = self._reconcile_predicted_score(
                    predicted_score=result.get("predicted_score"),
                    home_prob=home_prob,
                    away_prob=away_prob,
                    league=features.get('league', '')
                )

                return result
        
        # Fallback: 若 AI 輸出異常，使用數據計算的替代方案
        print(f"  AI output incomplete, using computed fallback")
        home_form = features.get('home_recent_form', {})
        away_form = features.get('away_recent_form', {})
        home_standings = features.get('home_standings', {})
        away_standings = features.get('away_standings', {})
        
        # 根據勝率計算預測
        home_win_pct = home_standings.get('win_pct', 0.5) if home_standings else 0.5
        away_win_pct = away_standings.get('win_pct', 0.5) if away_standings else 0.5
        
        if home_win_pct + away_win_pct > 0:
            home_prob = home_win_pct / (home_win_pct + away_win_pct)
        else:
            home_prob = 0.5
        
        home_avg_f = home_form.get('avg_goals_for', 0) or 0
        home_avg_a = home_form.get('avg_goals_against', 0) or 0
        away_avg_f = away_form.get('avg_goals_for', 0) or 0
        away_avg_a = away_form.get('avg_goals_against', 0) or 0
        
        h_form_score = home_avg_f / max(home_avg_a, 0.1) if home_avg_a > 0 else home_avg_f
        a_form_score = away_avg_f / max(away_avg_a, 0.1) if away_avg_a > 0 else away_avg_f
        
        total = h_form_score + a_form_score
        home_r = round(h_form_score / total * 10, 1) if total > 0 else 5.0
        away_r = round(a_form_score / total * 10, 1) if total > 0 else 5.0
        
        league = features.get('league', '')
        leauge_dims_map = {
            "MLB": ["球隊整體戰力", "打線火力", "先發投手", "牛棚表現", "主客場因素", "近期狀態"],
            "NBA": ["團隊整體戰力", "進攻效率", "防守強度", "籃板能力", "關鍵球處理", "近期狀態"],
            "FIFA": ["整體戰術實力", "前場進攻", "中場掌控", "後防穩定", "門將表現", "近期狀態"],
        }
        dims = leauge_dims_map.get(league.upper() if league else "", 
                ["整體戰力", "進攻能力", "防守能力", "戰術執行", "環境因素", "近期狀態"])
        
        home_vals = [round(home_r * (1 - i*0.05), 1) for i in range(6)]
        away_vals = [round(away_r * (1 - i*0.05), 1) for i in range(6)]
        
        factors = []
        if home_standings:
            factors.append(f"{features['game_info']['home_team_name']}排名第{home_standings['rank']}")
        if away_standings:
            factors.append(f"{features['game_info']['away_team_name']}排名第{away_standings['rank']}")
        if home_form.get('win_loss'):
            factors.append(f"主隊近期{home_form['win_loss']}")
        if away_form.get('win_loss'):
            factors.append(f"客隊近期{away_form['win_loss']}")
        
        fallback_conf = max(home_prob, 1-home_prob)
        fallback_conf_norm = max(1, min(10, round(fallback_conf * 10)))
        fallback = {
            "home_win_probability": round(home_prob, 4),
            "away_win_probability": round(1 - home_prob, 4),
            "confidence": fallback_conf_norm,
            "key_factors": factors[:4],
            "summary": f"{features['game_info']['home_team_name']} vs {features['game_info']['away_team_name']}："
                       f"主隊近期{home_form.get('win_loss', '數據不足')}，"
                       f"場均{home_avg_f:.1f}分/失{home_avg_a:.1f}分；"
                       f"客隊近期{away_form.get('win_loss', '數據不足')}，"
                       f"場均{away_avg_f:.1f}分/失{away_avg_a:.1f}分。",
            "predicted_score": f"{int(home_avg_f*0.8)}-{int(away_avg_f*0.8)}",
            "radar_chart": {
                "categories": dims,
                "home_team": [min(10, h) for h in home_vals],
                "away_team": [min(10, a) for a in away_vals],
            },
            "home_total_score": round(sum(home_vals)/len(home_vals), 1),
            "away_total_score": round(sum(away_vals)/len(away_vals), 1),
            "source_quality": {
                "score": self.calculate_source_score(),
                "sources": list(self.used_sources)
            }
        }
        return fallback

    def close(self):
        self.cur.close()
        self.conn.close()

if __name__ == "__main__":
    engine = AnalysisEngine()
    engine.cur.execute("SELECT game_id FROM predictx.games WHERE match_date = '2026-06-09' LIMIT 1")
    res = engine.cur.fetchone()
    if res:
        game_id = res['game_id']
        analysis = engine.analyze_game(game_id)
        print(json.dumps(analysis, indent=2, ensure_ascii=False))
    engine.close()