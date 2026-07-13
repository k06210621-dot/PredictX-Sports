import os
import json
import time
import threading
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
import requests

# --- LLM 呼叫速率限制（token bucket）---
# 避免 container 起動初期多場並發打爆 NVIDIA 免費層額度。
# 透過環境變數 LLM_RATE_PER_SEC 調整填補速度（預設 0.4 = 每 2.5 秒 1 次）。
class _TokenBucket:
    def __init__(self, rate, capacity=None):
        self.rate = rate                      # tokens per second
        self.capacity = capacity or max(1.0, rate)
        self.tokens = self.capacity
        self.last = time.monotonic()
        self.lock = threading.Lock()

    def acquire(self, n=1):
        with self.lock:
            now = time.monotonic()
            self.tokens = min(self.capacity, self.tokens + (now - self.last) * self.rate)
            self.last = now
            if self.tokens >= n:
                self.tokens -= n
                return
            wait = (n - self.tokens) / self.rate
        time.sleep(wait)
        with self.lock:
            self.tokens = min(self.capacity, self.tokens - n)

_LLM_RATE = float(os.environ.get("LLM_RATE_PER_SEC", "0.4"))
_llm_bucket = _TokenBucket(_LLM_RATE)

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

# --- 雲端 LLM 配置（支援 NVIDIA / OpenRouter / Groq / Nous Portal / Ollama Cloud）---
# 🆕 預設改為 Ollama Cloud + qwen3-coder-next（CPBL/NPB 分析品質顯著提升）
# 切換方式：透過 Railway 環境變數 CLOUD_LLM_PROVIDER 覆寫
#   - "nvidia"     → NVIDIA NIM API（主要，節省成本）
#   - "nous"       → Nous Portal（備援）
#   - "ollama"     → Ollama Cloud
#   - "groq"       → Groq
#   - "openrouter" → OpenRouter
CLOUD_LLM_PROVIDER = os.environ.get("CLOUD_LLM_PROVIDER", "nvidia")

if CLOUD_LLM_PROVIDER == "openrouter":
    CLOUD_LLM_URL = "https://openrouter.ai/api/v1/chat/completions"
    CLOUD_LLM_MODEL = os.environ.get("CLOUD_LLM_MODEL", "meta-llama/llama-3.3-70b-instruct:free")
    CLOUD_LLM_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
elif CLOUD_LLM_PROVIDER == "groq":
    CLOUD_LLM_URL = "https://api.groq.com/openai/v1/chat/completions"
    CLOUD_LLM_MODEL = os.environ.get("CLOUD_LLM_MODEL", "llama-3.3-70b-versatile")
    CLOUD_LLM_API_KEY = os.environ.get("GROQ_API_KEY", "")
elif CLOUD_LLM_PROVIDER == "nous":
    CLOUD_LLM_URL = "https://inference-api.nousresearch.com/v1/chat/completions"
    CLOUD_LLM_MODEL = os.environ.get("CLOUD_LLM_MODEL", "stepfun/step-3.7-flash:free")
    CLOUD_LLM_API_KEY = os.environ.get("NOUS_API_KEY", "")
elif CLOUD_LLM_PROVIDER == "ollama":
    CLOUD_LLM_URL = "https://api.ollama.com/api/chat"
    CLOUD_LLM_MODEL = os.environ.get("CLOUD_LLM_MODEL", "qwen3-coder-next")
    CLOUD_LLM_API_KEY = os.environ.get("OLLAMA_API_KEY", "")
else:
    # 主模型：deepseek/deepseek-v4-flash via Nous Portal（較不易併發爆量）
    CLOUD_LLM_URL = "https://inference-api.nousresearch.com/v1/chat/completions"
    CLOUD_LLM_MODEL = os.environ.get("CLOUD_LLM_MODEL", "deepseek/deepseek-v4-flash")
    CLOUD_LLM_API_KEY = os.environ.get("NOUS_API_KEY", "")

# 備援 LLM 配置（當主要 LLM 失敗時使用）
# 可透過 Railway 環境變數 FALLBACK_LLM_URL / FALLBACK_LLM_MODEL 覆寫
# 預設：Nous Portal + deepseek/deepseek-v4-flash（與主要模型相同供應商）
FALLBACK_LLM_URL = os.environ.get("FALLBACK_LLM_URL", "https://inference-api.nousresearch.com/v1/chat/completions")
FALLBACK_LLM_MODEL = os.environ.get("FALLBACK_LLM_MODEL", "deepseek/deepseek-v4-flash")
# 備援 API Key 獨立設定，若沒設則沿用主要 NOUS_API_KEY
FALLBACK_LLM_API_KEY = os.environ.get("FALLBACK_LLM_API_KEY", os.environ.get("NOUS_API_KEY", os.environ.get("NVIDIA_API_KEY", "")))

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
            "expert_opinion": 3.0,
            "historical_stats": 4.5,
            "weather": 2.5,
            "computed": 2.0
        }
        self.used_sources = []

    def log_source(self, source_type):
        if source_type in self.source_registry:
            self.used_sources.append(source_type)

    def _execute_query(self, query, params=None):
        """統一查詢執行：帶錯誤處理與日誌"""
        try:
            self.cur.execute(query, params)
            return self.cur.fetchall()
        except Exception as e:
            print(f"  ⚠ DB query error: {e}")
            raise

    def calculate_source_score(self):
        if not self.used_sources:
            return 0.0
        scores = [self.source_registry[s] for s in self.used_sources]
        return round(sum(scores) / len(scores), 2)

    def _compute_team_radar_scores(self, features, side='home'):
        """根據 stats 計算 6 維雷達圖分數（0-10）。
        side: 'home' or 'away'
        MLB 維度順序：球隊整體戰力, 打線火力, 先發投手, 牛棚表現, 主客場因素, 近期狀態
        """
        league = (features.get('league') or '').upper()
        form = features.get(f'{side}_recent_form') or {}
        standings = features.get(f'{side}_standings') or {}
        opponent_form = features.get(f'{"away" if side == "home" else "home"}_recent_form') or {}
        pitcher_data = features.get('mlb_pitchers') or features.get('pitchers') or {}

        avg_for = float(form.get('avg_goals_for') or 0)
        avg_against = float(form.get('avg_goals_against') or 0)
        opp_avg_for = float(opponent_form.get('avg_goals_for') or 0)
        opp_avg_against = float(opponent_form.get('avg_goals_against') or 0)

        win_pct = float(standings.get('win_pct') or 0.5)
        rank = standings.get('rank') or 15

        pitcher = pitcher_data.get(f'{side}_pitcher') or {}
        pitcher_stats = pitcher.get('stats') or {}

        def clamp(v, lo=1.0, hi=10.0):
            return max(lo, min(hi, round(v, 1)))

        def rank_to_score(r):
            # 排名 1 = 10 分，排名 30 = 1 分
            try:
                r = int(r)
                return max(1.0, 11.0 - r * 10.0 / 30.0)
            except Exception:
                return 5.0

        # 近期勝率（W-L 字串 "3-2" → 0.6）
        wl_str = form.get('win_loss') or ''
        recent_winrate = 0.5
        if wl_str and '-' in wl_str:
            try:
                w, l = wl_str.split('-')[:2]
                w = int(w); l = int(l)
                total = w + l
                if total > 0:
                    recent_winrate = w / total
            except Exception:
                pass

        if league in ('MLB', 'NPB', 'CPBL'):
            # 球隊整體戰力：基於勝率（最直接的實力指標）
            team_strength = clamp(win_pct * 10) if win_pct and win_pct > 0 else clamp(rank_to_score(rank))
            # 打線火力：場均得分（棒球常見 3-6 分，2.5→5 分基準）
            offense = clamp((avg_for - 2.5) * 2 + 5)
            # 先發投手：若有 ERA → 低 ERA 高分
            era = pitcher_stats.get('era')
            if era is not None:
                pitcher_score = clamp(10 - (float(era) - 2.5) * 1.5)
            else:
                pitcher_score = clamp(5 + (avg_for - avg_against) * 0.8)
            # 牛棚：用對手場均得分推估（聯盟平均 ~4.5 為基準）
            bullpen = clamp(10 - max(0, opp_avg_for - 4.0) * 1.2)
            # 主客場因素
            home_away = 7.0 if side == 'home' else 5.0
            venue_wr = standings.get('home_win_pct') if side == 'home' else standings.get('away_win_pct')
            if venue_wr is not None:
                home_away = clamp(float(venue_wr) * 10)
            # 近期狀態
            recent = clamp(recent_winrate * 10)
            values = [team_strength, offense, pitcher_score, bullpen, home_away, recent]
        elif league in ('NBA', 'WNBA'):
            # 🏀 籃球六維邏輯（NBA + WNBA 共用）
            team_strength = clamp(win_pct * 10) if win_pct and win_pct > 0 else clamp(rank_to_score(rank))
            offense = clamp((avg_for - 100) * 0.2 + 5)
            defense = clamp(10 - max(0, opp_avg_for - 110) * 0.2)
            clutch = clamp(5 + (avg_for - avg_against) * 0.3)
            home_away = 6.5 if side == 'home' else 5.0
            venue_wr = standings.get('home_win_pct') if side == 'home' else standings.get('away_win_pct')
            if venue_wr is not None:
                home_away = clamp(float(venue_wr) * 10)
            recent = clamp(recent_winrate * 10)
            values = [team_strength, offense, defense, clutch, home_away, recent]
        else:
            team_strength = clamp(win_pct * 10) if win_pct and win_pct > 0 else 5.0
            offense = clamp((avg_for - 2) * 1.5 + 5)
            defense = clamp(10 - max(0, avg_against - 3) * 1.5)
            execution = clamp(5 + (avg_for - avg_against) * 0.5)
            home_away = 6.0 if side == 'home' else 5.0
            recent = clamp(recent_winrate * 10)
            values = [team_strength, offense, defense, execution, home_away, recent]

        return {'values': values}

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
            "WNBA": (70, 110), # WNBA 單隊常見 70-110 分（場均低於 NBA）
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
        home_favorite = home_prob > away_prob

        # 解析原比分為 (home, away)
        if original_score is None:
            # LLM 沒給有效比分，從範圍中位數開始
            mid = (lo + hi) // 2
            original_score = (mid, mid)
        h_score, a_score = original_score

        # 偵測矛盾：favorite 的比分是否 <= underdog（包含平手）
        # 棒球/籃球都沒有平手（棒球延長賽分勝負、籃球 OT 分勝負）
        # 因此 h_score == a_score 也視為矛盾，需修正為「favorite 勝 1 分以上」
        is_tie = (h_score == a_score)
        contradiction = (home_favorite and h_score <= a_score) or (not home_favorite and a_score <= h_score) or is_tie

        if not contradiction:
            # 無矛盾，直接回傳（即使 prob_diff 很小）
            return f"{h_score}-{a_score}"

        # 🆕 [fix] 有矛盾時一律修正，不再因 prob_diff < 0.05 跳過
        # 修正策略：favorite 分數 = max(原分數) + 1，underdog = min(原分數)
        # 若原分數相同（如 2-2），favorite +1
        if h_score == a_score:
            if home_favorite:
                h_score = min(h_score + 1, hi)
            else:
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

        # 🆕 [fix] 根據勝率差距動態調整比分差距
        # prob_diff > 0.4 → favorite 應至少贏 3 分以上
        # prob_diff > 0.2 → 至少 2 分差距
        # prob_diff > 0.1 → 至少 1 分差距
        target_gap = 1
        if prob_diff > 0.4:
            target_gap = 3
        elif prob_diff > 0.2:
            target_gap = 2
        elif prob_diff > 0.1:
            target_gap = 1

        # 確保 favorite_score >= target_gap + lo，否則先提升 favorite
        current_gap = favorite_score - underdog_score
        if current_gap < target_gap:
            # 計算需要多少調整
            deficit = target_gap - current_gap
            # 先提升 favorite_score
            favorite_score = min(hi, favorite_score + deficit)
            # 再降低 underdog_score，但不能低於 lo
            underdog_score = max(lo, underdog_score)
            # 若還不夠，就再降 underdog（但不能低於 lo）
            if favorite_score - underdog_score < target_gap:
                underdog_score = max(lo, favorite_score - target_gap)

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
        #    WNBA 暫不抓進階數據（nba_data_fetcher 專為 NBA API 設計，WNBA 用 ESPN 統計替代）
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

        # 6.5 對 WNBA 賽事：從 basketball-reference.com 抓取進階數據
        if league and league.upper() == 'WNBA':
            try:
                from wnba_data_fetcher import WNBADataFetcher
                fetcher = WNBADataFetcher(conn=self.conn)
                home_name = game['home_team_en']
                away_name = game['away_team_en']
                wnba_data = fetcher.fetch_and_store_game_data(game_id, home_name, away_name)
                if wnba_data:
                    features['wnba_advanced'] = wnba_data
                    for _ in wnba_data.get('sources', []):
                        self.log_source("official_api")
                    h = wnba_data['team_stats']['home']
                    a = wnba_data['team_stats']['away']
                    print(f"  📡 WNBA data: {home_name} OffRtg={h['off_rtg']}/DefRtg={h['def_rtg']}/NRtg={h['net_rtg']}, {away_name} OffRtg={a['off_rtg']}/DefRtg={a['def_rtg']}/NRtg={a['net_rtg']}")
                fetcher.close()
            except Exception as e:
                print(f"  ⚠ WNBA data fetch error: {e}")
        
        # 7. 整合天氣資料（MLB 與 NBA，WNBA 室內為主不抓）
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

        # 7.5 傷兵名單（MLB / NBA / WNBA）
        if league and league.upper() in ('MLB', 'NBA', 'WNBA'):
            try:
                from injury_fetcher import fetch_injuries
                home_name = game['home_team_en']
                away_name = game['away_team_en']
                injuries = fetch_injuries(league, home_name, away_name)
                if injuries.get('home') or injuries.get('away'):
                    features['injuries'] = injuries
                    h_cnt = len(injuries.get('home', []))
                    a_cnt = len(injuries.get('away', []))
                    print(f"  🏥 Injuries: home={h_cnt}, away={a_cnt}")
                else:
                    features['injuries'] = {"home": [], "away": []}
            except Exception as e:
                print(f"  ⚠ Injury fetch error: {e}")
                features['injuries'] = {"home": [], "away": []}

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

                # 🆕 [2026-07-07] 抓 NPB 兩隊前 5 名投手個人 stats（ERA/WHIP/K9）
                # 目的：注入 features['npb_pitchers']，讓 Recipe 6/7 投手 ERA 差距觸發
                try:
                    home_pitchers = fetcher.get_top_starters(home_name, top_n=5) or []
                    away_pitchers = fetcher.get_top_starters(away_name, top_n=5) or []

                    # 🆕 [方案 A] 分析時重新抓 lottonavi 當日先發投手
                    # ingest 階段可能先發尚未公布，分析時重抓可確保拿到最新先發名單
                    today_sp_home = game.get('home_pitcher_name')
                    today_sp_away = game.get('away_pitcher_name')
                    lottonavi_home_era = None
                    lottonavi_away_era = None
                    try:
                        match_date_str = str(game.get('match_date', '')).replace('-', '')
                        if match_date_str:
                            lottonavi_starters = fetcher.get_today_starters(match_date_str)
                            if lottonavi_starters:
                                key1 = f"{home_name}_vs_{away_name}"
                                key2 = f"{away_name}_vs_{home_name}"
                                sp = lottonavi_starters.get(key1)
                                # 🆕 [2026-07-13] 過濾掉 lottonavi 「尚未公布」之類的佔位字串
                                def _lot_pitcher_name(raw_name, fallback):
                                    if not raw_name:
                                        return fallback
                                    stripped = str(raw_name).strip()
                                    if stripped in ('', '尚未公布', '未定', 'TBD', '-', '--', '---'):
                                        return fallback
                                    return raw_name
                                if sp:
                                    today_sp_home = _lot_pitcher_name(sp.get('home_pitcher', {}).get('name'), today_sp_home)
                                    today_sp_away = _lot_pitcher_name(sp.get('away_pitcher', {}).get('name'), today_sp_away)
                                    lottonavi_home_era = sp.get('home_pitcher', {}).get('era')
                                    lottonavi_away_era = sp.get('away_pitcher', {}).get('era')
                                elif key2 in lottonavi_starters:
                                    sp = lottonavi_starters[key2]
                                    today_sp_home = _lot_pitcher_name(sp.get('away_pitcher', {}).get('name'), today_sp_home)
                                    today_sp_away = _lot_pitcher_name(sp.get('home_pitcher', {}).get('name'), today_sp_away)
                                    lottonavi_home_era = sp.get('away_pitcher', {}).get('era')
                                    lottonavi_away_era = sp.get('home_pitcher', {}).get('era')
                                print(f"  🏯 NPB lottonavi 即時先發: {home_name}={today_sp_home}, {away_name}={today_sp_away}")
                    except Exception as lot_err:
                        print(f"  ⚠ NPB lottonavi re-fetch error: {lot_err}")

                    # 🆕 直接使用 lottonavi 先發投手數據（不再比對 baseball-data.com）
                    # lottonavi 已提供先發名字 + ERA，比對常因日文姓名寫法差異失敗
                    home_sp_stats = {'era': lottonavi_home_era} if lottonavi_home_era else None
                    away_sp_stats = {'era': lottonavi_away_era} if lottonavi_away_era else None

                    if home_pitchers or away_pitchers:
                        features['npb_pitchers'] = {
                            'home_team': home_name,
                            'away_team': away_name,
                            'home_pitchers': home_pitchers,
                            'away_pitchers': away_pitchers,
                            'home_pitcher': {
                                'name': today_sp_home or (home_pitchers[0]['name'] if home_pitchers else 'TBD'),
                                'stats': home_sp_stats or (home_pitchers[0] if home_pitchers else {}),
                            },
                            'away_pitcher': {
                                'name': today_sp_away or (away_pitchers[0]['name'] if away_pitchers else 'TBD'),
                                'stats': away_sp_stats or (away_pitchers[0] if away_pitchers else {}),
                            },
                        }
                        h_disp = home_sp_stats or (home_pitchers[0] if home_pitchers else {})
                        a_disp = away_sp_stats or (away_pitchers[0] if away_pitchers else {})
                        h_name = features['npb_pitchers']['home_pitcher']['name']
                        a_name = features['npb_pitchers']['away_pitcher']['name']
                        print(f"  ⚾ Home SP: {h_name} (ERA={h_disp.get('era', 0)}) [lottonavi{' ✓' if home_sp_stats else ' fallback'}]")
                        print(f"  ⚾ Away SP: {a_name} (ERA={a_disp.get('era', 0)}) [lottonavi{' ✓' if away_sp_stats else ' fallback'}]")
                except Exception as pitcher_err:
                    print(f"  ⚠ NPB top starters fetch error: {pitcher_err}")

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

        # 8.5 球員資料注入（適用所有有球員資料的聯盟：MLB/NBA/WNBA/CPBL/NPB）
        if league and league.upper() in ('MLB', 'NBA', 'WNBA', 'CPBL', 'NPB'):
            try:
                home_team_id = game['home_team_id']
                away_team_id = game['away_team_id']

                self.cur.execute("""
                    SELECT p.player_id, p.player_name, p.position, p.jersey_number, pt.team_id
                    FROM predictx.players p
                    JOIN predictx.player_teams pt ON p.player_id = pt.player_id
                    WHERE (pt.team_id = %s OR pt.team_id = %s) AND pt.is_active = true
                    ORDER BY pt.team_id, p.position
                """, (home_team_id, away_team_id,))
                rows = self.cur.fetchall() or []
                if rows:
                    home_players = [dict(r) for r in rows if str(r['team_id']) == str(home_team_id)]
                    away_players = [dict(r) for r in rows if str(r['team_id']) == str(away_team_id)]
                    features['roster'] = {
                        'home': home_players,
                        'away': away_players,
                    }
                    print(f"  👥 {league} roster: home={len(home_players)}, away={len(away_players)}")
            except Exception as e:
                print(f"  ⚠ {league} roster fetch error: {e}")
        
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

            # CPBL 今日先發投手（從 cpbl.com.tw 官網 API）— 獨立區塊，不受上方 try 影響
            try:
                from cpbl_data_fetcher import CPBLDataFetcher
                fetcher2 = CPBLDataFetcher()
                # 重新從 game dict 取得隊名（主 try 區塊可能已失敗）
                sp_home_name = game.get('home_team_en', '')
                sp_away_name = game.get('away_team_en', '')
                match_date = game.get('match_date')
                cpbl_starters = fetcher2.get_today_starting_pitchers(match_date)
                if cpbl_starters:
                    features['cpbl_starting_pitchers'] = cpbl_starters
                    h_sp = cpbl_starters.get(sp_home_name, {})
                    a_sp = cpbl_starters.get(sp_away_name, {})
                    h_name = h_sp.get('name', 'TBD') if h_sp else 'TBD'
                    a_name = a_sp.get('name', 'TBD') if a_sp else 'TBD'
                    print(f"  🏆 CPBL starting pitchers: {sp_home_name}={h_name}, {sp_away_name}={a_name}")

                    # 寫回 games 表，讓 API 端點 /api/games 回傳先發投手名稱
                    try:
                        self.cur.execute(
                            """UPDATE predictx.games
                               SET home_pitcher_name = %s,
                                   away_pitcher_name = %s
                               WHERE game_id = %s""",
                            (h_name, a_name, game_id)
                        )
                        self.conn.commit()
                    except Exception as db_err:
                        print(f"  ⚠ CPBL pitcher DB write error: {db_err}")
                fetcher2.close()
            except Exception as e:
                print(f"  ⚠ CPBL starting pitcher fetch error: {e}")
        
        return features

    def generate_win_probability_prompt(self, features):
        """
        構建勝率預測的 Prompt（強化版：注入真實數據 + Chain-of-Thought + rolling accuracy）
        """
        game = features['game_info']
        home_team = game['home_team_name']
        away_team = game['away_team_name']
        league = features['league']

        # 🆕 [2026-06-24] 取得最近 30 場 AI 命中率（讓 LLM 自我校正）
        # 若樣本 < 10 不注入（避免誤導）
        rolling_accuracy_str = ""
        try:
            self.cur.execute(
                """
                WITH ranked AS (
                    SELECT is_hit, prediction_time,
                           ROW_NUMBER() OVER (ORDER BY prediction_time DESC) AS rn
                    FROM predictx.ai_prediction_history
                    WHERE league = %s
                      AND is_hit IS NOT NULL
                )
                SELECT 
                  COUNT(*) AS total,
                  SUM(CASE WHEN is_hit THEN 1 ELSE 0 END) AS hits
                FROM ranked
                WHERE rn <= 30
                """,
                (league.upper(),)
            )
            row = self.cur.fetchone()
            # RealDictCursor 用 row['key'] 不用 row[0]
            total = int(row['total']) if row and row.get('total') else 0
            hits = int(row['hits']) if row and row.get('hits') else 0
            if total >= 10:
                rolling_acc = hits / total
                rolling_accuracy_str = f"""

═══════════════════════════════════════
📈 AI 自我校驗資訊（資料飛輪）
═══════════════════════════════════════
本聯盟 ({league}) 近 30 場 AI 預測命中率：**{rolling_acc*100:.1f}%**（{hits}/{total} 場）
- 若命中率 > 60%：模型目前狀態良好，請保持信心（confidence 可稍微提高）
- 若命中率 < 50%：模型可能過度自信，請下修 confidence 並重新校驗
- 此資訊是實際結算回饋，用於資料飛輪自我調整
"""
        except Exception as e:
            # 失敗不影響主流程
            print(f"  ⚠ rolling accuracy fetch failed (non-fatal): {e}")
            rolling_accuracy_str = ""
        
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

        # 🆕 注入 TheSportsDB 增強資料（逐局比分 + 球場特性 + 投手名單）
        try:
            from thesportsdb_enricher import get_enricher
            enricher = get_enricher()
            tdb_section = enricher.build_innings_analysis_section(home_team, away_team)

            # 🆕 [CPBL/NPB/NBA] 投手資料（基於 TheSportsDB 球員名單）
            # MLB 已用 mlb_pitcher_stats 處理，這是 fallback for 其他聯盟
            league = features.get('league', '')
            team_ids = features.get('team_ids', {})
            if league in ('CPBL', 'NPB', 'NBA') and not features.get('mlb_pitchers'):
                if home_id := team_ids.get('home'):
                    tdb_section += enricher.build_pitcher_quality_section(league, str(home_id))
                if away_id := team_ids.get('away'):
                    tdb_section += enricher.build_pitcher_quality_section(league, str(away_id))

            tdb_section += enricher.build_venue_section(home_team, away_team)
        except Exception as _e:
            import logging as _logging
            _logging.getLogger(__name__).warning(f"TheSportsDB enricher failed (skip): {_e}")
            tdb_section = ""

        # 🆕 注入本地球員資料 (CPBL roster + NPB qualified stats)
        try:
            from local_player_enricher import (
                build_cpbl_roster_section,
                build_npb_qualified_section,
                cpbl_team_to_code,
                npb_team_name_to_league_and_code,
            )
            league = features.get('league', '')

            if league == 'CPBL':
                # 用 home_team/away_team 中文名找 CPBL 球隊代碼
                home_code = cpbl_team_to_code(home_team) if home_team else None
                away_code = cpbl_team_to_code(away_team) if away_team else None
                if home_code:
                    tdb_section += build_cpbl_roster_section(home_code, "home")
                if away_code:
                    tdb_section += build_cpbl_roster_section(away_code, "away")

            elif league == 'NPB':
                # 兩隊的聯盟可能不同，分別注入
                home_lc = npb_team_name_to_league_and_code(home_team) if home_team else None
                away_lc = npb_team_name_to_league_and_code(away_team) if away_team else None
                leagues_to_include = set()
                if home_lc:
                    leagues_to_include.add(home_lc[0])
                if away_lc:
                    leagues_to_include.add(away_lc[0])
                for lg in leagues_to_include:
                    tdb_section += build_npb_qualified_section(lg)
        except Exception as _e:
            import logging as _logging
            _logging.getLogger(__name__).warning(f"Local player enricher failed (skip): {_e}")

        
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
- **【強制規則】當近 3 場 ERA 與整季 ERA 差距 ≥ 3.0 時，必須以「近 3 場」為主要預測依據，整季數據僅供參考**
- **【強制規則】若近 3 場被打爆（ERA > 6.0），即使整季 ERA 漂亮，下場該球隊勝率應下修至少 5-10%**
- **【強制規則】若近 3 場極佳（ERA < 2.0），即使整季普通，下場該球隊勝率應上修至少 3-5%**
- **【強制規則】summary 中必須明確寫出「近 3 場 ERA vs 整季 ERA」的對比數字**
- 投手明顯「降溫中」的徵兆：近 3 場被打全壘打數增加、WHIP > 1.5、被安打率上升
- 投手明顯「升溫中」的徵兆：近 3 場 K/9 > 10、WHIP < 1.0、對手打擊率 < .220

**⚾ 關鍵指標提醒：先發投手的 K/9（三振能力）與 BB/9（保送控制）/ K/BB 比值，往往是 MLB 比賽勝負的決定性因素。請優先根據 K/9 + BB/9 對位差距判斷投手優勢，再疊加團隊戰績與打線數據；若投手對位懸殊，即使團隊戰績落後，仍可能由先發投手主導比賽走向。**
"""

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

        # WNBA 進階數據（從 basketball-reference.com 爬取）
        wnba_advanced = features.get('wnba_advanced', {})
        if wnba_advanced:
            h = wnba_advanced['team_stats']['home']
            a = wnba_advanced['team_stats']['away']
            wnba_advanced_section = f"""===== WNBA 進階數據（來源：espn.com）=====
主隊 {home_team}:
  戰績: {h['wins']}W-{h['losses']}L, 勝率: {h['win_pct']:.1%}, 種子: {h.get('playoff_seed','?')}
  場均得分: {h['pts_per_g']:.1f}, 場均失分: {h['opp_pts_per_g']:.1f}, 淨勝分: {h['differential']:+.1f}
  主場戰績: {h.get('home_record','?')} ({h.get('home_win_pct', 0):.1%})
  客場戰績: {h.get('road_record','?')} ({h.get('road_win_pct', 0):.1%})
  連勝/敗: {h.get('streak','?')}
  投籃: FG%={h.get('fg_pct', 0):.1%}, 3P%={h.get('three_pt_pct', 0):.1%}, FT%={h.get('ft_pct', 0):.1%}
  進階: TS%={h.get('ts_pct', 0):.1%}, eFG%={h.get('efg_pct', 0):.1%}, TOV%={h.get('tov_pct', 0):.1%}
  團隊: AST/TO={h.get('ast_to_tov', 0):.2f}, OREB={h.get('oreb_per_g', 0):.1f}, DREB={h.get('dreb_per_g', 0):.1f}, STL={h.get('stl_per_g', 0):.1f}, BLK={h.get('blk_per_g', 0):.1f}

客隊 {away_team}:
  戰績: {a['wins']}W-{a['losses']}L, 勝率: {a['win_pct']:.1%}, 種子: {a.get('playoff_seed','?')}
  場均得分: {a['pts_per_g']:.1f}, 場均失分: {a['opp_pts_per_g']:.1f}, 淨勝分: {a['differential']:+.1f}
  主場戰績: {a.get('home_record','?')} ({a.get('home_win_pct', 0):.1%})
  客場戰績: {a.get('road_record','?')} ({a.get('road_win_pct', 0):.1%})
  連勝/敗: {a.get('streak','?')}
  投籃: FG%={a.get('fg_pct', 0):.1%}, 3P%={a.get('three_pt_pct', 0):.1%}, FT%={a.get('ft_pct', 0):.1%}
  進階: TS%={a.get('ts_pct', 0):.1%}, eFG%={a.get('efg_pct', 0):.1%}, TOV%={a.get('tov_pct', 0):.1%}
  團隊: AST/TO={a.get('ast_to_tov', 0):.2f}, OREB={a.get('oreb_per_g', 0):.1f}, DREB={a.get('dreb_per_g', 0):.1f}, STL={a.get('stl_per_g', 0):.1f}, BLK={a.get('blk_per_g', 0):.1f}"""
        else:
            wnba_advanced_section = ""
        

        # 🆕 WNBA 主力球員（從 2026-07-12 開始，使用團隊估算數據）
        wnba_top_players = wnba_advanced.get('top_players', {}) if wnba_advanced else {}
        if wnba_top_players:
            home_players = wnba_top_players.get('home', [])
            away_players = wnba_top_players.get('away', [])
            
            if home_players or away_players:
                def fmt_wnba_players(players, team_name):
                    if not players:
                        return f"{team_name}: 無球員數據"
                    line_items = []
                    for i, p in enumerate(players[:5], 1):
                        name = p.get('name', '?')
                        pts = p.get('pts', 0)
                        reb = p.get('reb', 0)
                        ast = p.get('ast', 0)
                        fg_pct = p.get('fg_pct')
                        fg_str = f"{fg_pct:.1%}" if fg_pct and fg_pct > 0 else '?.?%'
                        line_items.append(f"    #{i} {name}: PTS={pts:.1f}, REB={reb:.1f}, AST={ast:.1f}, FG%={fg_str}")
                    return "\n".join(line_items)

                wnba_advanced_section += """

===== 主力球員 Top 5（團隊估算，依 PTS 排序）=====
主隊 """ + home_team + """:
""" + fmt_wnba_players(home_players, home_team) + """

客隊 """ + away_team + """:
""" + fmt_wnba_players(away_players, away_team) + """

💡 註：WNBA ESPN API 不提供球員數據，此為主隊/客隊主力球員的估算值（基於團隊 PPG 分配）。"""
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
        
        # 🏥 傷兵名單段落
        injury_data = features.get('injuries', {})
        if injury_data and (injury_data.get('home') or injury_data.get('away')):
            def _format_injury_list(players):
                if not players:
                    return "無傷兵"
                lines = []
                for p in players:
                    pos = f" [{p['position']}]" if p.get('position') else ""
                    desc = f" — {p['desc']}" if p.get('desc') else ""
                    lines.append(f"  • {p['name']}{pos} ({p['status']}){desc}")
                return "\n".join(lines)

            injury_section = f"""===== 傷兵名單（來源：{'MLB statsapi' if league.upper() == 'MLB' else 'ESPN'}）=====
主隊 {home_team} 傷兵:
{_format_injury_list(injury_data.get('home', []))}

客隊 {away_team} 傷兵:
{_format_injury_list(injury_data.get('away', []))}

💡 分析指引：
- 先發投手若在傷兵名單中，該隊勝率應明顯下修（IL10: -5%，IL15: -8%，IL60: -10%）
- 核心打者（主力先發）缺陣影響較大，替補球員缺陣影響較小
- Day-To-Day 不確定性高，保守估計勝率下修 2-3%
- 若兩隊都有傷兵，請比較「誰的傷兵對戰力影響更大」再決定調整方向
"""
        else:
            injury_section = ""
        
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

            # 🆕 加入主力打者 Top 5（從 2026-07-12 開始）
            top_batters = npb_data.get('top_batters', {})
            home_batters = top_batters.get('home', [])
            away_batters = top_batters.get('away', [])

            if home_batters or away_batters:
                def fmt_batters(batters, team_name):
                    if not batters:
                        return f"{team_name}: 無球員數據"
                    lines = []
                    for i, b in enumerate(batters, 1):
                        name = b.get('name', '?')
                        avg = b.get('avg')
                        hr = b.get('hr', 0)
                        rbi = b.get('rbi', 0)
                        avg_str = f"{avg:.3f}" if avg else "N/A"
                        lines.append(f"    #{i} {name}: AVG={avg_str}, HR={hr}, RBI={rbi}")
                    return "\n".join(lines)

                npb_section += """

===== 主力打者 Top 5（依 RBI 排序）=====
主隊 """ + home_team + """:
""" + fmt_batters(home_batters, home_team) + """

客隊 """ + away_team + """:
""" + fmt_batters(away_batters, away_team) + """
"""

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

        # 🆕 [2026-07-06] 今日先發投手（從 games 表讀取 lottonavi 抓到的 SP 姓名）
        # 比 npb_starters 輪值更精準 — lottonavi 知道「今天誰先發」
        home_sp = game.get('home_pitcher_name')
        away_sp = game.get('away_pitcher_name')
        if home_sp or away_sp:
            npb_section += f"""

===== 今日先發投手（來源：lottonavi）=====
主隊 {home_team} 今日先發：{home_sp or '尚未公布'}
客隊 {away_team} 今日先發：{away_sp or '尚未公布'}

💡 NPB 分析指引【強制規則】：
- **先發投手的三振能力(K/9)與保送控制(BB/9、K/BB)是 NPB 低得分比賽的「勝負關鍵指標」，權重應明顯高於團隊戰績/排名。**
- 當雙方先發 K/9 差距 ≥ 2.0，或 BB/9 差距 ≥ 1.0，或 K/BB 比值差距 ≥ 1.0 時，勝率應直接朝「三振能力強、保送少」的一方偏移至少 3-5%。
- summary 中必須明確寫出雙方先發的 K/9 與 BB/9 對比數字，並說明其對勝負的影響。"""

        # 🆕 [2026-07-06] NPB 當日 SP 個人 stats（從 predictx.player_season_stats）
        # 這是 lottonavi 抓出「指定先發投手」後，從 DB 撈這位投手的當季 ERA/SO/BB
        # 比 npb_starters 輪值更精準 — 因為 lottonavi 知道「今天誰先發」

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
            "WNBA": ["團隊整體戰力", "進攻效率", "防守強度", "籃板能力", "關鍵球處理", "近期狀態"],
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
        elif "WNBA" in league_upper_check:
            home_advantage_note = "\n- WNBA 主場優勢顯著：歷史主場勝率約 58-60%，與 NBA 接近。對實力接近的對戰，主場球隊勝率應明顯 > 0.5。"
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
            cpbl_spec += "- 對戰組合的歷史交手紀錄（H2H）在中職有較高參考價值\n"
            cpbl_spec += "\n**⚾ 關鍵指標提醒：先發投手的 K/9（三振能力）與 BB/9（保送控制）/ K/BB 比值，是中職勝負關鍵指標。中職洋將投手常主導戰局，請優先根據 K/9 + BB/9 對位差距判斷投手優勢，權重應高於團隊戰績。**\n"

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

            # 🆕 [2026-07-06] CPBL 當日 SP 個人 stats（從 predictx.player_season_stats）
            if (game.get('home_pitcher_name') or game.get('away_pitcher_name')):
                cpbl_sp_names = [game.get('home_pitcher_name'), game.get('away_pitcher_name')]
                cpbl_sp_names = [n for n in cpbl_sp_names if n and n != '尚未公布' and n != 'TBD']
                if cpbl_sp_names:
                    try:
                        self.cur.execute(f"""
                            SELECT p.player_name, pss.kind, pss.era, pss.w, pss.l, pss.sv, pss.hld, pss.ip,
                                   pss.p_h, pss.p_r, pss.p_er, pss.p_hr, pss.p_bb, pss.p_hbp, pss.p_so,
                                   pss.avg, pss.obp, pss.slg, pss.g, pss.pa, pss.ab, pss.b_r, pss.b_h,
                                   pss.tb, pss.rbi, pss.sb, pss.b_hr, pss.b_bb, pss.b_hbp, pss.b_so,
                                   t.english_name
                            FROM predictx.player_season_stats pss
                            JOIN predictx.players p ON pss.player_id = p.player_id
                            JOIN predictx.player_teams pt ON p.player_id = pt.player_id
                            JOIN predictx.teams t ON pt.team_id = t.team_id
                            WHERE pss.season = 2026
                              AND pss.source = 'sportify_tw'
                              AND t.league = 'CPBL'
                              AND pt.is_active = true
                              AND (
                                {' OR '.join(['p.player_name ILIKE %s' for _ in cpbl_sp_names])}
                              )
                        """, [f'%{n}%' for n in cpbl_sp_names])
                        sp_rows = self.cur.fetchall() or []
                        if sp_rows:
                            sp_lines = []
                            for r in sp_rows:
                                if isinstance(r, dict):
                                    pname = r.get('player_name')
                                    team = r.get('english_name', '')
                                    kind = r.get('kind')
                                    if kind == 'pitcher':
                                        era = r.get('era', 0) or 0
                                        w = r.get('w', 0) or 0
                                        l = r.get('l', 0) or 0
                                        sv = r.get('sv', 0) or 0
                                        hld = r.get('hld', 0) or 0
                                        ip = r.get('ip', 0) or 0
                                        p_so = r.get('p_so', 0) or 0
                                        p_bb = r.get('p_bb', 0) or 0
                                        p_hr = r.get('p_hr', 0) or 0
                                        p_h = r.get('p_h', 0) or 0
                                        k9 = (p_so * 9 / ip) if ip else 0
                                        bb9 = (p_bb * 9 / ip) if ip else 0
                                        whip = ((p_h + p_bb) / ip) if ip else 0
                                        sp_lines.append(
                                            f"  投手 {pname} ({team}): ERA={era:.2f}, {w}勝-{l}敗-{sv}SV-{hld}HLD, "
                                            f"IP={ip}, SO={p_so}, BB={p_bb}, HR={p_hr}, "
                                            f"K/9={k9:.1f}, BB/9={bb9:.1f}, WHIP={whip:.2f}"
                                        )
                                    else:
                                        avg = r.get('avg', 0) or 0
                                        obp = r.get('obp', 0) or 0
                                        slg = r.get('slg', 0) or 0
                                        b_hr = r.get('b_hr', 0) or 0
                                        b_rbi = r.get('rbi', 0) or 0
                                        sp_lines.append(
                                            f"  打者 {pname} ({team}): AVG={avg:.3f}, OBP={obp:.3f}, SLG={slg:.3f}, "
                                            f"HR={b_hr}, RBI={b_rbi}"
                                        )
                            if sp_lines:
                                cpbl_spec += "\n\n===== CPBL 球員個人數據（來源：sportify.tw）=====\n" + "\n".join(sp_lines)
                                self.log_source("official_api")
                                print(f"  📊 CPBL SP stats: {len(sp_lines)} players from DB")
                    except Exception as e:
                        print(f"  ⚠ CPBL player stats fetch error: {e}")

            # CPBL 今日先發投手（優先用 game 字典的 lottonavi/手動資料，其次用 cpbl.com.tw 抓取資料）
            cpbl_starters = features.get('cpbl_starting_pitchers', {}) or {}
            home_sp = game.get('home_pitcher_name') or (cpbl_starters.get(home_team, {}).get('name') if cpbl_starters else None) or 'TBD'
            away_sp = game.get('away_pitcher_name') or (cpbl_starters.get(away_team, {}).get('name') if cpbl_starters else None) or 'TBD'
            print(f"  🔍 [CPBL SP] game.home_pitcher_name={game.get('home_pitcher_name')!r} game.away_pitcher_name={game.get('away_pitcher_name')!r} → home_sp={home_sp!r} away_sp={away_sp!r}")
            if home_sp != 'TBD' or away_sp != 'TBD':
                cpbl_spec += f"\n\n===== 今日先發投手（來源：games 表）====="
                cpbl_spec += f"\n主隊 {home_team} 先發：{home_sp}"
                cpbl_spec += f"\n客隊 {away_team} 先發：{away_sp}"

            cpbl_analysis_guide = "\n===== " + cpbl_spec + "\n\n請根據以上 CPBL 特性，結合提供的數據進行分析。\n"

        # 球員名單注入（適用 MLB/NBA/WNBA/CPBL，通用化）
        rostersection = ""
        if league and league.upper() in ('MLB', 'NBA', 'WNBA', 'CPBL', 'NPB') and features.get('roster'):
            roster = features['roster']
            h_players = roster.get('home', [])
            a_players = roster.get('away', [])

            def _fmt_roster(players, limit=6):
                lines = []
                for p in players[:limit]:
                    pos = p.get('position') or '?'
                    name = p.get('player_name') or 'Unknown'
                    jersey = p.get('jersey_number') or '?'
                    lines.append(f"  #{jersey} {pos}: {name}")
                if not lines:
                    return "  (名單待補)"
                return "\n".join(lines)

            # 棒球 vs 籃球用不同位置說明
            if league.upper() in ('WNBA', 'NBA'):
                pos_hint = "（位置 F=前鋒, G=後衛, C=中鋒）"
            else:
                pos_hint = "（投手位置: SP=先發, RP=後援, CL=終結者）"

            rostersection = (
                f"\n===== {league} 球員名單（用於 AI 摘要提及主力近況）=====\n"
                f"主隊 {home_team} 名單（{len(h_players)}人）:\n{_fmt_roster(h_players)}\n"
                f"客隊 {away_team} 名單（{len(a_players)}人）:\n{_fmt_roster(a_players)}\n"
                f"{pos_hint}\n"
            )

        # 🆕 [2026-06-24] 聯盟主場優勢常數（依歷史統計資料）
        league_home_adv_const = {
            "MLB": 0.030,   # 主力棒球歷史主場勝率約 53%
            "NPB": 0.030,   # 日本職棒類似 MLB
            "CPBL": 0.050,  # 中職較高（球迷文化）
            "NBA": 0.080,   # NBA 主場勝率約 60%
        }
        league_home_adv = league_home_adv_const.get((league or "").upper(), 0.030)

        # 🆕 [2026-07-06] 信心理量規則（優化：明確化標準）
        # 重點：給出具體的數值門檻（戰績差距、淨勝分差、投手對位差）讓 LLM 不會過度保守
        confidence_calibration = """
**Confidence 評分準則（依「客觀數據差距」決定）**：

- **1-3**: 數據嚴重不足或兩隊實力極為接近（戰績差距 < 5 場 或 勝率差 < 5%），推論機率可能僅 50-55%。

- **4-5**: 有基本數據但仍有重大不確定因素。例如：
  - 戰績差距 5-10 場（勝率差 5-10%）
  - 先發投手尚未公布
  - 預期驗證率 55-60%

- **6（推薦範圍）**: 數據明確顯示一方略佔優。**任一**條件成立即可：
  - 戰績差距 10-20 場（勝率差 10-20%）
  - 淨勝分差異 ≥ 3 分/場
  - 先發投手對位明顯（例: 4.0 ERA vs 6.5 ERA）
  - 預期驗證率 60-65%
  - ⚠️ **不要低於 6**：當雙方至少有一個明確差異時，6 是合理基線
- **7**: 數據顯示一方明顯佔優。需至少**兩個**上述條件成立：
  - 例如：戰績差 15 場 + 淨勝分差 4 分
  - 預期驗證率 70-75%

- **8**: 數據強烈支持一方（投手實力差距大、戰績懸殊 20+ 場、淨勝分差 6+）：
  - 預期驗證率 80-85%

- **9**: 極高把握（如 ace 對弱投，戰績差 25+ 場）：
  - 預期驗證率 85-90%

- **10**: 史詩級優勢，僅限極少數情況（幾乎不打）。

**重要提醒**：
- 信心 6+ 是「基線」而非「上限」——當數據明確支持時應大膽給 6-7
- 信心 8+ 仍需「多項指標」都明顯支持才給
- 請根據「數據差距的實際幅度」評分，不要預設立場偏向保守
"""

        # 🆕 [2026-06-24] 主場優勢說明（豐富版，含數字）
        home_advantage_full = f"""
| 聯盟 | 歷史主場勝率 | 換算係數 | 本場幅度 |
|------|-------------|---------|---------|
| MLB  | ~53-54%      | +{league_home_adv_const['MLB']:.3f} | 實力接近時主隊 0.51-0.55 |
| NPB  | ~53-55%      | +{league_home_adv_const['NPB']:.3f} | 接近性同上  |
| CPBL | ~55-60%      | +{league_home_adv_const['CPBL']:.3f} | 主隊優勢更明顯 |
| NBA  | ~60%         | +{league_home_adv_const['NBA']:.3f} | NBA 主場優勢最顯著 |

**用法**：在 Step 4 計算 home_win_probability 時，加上一個基準 0.50 後，須額外加上該聯盟的主場係數（{league_home_adv:.3f}）。
範例：若加權平均後是 0.50 + 0.05 (主場優勢) = 0.55，最終值為 0.55（若接近則微調至 0.52-0.58 區間）。
禁止：忽視主場優勢導致客隊勝率 > 主隊勝率 (五五波對戰時)。
"""

        prompt = f'''
你是一位專業運動數據分析師。你的任務是用結構化的方式分析比賽，並輸出**機器可解析的 JSON**。

═══════════════════════════════════════
⚡ 重要：分析流程（Chain-of-Thought）
═══════════════════════════════════════
請**嚴格依序**完成以下推理，不要跳步：

**Step 1 — 數據盤點 (Data Audit)**
列出資料完整度：哪些關鍵數據可用、哪些缺失。
若棒球聯盟（MLB/NPB/CPBL）缺少先發投手資料，請在 confidence 自動降 2 級。
若籃球聯盟（NBA/WNBA）缺少任一隊伍進階戰績（戰績、PPG、近況），請在 confidence 自動降 1 級。

**Step 2 — 雙方對比 (Head-to-Head Comparison)**
將下列六大維度的雙方數據並排比較，每項給一個差值（正值=主隊有利）：
- {json.dumps(current_dims, ensure_ascii=False)}

**Step 3 — 關鍵因子識別 (Key Factor Identification)**
從 Step 2 中挑出 4-6 個**決定性因子**，每個給「權重 0-1」。
權重總和 = 1.0（強制）。
例：投手對位 0.35 + 主場優勢 0.15 + 近期狀態 0.20 + ...

**Step 4 — 機率綜合 (Probability Aggregation)**
根據 Step 3 的因子權重**綜合判斷** home_win_probability：
- **不要機械式套用任何公式**——請根據 Step 2 的實質數據對比與 Step 3 的因子權重，自行權衡
- 起點 0.50（五五波基準）
- **主場優勢請以 Step 2 的實際對比為主，不要因「主場」一詞就額外加分**
  - 對手實力明顯較弱 → 主場效應可加 0.03-0.05
  - 對手實力明顯較強 → 主場效應可忽略甚至逆轉
  - 雙方實力接近 → 主場效應 +0.02 ~ +0.04 微調
- 最終值限制在 [0.20, 0.80] 區間（避免極端）
- **重要**：若 Step 2 顯示客隊明顯佔優（如對手戰績、投手、打線都更好），即使主隊有主場，home_win_probability 也應 < 0.45
- away_win_probability = 1 - home_win_probability

**Step 5 — 信心理量 (Confidence Calibration)**
依下列規則**真實**評估 confidence：
{confidence_calibration}

**Step 6 — 預測比分 (Score Prediction)**
依 home_win_probability 反推合理比分範圍：
- 0.55-0.60 → 接近比分（±1 分）
- 0.60-0.70 → 較明確差距
- 0.70+ → 大比分領先

═══════════════════════════════════════
📊 數據輸入 (Data Inputs)
═══════════════════════════════════════

【比賽資訊】
- 聯賽: {league}
- 主場: {home_team}
- 客場: {away_team}

【主隊 {home_team}】
聯盟排名: {home_standings}
{home_form}

【客隊 {away_team}】
聯盟排名: {away_standings}
{away_form}

【對陣歷史】
{matchup}


【進階數據：球員/投手/球場】
{tdb_section}
{mlb_advanced_section}
{nba_advanced_section}
{wnba_advanced_section}
{npb_section}
{weather_section}
{injury_section}
{cpbl_analysis_guide}
{home_advantage_note}
{rostersection}

═══════════════════════════════════════
🎯 主場優勢與聯盟特性
═══════════════════════════════════════
{home_advantage_full}
{rolling_accuracy_str}

═══════════════════════════════════════
⚖️ Compliance 與格式要求
═══════════════════════════════════════

【合規用語 (強制遵守)】
- 禁止：「預測獲勝」「預測比分」「贏 X 分以上」「下注」「賠率」「賭博」「投注」
- 用語替代：「模型推演」「領先 X 分以上推演機率」「分析顯示」
- 「球隊勝率」(歷史戰績) 可保留，AI 推論結果禁止「預測勝率」字眼

【JSON 格式強制規則】
1. 只輸出有效 JSON，不要有任何其他文字、markdown、註解
2. home_win_probability + away_win_probability = 1.0
3. **不允許 0.50/0.50 五五波**：必須根據數據明確判斷（即使微幅偏差也要給 0.51 或 0.52）
4. **禁止系統性傾向主隊**：如果所有場次都給主隊較高勝率，請重新檢視是否機械式套用主場優勢。應該根據對戰實力強弱決定傾向，而非「主場 = 加分」單一邏輯
5. **禁止系統性傾向客隊**：實力接近時主隊勝率應在 0.52-0.55 區間（但若客隊數據明顯較強，請直接給客隊較高勝率，不要硬湊主場優勢）
6. predicted_score 必須是具體字串如 "3-2"，不可是 "N/A" 或空值
7. radar_chart 必須有 6 個 categories 和對應 6 個數值（0-10），不得為空
8. key_factors 至少 4 個，**每個必須包含具體數字/球員名/百分比**

【反偏差自檢 (Anti-Bias Self-Check)】
完成分析後，請自我檢查：
- 若本場預測主隊勝率 > 0.55，但 Step 2 的實質數據（戰績、投手、打線）顯示客隊佔優 → 請重新評估
- 若本場預測主隊勝率 < 0.45，但主隊實際有明顯數據優勢 → 請重新評估
- 正確的方向：主隊勝率應**反映數據對比**，而非反映「主場 = 加分」的口號

═══════════════════════════════════════
📋 輸出模板（嚴格遵守 keys 順序）
═══════════════════════════════════════

{{
  "reasoning": {{
    "step1_data_audit": "資料完整度評估（30字內）",
    "step2_comparison": "六維度主隊優勢摘要（50字內）",
    "step3_key_factors": [
      {{"name": "因子名", "weight": 0.0, "advantage": "home/away/even", "delta": 0}},
      ...
    ],
    "step4_probability_calc": "機率推導過程（30字內）",
    "step5_confidence_rationale": "信心理量理由（30字內）",
    "step6_score_rationale": "比分推導理由（30字內）"
  }},
  "home_win_probability": 0.0,
  "away_win_probability": 1 - home_win_probability,
  "confidence": 1-10 整數,
  "key_factors": [
    "因子1（必須含具體數字/球員名）",
    ...
  ],
  "summary": "深度分析摘要（180-400字，引用具體球員與數據）",
  "predicted_score": "X-Y",
  "radar_chart": {{
    "categories": {json.dumps(current_dims, ensure_ascii=False)},
    "home_team": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    "away_team": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
  }}
}}

請只輸出這個 JSON object，不要有任何其他文字。
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
        # 先試主要 LLM（受 token bucket 限速，避免免費層並發限制）
        _llm_bucket.acquire()
        result = self._try_llm(CLOUD_LLM_URL, CLOUD_LLM_MODEL, CLOUD_LLM_API_KEY, prompt)
        if result:
            return result
        # 主要 LLM 失敗，試備援（不同模型才切，避免同 URL 同 model 重試）
        if FALLBACK_LLM_API_KEY and FALLBACK_LLM_MODEL != CLOUD_LLM_MODEL:
            print(f"  ⚠ Primary LLM ({CLOUD_LLM_MODEL}) failed, trying fallback ({FALLBACK_LLM_MODEL})...")
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
            "max_tokens": 11796,  # 9830 * 1.2 = 11796（再提高 20% 避免 reasoning 過長導致 JSON 截斷）
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
        
        # 處理嵌套結構（修正：先保留外層雷達圖/分析，再合併所有巢狀區塊，避免丟失 radar_chart + 重要欄位）
        if isinstance(result, dict):
            # 🆕 [fix] 不再「整個 replace」子字典，而是「淺層合併」：所有巢狀區塊的欄位都併入外層
            outer_radar = result.get('radar_chart') if isinstance(result.get('radar_chart'), dict) else None
            outer_key_factors = result.get('key_factors') if isinstance(result.get('key_factors'), list) else None
            outer_summary = result.get('summary') if isinstance(result.get('summary'), str) else None
            outer_predicted_score = result.get('predicted_score') if isinstance(result.get('predicted_score'), str) else None

            merged = dict(result)  # 保留外層所有欄位
            visited_keys = set()
            # 反覆合併巢狀區塊（支援 result→prediction→hp 多層巢狀）
            for _ in range(3):  # 最多 3 層深度
                progressed = False
                for key in ['result', 'analysis', 'output', 'prediction']:
                    if key in visited_keys:
                        continue
                    if key in merged and isinstance(merged[key], dict):
                        nested = merged[key]
                        visited_keys.add(key)
                        for nk, nv in nested.items():
                            if nk not in merged or merged.get(nk) in ('', 0.0, 0, None, [], {}):
                                merged[nk] = nv
                                progressed = True
                if not progressed:
                    break

            # 確保外層的雷達圖不會被巢狀區塊的（多半為空）覆蓋
            if outer_radar:
                merged['radar_chart'] = outer_radar
            if outer_key_factors:
                merged['key_factors'] = outer_key_factors
            if outer_summary:
                merged['summary'] = outer_summary
            if outer_predicted_score:
                merged['predicted_score'] = outer_predicted_score

            result = merged

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
            if 'radar_chart' not in result or not isinstance(result.get('radar_chart'), dict):
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
            
            # 處理嵌套結構（修正：先保留外層雷達圖/分析，再合併所有巢狀區塊）
            if isinstance(result, dict):
                outer_radar = result.get('radar_chart') if isinstance(result.get('radar_chart'), dict) else None
                outer_key_factors = result.get('key_factors') if isinstance(result.get('key_factors'), list) else None
                outer_summary = result.get('summary') if isinstance(result.get('summary'), str) else None
                outer_predicted_score = result.get('predicted_score') if isinstance(result.get('predicted_score'), str) else None

                merged = dict(result)
                visited_keys = set()
                for _ in range(3):  # 最多 3 層深度
                    progressed = False
                    for key in ['result', 'analysis', 'output', 'prediction']:
                        if key in visited_keys:
                            continue
                        if key in merged and isinstance(merged[key], dict):
                            nested = merged[key]
                            visited_keys.add(key)
                            for nk, nv in nested.items():
                                if nk not in merged or merged.get(nk) in ('', 0.0, 0, None, [], {}):
                                    merged[nk] = nv
                                    progressed = True
                    if not progressed:
                        break

                if outer_radar:
                    merged['radar_chart'] = outer_radar
                if outer_key_factors:
                    merged['key_factors'] = outer_key_factors
                if outer_summary:
                    merged['summary'] = outer_summary
                if outer_predicted_score:
                    merged['predicted_score'] = outer_predicted_score

                result = merged

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
                if 'radar_chart' not in result or not isinstance(result.get('radar_chart'), dict):
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
                # 🆕 [fix] 摘要太短（< 150 字）視為不完整，走 fallback
                is_too_short = len(summary) < 150
                # 🆕 [fix] 摘要太長（> 600 字）截斷為 600 字以內（避免使用者閱讀疲勞）
                is_too_long = len(summary) > 600
                if is_template:
                    print("  AI returned template, using computed fallback")
                    return None  # 走 fallback 路徑
                if is_too_short:
                    print(f"  ⚠ AI summary too short ({len(summary)} chars < 150), using fallback for richer analysis")
                    return None  # 走 fallback 路徑（fallback 會被替換為更好的摘要）
                if is_too_long:
                    print(f"  ⚠ AI summary too long ({len(summary)} chars > 600), truncating to fit UX limit")
                    # 截斷到 600 字以內，盡量在句號處切斷
                    truncated = summary[:600]
                    last_period = max(
                        truncated.rfind("。"),
                        truncated.rfind("！"),
                        truncated.rfind("？"),
                        truncated.rfind(". "),
                    )
                    if last_period > 200:
                        truncated = truncated[: last_period + 1]
                    else:
                        truncated = truncated.rstrip() + "。"
                    result["summary"] = truncated
                    print(f"  → Truncated to {len(truncated)} chars")
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
                        'WNBA': 0.58,  # WNBA 主場勝率與 NBA 接近
                        'CPBL': 0.55,  # CPBL 主場勝率約 55-60%
                        'MLB': 0.54,   # MLB 主場勝率約 53-54%
                        'NPB': 0.54,   # NPB 主場勝率約 53%
                    }
                    home_prob = home_advantage_map.get(lg, 0.53)  # 預設 53% (一般主場優勢)
                    away_prob = 1.0 - home_prob
                
                result["home_win_probability"] = round(home_prob, 4)
                result["away_win_probability"] = round(away_prob, 4)

                # 🆕 [Recipe 6 post-process] 投手近況調整（MLB/NPB/CPBL 棒球類）
                # 當投手近 3 場 ERA 與整季 ERA 差距過大時，強制校正勝率
                # 原因：AI prompt 已加強引導，但 LLM 仍會被戰績/排名蓋過，需後處理保險
                lg = (features.get('league') or '').upper()
                if lg in ('MLB', 'NPB', 'CPBL'):
                    pitcher_data = features.get('mlb_pitchers') or features.get('npb_pitchers') or features.get('cpbl_pitchers') or features.get('pitchers') or {}
                    pitcher_adjustment_log = []

                    def _get_pitcher(side):
                        return (pitcher_data.get(f'{side}_pitcher') or {}).get('stats') or {}

                    def _safe_float(value, default=0.0):
                        try:
                            v = float(value or 0)
                            return v if v > 0 else default
                        except (TypeError, ValueError):
                            return default

                    home_pitcher_stats = _get_pitcher('home')
                    away_pitcher_stats = _get_pitcher('away')

                    home_k9 = _safe_float(home_pitcher_stats.get('k_per_9'))
                    away_k9 = _safe_float(away_pitcher_stats.get('k_per_9'))
                    home_bb9 = _safe_float(home_pitcher_stats.get('bb_per_9'))
                    away_bb9 = _safe_float(away_pitcher_stats.get('bb_per_9'))
                    home_kbb_ratio = _safe_float(home_pitcher_stats.get('k_bb_ratio'))
                    away_kbb_ratio = _safe_float(away_pitcher_stats.get('k_bb_ratio'))

                    for side, current_prob_name in [('home', 'home_prob'), ('away', 'away_prob')]:
                        p = pitcher_data.get(f'{side}_pitcher') or {}
                        if not p:
                            continue
                        season_stats = p.get('stats') or {}
                        recent = p.get('recent_stats') or {}
                        recent_summary = recent.get('summary') or {}

                        season_era = float(season_stats.get('era', 0) or 0)
                        recent_era = float(recent_summary.get('era', 0) or 0)
                        recent_count = int(recent_summary.get('count', 0) or 0)

                        # 至少需要 2 場 recent data 才調整（避免 1 場爆量誤判）
                        if recent_count < 2 or season_era == 0 or recent_era == 0:
                            continue

                        era_diff = recent_era - season_era
                        adjustment = 0.0
                        reason = ""

                        # 降溫中：近 3 場比整季差很多
                        if recent_era > 6.0 and era_diff > 3.0:
                            adjustment = -0.08 # 該隊勝率降 8%
                            reason = f"{side}_pitcher 降溫中（近3場 ERA={recent_era}, 整季={season_era}）"
                        elif recent_era > 5.0 and era_diff > 2.5:
                            adjustment = -0.05
                            reason = f"{side}_pitcher 略降溫（近3場 ERA={recent_era}, 整季={season_era}）"
                        # 升溫中：近 3 場比整季好很多
                        elif recent_era < 2.0 and era_diff < -2.5:
                            adjustment = +0.06
                            reason = f"{side}_pitcher 升溫中（近3場 ERA={recent_era}, 整季={season_era}）"
                        elif recent_era < 2.5 and era_diff < -1.5:
                            adjustment = +0.04
                            reason = f"{side}_pitcher 略升溫（近3場 ERA={recent_era}, 整季={season_era}）"

                        if adjustment != 0.0:
                            if side == 'home':
                                home_prob = max(0.30, min(0.85, home_prob + adjustment))
                                away_prob = 1.0 - home_prob
                            else:
                                away_prob = max(0.30, min(0.85, away_prob + adjustment))
                                home_prob = 1.0 - away_prob
                            pitcher_adjustment_log.append(f"{reason} → 勝率調整 {adjustment:+.2f}")

                    # 🆕 [P0-NPB] 先發投手三振能力(K/9)與四壞球控制(BB/9)確定性加成
                    # 只對 NPB 生效：NPB 得分低、先發投手 K/BB 是勝負關鍵指標
                    # 直接調整勝率（不依賴 LLM 感覺），與 Recipe 6 ERA 校正疊加
                    if lg == 'NPB':
                        kb_adjust_log = []
                        h_sp = (pitcher_data.get('home_pitcher') or {}).get('stats') or {}
                        a_sp = (pitcher_data.get('away_pitcher') or {}).get('stats') or {}
                        
                        # 🆕 [fix] lottonavi 只提供 ERA，缺少 K/9 BB/9 時從輪值 #1 借用
                        if h_sp and 'k_per_9' not in h_sp:
                            home_pitchers_list = features.get('npb_pitchers', {}).get('home_pitchers', [])
                            if home_pitchers_list:
                                h_sp['k_per_9'] = home_pitchers_list[0].get('k_per_9', 0)
                                h_sp['bb_per_9'] = home_pitchers_list[0].get('bb_per_9', 0)
                        if a_sp and 'k_per_9' not in a_sp:
                            away_pitchers_list = features.get('npb_pitchers', {}).get('away_pitchers', [])
                            if away_pitchers_list:
                                a_sp['k_per_9'] = away_pitchers_list[0].get('k_per_9', 0)
                                a_sp['bb_per_9'] = away_pitchers_list[0].get('bb_per_9', 0)
                        
                        h_k9 = float(h_sp.get('k_per_9', 0) or 0)
                        a_k9 = float(a_sp.get('k_per_9', 0) or 0)
                        h_bb9 = float(h_sp.get('bb_per_9', 0) or 0)
                        a_bb9 = float(a_sp.get('bb_per_9', 0) or 0)
                        # 雙方都要有有效數據（ip>0 才有 k_per_9/bb_per_9）才調整
                        if h_k9 > 0 and a_k9 > 0 and h_bb9 > 0 and a_bb9 > 0:
                            # 三振能力差：每 1.0 K/9 差距 → 勝率 ±0.015
                            k9_diff = h_k9 - a_k9
                            k9_adj = round(k9_diff * 0.015, 4)
                            # 控球差（BB/9 越低越好）：每 0.5 BB/9 差距 → 勝率 ±0.01
                            bb9_diff = a_bb9 - h_bb9  # 我方 BB 越少越有利
                            bb9_adj = round(bb9_diff * 0.02, 4)  # 0.5 差距 → 0.01
                            kb_adj = round(k9_adj + bb9_adj, 4)
                            if abs(kb_adj) >= 0.005:
                                home_prob = max(0.30, min(0.85, home_prob + kb_adj))
                                away_prob = 1.0 - home_prob
                                kb_adjust_log.append(
                                    f"NPB SP K/BB: 主K/9={h_k9}(BB/9={h_bb9}) vs 客K/9={a_k9}(BB/9={a_bb9}) "
                                    f"→ 勝率調整 {kb_adj:+.4f}"
                                )
                        if kb_adjust_log:
                            pitcher_adjustment_log.extend(kb_adjust_log)

                    if pitcher_adjustment_log:
                        result["home_win_probability"] = round(home_prob, 4)
                        result["away_win_probability"] = round(away_prob, 4)
                        # 把調整理由寫進 summary（若 LLM 沒強調 recent ERA 對比）
                        existing_summary = result.get("summary", "") or ""
                        adjustment_note = "\n\n[投手近況校正] " + "; ".join(pitcher_adjustment_log)
                        if "近 3 場" not in existing_summary and "近3場" not in existing_summary:
                            result["summary"] = existing_summary + adjustment_note
                        print(f" ⚾ Recipe 6 投手調整: {pitcher_adjustment_log}")

                    # 🆕 [Recipe NPB/MLB/CPBL 投手參數擴充] 先發投手 K/9 + BB/9 的確定性加成
                    pitcher_param_delta = {
                        'home_k9': home_k9,
                        'away_k9': away_k9,
                        'home_bb9': home_bb9,
                        'away_bb9': away_bb9,
                    }

                    pitcher_adjustment = 0.0
                    pitcher_adjustment_reasons = []

                    k9_advantage = (home_k9 - away_k9)
                    if k9_advantage >= 1.0:
                        pitcher_adjustment += min(0.02 * (k9_advantage / 1.0), 0.04)
                        pitcher_adjustment_reasons.append(f"主隊先發K/9優勢 +{k9_advantage:.1f}")

                    bb9_gap = (away_bb9 - home_bb9)
                    if bb9_gap >= 0.5:
                        pitcher_adjustment += 0.01 * (bb9_gap / 0.5)
                        pitcher_adjustment_reasons.append(f"客隊BB/9偏高 +{bb9_gap:.1f}")

                    if home_kbb_ratio > 0 and away_kbb_ratio > 0 and (home_kbb_ratio - away_kbb_ratio) > 0.5:
                        pitcher_adjustment += 0.02
                        pitcher_adjustment_reasons.append(f"主隊K/BB比值優勢 +{(home_kbb_ratio - away_kbb_ratio):.2f}")

                    if pitcher_adjustment != 0.0:
                        pitcher_adjustment = max(-0.05, min(0.05, pitcher_adjustment))
                        if home_prob > away_prob:
                            home_prob = max(0.30, min(0.85, home_prob + pitcher_adjustment))
                            away_prob = 1.0 - home_prob
                        else:
                            away_prob = max(0.30, min(0.85, away_prob - pitcher_adjustment))
                            home_prob = 1.0 - away_prob
                        result["home_win_probability"] = round(home_prob, 4)
                        result["away_win_probability"] = round(away_prob, 4)
                        existing_summary = result.get("summary", "") or ""
                        adjustment_note = "\n\n[投手參數校正] " + "; ".join(pitcher_adjustment_reasons) + f" => 勝率調整 {pitcher_adjustment:+.2f}"
                        if "[投手參數校正]" not in existing_summary:
                            result["summary"] = existing_summary + adjustment_note
                        print(f" ⚾ Recipe 6 投手參數調整: {pitcher_adjustment_reasons}")


                # 信心指數標準化: 若 Ollama 回傳 0~1 分數則轉換為 1~10 評分
                raw_conf = float(result.get("confidence", 0.0))
                if raw_conf <= 1.0:
                    # 0-1 -> 1-10 映射: 0.0->1, 0.5->5, 1.0->10
                    normalized_conf = max(1, round(raw_conf * 10))
                else:
                    normalized_conf = max(1, min(10, round(raw_conf)))
                result["confidence"] = normalized_conf

                # 🆕 [Recipe 7: 方法 E] 基於特徵的置信度動態調整
                # 戰績差距、投手差距、排名差距若明顯,主動調高置信度
                # 目的: 讓強弱懸殊賽事自然落在 8-9 區間,提升分佈多樣性
                feature_boost = 0
                boost_reasons = []

                home_standings_raw = features.get('home_standings') or {}
                away_standings_raw = features.get('away_standings') or {}
                home_win_pct_raw = float(home_standings_raw.get('win_pct', 0.5) or 0.5)
                away_win_pct_raw = float(away_standings_raw.get('win_pct', 0.5) or 0.5)
                win_pct_diff = abs(home_win_pct_raw - away_win_pct_raw)

                # 條件 1: 戰績差距 > 20%
                if win_pct_diff > 0.20:
                    feature_boost += 1
                    boost_reasons.append(f"戰績差距 {win_pct_diff:.0%}")

                # 條件 2: 投手 ERA 差距 > 1.5
                lg_check = (features.get('league') or '').upper()
                if lg_check in ('MLB', 'NPB', 'CPBL'):
                    pitcher_data_check = features.get('mlb_pitchers') or features.get('npb_pitchers') or features.get('cpbl_pitchers') or features.get('pitchers') or {}
                    home_p = pitcher_data_check.get('home_pitcher') or {}
                    away_p = pitcher_data_check.get('away_pitcher') or {}
                    # 🆕 [2026-07-13] ERA 可能是字串 '---'（尚未公布），需 try/except
                    def _safe_era(stats_dict):
                        raw = (stats_dict or {}).get('era', 0)
                        if raw in (None, '', '---', '--'):
                            return 0.0
                        try:
                            return float(raw)
                        except (ValueError, TypeError):
                            return 0.0
                    h_era = _safe_era(home_p.get('stats'))
                    a_era = _safe_era(away_p.get('stats'))
                    if h_era > 0 and a_era > 0:
                        era_diff = abs(h_era - a_era)
                        if era_diff > 1.5:
                            feature_boost += 1
                            boost_reasons.append(f"投手 ERA 差距 {era_diff:.2f}")

                # 條件 3: 排名差距 > 10 名
                home_rank = home_standings_raw.get('rank')
                away_rank = away_standings_raw.get('rank')
                if home_rank and away_rank:
                    rank_diff = abs(int(home_rank) - int(away_rank))
                    if rank_diff > 10:
                        feature_boost += 1
                        boost_reasons.append(f"排名差距 {rank_diff}")

                if feature_boost > 0:
                    old_conf = normalized_conf
                    normalized_conf = min(10, normalized_conf + feature_boost)
                    result["confidence"] = normalized_conf
                    print(f"  📈 Recipe 7 置信度提升: {old_conf} → {normalized_conf} (依據: {', '.join(boost_reasons)})")

                # 🆕 信心度-勝率一致性檢查
                # 根據調整後的置信度,動態計算最低勝率差距門檻
                # 強弱懸殊賽事(置信度 8-9)會自動要求更大勝率差距
                prob_diff = abs(home_prob - away_prob)

                # 🆕 [Recipe 7: 方法 B 改良] 主場優勢動態化
                # 強隊主場 (戰績前 1/3): 0.56,一般: 0.54,弱隊主場: 0.52
                # 應用於一致性檢查的最低差距門檻
                home_advantage = 0.54
                if home_win_pct_raw > 0.60:
                    home_advantage = 0.56  # 強隊主場優勢更明顯
                elif home_win_pct_raw < 0.45:
                    home_advantage = 0.52  # 弱隊主場優勢較弱

                min_prob_diff_map = {
                    1: 0.00, 2: 0.00, 3: 0.00,
                    4: 0.04, 5: 0.06,    # 信心 4-5：至少有 4-6% 差距
                    6: 0.08,             # 信心 6：至少 8% 差距
                    7: 0.13,             # 信心 7：至少 13% 差距（明顯佔優,放寬讓更多場次落入）
                    8: 0.18,             # 信心 8：至少 18% 差距（放寬 2pp）
                    9: 0.23,             # 信心 9：至少 23% 差距（放寬 2pp）
                    10: 0.30,            # 信心 10：至少 30% 差距
                }
                # 弱主場時下修 1pp,避免弱隊主場差距被過度放大
                if home_advantage < 0.54:
                    min_prob_diff_map = {k: max(0, v - 0.01) for k, v in min_prob_diff_map.items()}
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

                # 🆕 [Recipe 8] radar_chart 補齊邏輯（修雷達圖消失 bug）
                # 修正: LLM 常回傳空陣列的 radar_chart ({"categories": [], ...})
                # 舊邏輯只在「完全沒 key」時補空 dict,不會修「空陣列」情況
                # 新邏輯: 任一欄位為空時,用 _compute_team_radar_scores 補上本地計算值
                radar = result.get('radar_chart')
                radar_invalid = (
                    not isinstance(radar, dict) or
                    not radar.get('categories') or
                    not radar.get('home_team') or
                    not radar.get('away_team')
                )
                if radar_invalid:
                    league_lc = (features.get('league') or '').upper()
                    dims_map = {
                        "MLB": ["球隊整體戰力", "打線火力", "先發投手", "牛棚表現", "主客場因素", "近期狀態"],
                        "NPB": ["球隊整體戰力", "打線火力", "先發投手", "牛棚表現", "主客場因素", "近期狀態"],
                        "CPBL": ["球隊整體戰力", "打線火力", "先發投手", "牛棚表現", "主客場因素", "近期狀態"],
                        "NBA": ["團隊整體戰力", "進攻效率", "防守強度", "籃板能力", "關鍵球處理", "近期狀態"],
                        "WNBA": ["團隊整體戰力", "進攻效率", "防守強度", "籃板能力", "關鍵球處理", "近期狀態"],
                    }
                    dims = dims_map.get(league_lc, ["整體戰力", "進攻能力", "防守能力", "戰術執行", "環境因素", "近期狀態"])
                    home_radar_scores = self._compute_team_radar_scores(features, 'home')
                    away_radar_scores = self._compute_team_radar_scores(features, 'away')
                    result['radar_chart'] = {
                        "categories": dims,
                        "home_team": [min(10, max(0, h)) for h in home_radar_scores['values']],
                        "away_team": [min(10, max(0, a)) for a in away_radar_scores['values']],
                    }
                    print(f"  📊 Recipe 8 雷達圖補齊: {len(dims)} 維")

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
        
        # 🆕 [fix] 預測比分應考慮淨分差，不只是進攻得分
        # 弱隊場均失分高 → 對強隊應失更多分
        home_avg_f = home_form.get('avg_goals_for', 0) or 0
        home_avg_a = home_form.get('avg_goals_against', 0) or 0
        away_avg_f = away_form.get('avg_goals_for', 0) or 0
        away_avg_a = away_form.get('avg_goals_against', 0) or 0

        # 🆕 [P0-NPB fallback 同步] 先發投手 K/9 與 BB/9 確定性加成
        # 與正常路徑 Recipe 6 區塊使用完全一致公式，確保 fallback 也反映投手三振/保送優勢
        lg_fb = (features.get('league') or '').upper()
        if lg_fb == 'NPB':
            kb_pitcher = features.get('npb_pitchers') or features.get('mlb_pitchers') or features.get('pitchers') or {}
            h_sp_fb = (kb_pitcher.get('home_pitcher') or {}).get('stats') or {}
            a_sp_fb = (kb_pitcher.get('away_pitcher') or {}).get('stats') or {}
            
            # 🆕 [fix] lottonavi 只提供 ERA，缺少 K/9 BB/9 時從輪值 #1 借用
            if h_sp_fb and 'k_per_9' not in h_sp_fb:
                home_pitchers_fb = features.get('npb_pitchers', {}).get('home_pitchers', [])
                if home_pitchers_fb:
                    h_sp_fb['k_per_9'] = home_pitchers_fb[0].get('k_per_9', 0)
                    h_sp_fb['bb_per_9'] = home_pitchers_fb[0].get('bb_per_9', 0)
            if a_sp_fb and 'k_per_9' not in a_sp_fb:
                away_pitchers_fb = features.get('npb_pitchers', {}).get('away_pitchers', [])
                if away_pitchers_fb:
                    a_sp_fb['k_per_9'] = away_pitchers_fb[0].get('k_per_9', 0)
                    a_sp_fb['bb_per_9'] = away_pitchers_fb[0].get('bb_per_9', 0)
            
            h_k9_fb = float(h_sp_fb.get('k_per_9', 0) or 0)
            a_k9_fb = float(a_sp_fb.get('k_per_9', 0) or 0)
            h_bb9_fb = float(h_sp_fb.get('bb_per_9', 0) or 0)
            a_bb9_fb = float(a_sp_fb.get('bb_per_9', 0) or 0)
            if h_k9_fb > 0 and a_k9_fb > 0 and h_bb9_fb > 0 and a_bb9_fb > 0:
                k9_adj_fb = round((h_k9_fb - a_k9_fb) * 0.015, 4)
                bb9_adj_fb = round((a_bb9_fb - h_bb9_fb) * 0.02, 4)
                kb_adj_fb = round(k9_adj_fb + bb9_adj_fb, 4)
                if abs(kb_adj_fb) >= 0.005:
                    home_prob = max(0.30, min(0.85, home_prob + kb_adj_fb))
                    print(f"  ⚾ [fallback] NPB SP K/BB: 主 K/9={h_k9_fb}(BB/9={h_bb9_fb}) vs 客 K/9={a_k9_fb}(BB/9={a_bb9_fb}) → 勝率調整 {kb_adj_fb:+.4f}")

        # Radar chart 維度（用於 fallback 也保留 AI-style 6 維度）
        league = features.get('league', '')
        leauge_dims_map = {
            "MLB": ["球隊整體戰力", "打線火力", "先發投手", "牛棚表現", "主客場因素", "近期狀態"],
            "NBA": ["團隊整體戰力", "進攻效率", "防守強度", "籃板能力", "關鍵球處理", "近期狀態"],
            "WNBA": ["團隊整體戰力", "進攻效率", "防守強度", "籃板能力", "關鍵球處理", "近期狀態"],
            "CPBL": ["球隊整體戰力", "打線火力", "先發投手", "牛棚表現", "主客場因素", "近期狀態"],
        }
        dims = leauge_dims_map.get(
            league.upper() if league else "",
            ["整體戰力", "進攻能力", "防守能力", "戰術執行", "環境因素", "近期狀態"],
        )

        # 用 stats 計算有意義的 6 維雷達圖（避免線性遞減造成每隊 6 個相近數字）
        home_radar = self._compute_team_radar_scores(features, 'home')
        away_radar = self._compute_team_radar_scores(features, 'away')
        home_vals = home_radar['values']
        away_vals = away_radar['values']

        # 預測單隊得分 = (己隊進攻實力 + 對手防守弱點) / 2
        home_predicted = round(((home_avg_f or 3) + (away_avg_a or 3)) / 2)
        away_predicted = round(((away_avg_f or 3) + (home_avg_a or 3)) / 2)

        # 🆕 [fix] 依聯盟決定單隊得分範圍（WNBA 70-110、NBA 95-135、棒球 1-12）
        score_ranges = {
            "MLB": (1, 12), "NPB": (1, 12), "CPBL": (1, 12),
            "NBA": (95, 135), "WNBA": (70, 110),
        }
        lo, hi = score_ranges.get(league.upper() if league else "", (1, 12))
        home_predicted = max(lo, min(hi, home_predicted))
        away_predicted = max(lo, min(hi, away_predicted))

        # 🆕 [fix] 建立分析性句子（避免 fallback 摘要過短）
        # 1. 主隊實力描述
        home_net = home_avg_f - home_avg_a
        away_net = away_avg_f - away_avg_a
        if home_net > 1.5:
            home_team_strength_sentence = (
                f"主隊進攻端表現優於防守（淨分差 +{home_net:.1f}），"
                f"近期戰績顯示火力穩定輸出；"
            )
        elif home_net < -1.5:
            home_team_strength_sentence = (
                f"主隊防守端漏洞明顯（淨分差 {home_net:+.1f}），"
                f"近期失分過多成為隱憂；"
            )
        else:
            home_team_strength_sentence = (
                f"主隊攻守表現接近平衡（淨分差 {home_net:+.1f}）；"
            )

        # 2. 客隊實力描述
        if away_net > 1.5:
            away_team_strength_sentence = (
                f"客隊整體戰力強勢（淨分差 +{away_net:.1f}），"
                f"近況明顯優於主隊；"
            )
        elif away_net < -1.5:
            away_team_strength_sentence = (
                f"客隊防守不佳（淨分差 {away_net:+.1f}），"
                f"若投打無法互補則難以取勝；"
            )
        else:
            away_team_strength_sentence = f"客隊攻守穩定（淨分差 {away_net:.1f}）；"

        # 3. 對戰洞察
        if abs(home_net - away_net) < 0.5:
            matchup_insight = (
                f"兩隊淨分差相近，勝負關鍵在投手先發表現與關鍵時刻打擊。"
            )
        elif home_net > away_net:
            matchup_insight = (
                f"主隊淨分差領先 {home_net - away_net:.1f} 分，加上主場優勢，看好主隊延續氣勢。"
            )
        else:
            matchup_insight = (
                f"客隊淨分差領先 {away_net - home_net:.1f} 分，整體戰力明顯優於主隊，"
                f"即便作客仍具備勝算。"
            )

        # Key factors（至少 4 個）
        factors = []
        if home_standings:
            factors.append(
                f"{features['game_info']['home_team_name']}排名第{home_standings['rank']}（勝率 {home_standings.get('win_pct', '?')}）"
            )
        if away_standings:
            factors.append(
                f"{features['game_info']['away_team_name']}排名第{away_standings['rank']}（勝率 {away_standings.get('win_pct', '?')}）"
            )
        if home_form.get('win_loss'):
            factors.append(
                f"主隊近期{home_form['win_loss']}，場均得{home_avg_f:.1f}失{home_avg_a:.1f}（淨分差 {home_avg_f - home_avg_a:+.1f}）"
            )
        if away_form.get('win_loss'):
            factors.append(
                f"客隊近期{away_form['win_loss']}，場均得{away_avg_f:.1f}失{away_avg_a:.1f}（淨分差 {away_avg_f - away_avg_a:+.1f}）"
            )
        # 補到至少 4 個
        away_prob = 1 - home_prob  # 在 fallback 路徑，away = 1 - home
        if len(factors) < 4:
            if home_prob > away_prob:
                factors.append(f"主隊具備主場優勢（勝率 {home_prob:.0%}）")
            else:
                factors.append(f"客隊實力佔優（勝率 {away_prob:.0%}）")
        if len(factors) < 4:
            factors.append(f"預測比分 {home_predicted}-{away_predicted}")

        fallback = {
            "home_win_probability": round(home_prob, 4),
            "away_win_probability": round(1 - home_prob, 4),
            "confidence": max(1, min(10, round(max(home_prob, 1 - home_prob) * 10))),
            "key_factors": factors[:4],
            "summary": (
                f"{features['game_info']['home_team_name']} vs {features['game_info']['away_team_name']}："
                f"{home_form.get('win_loss', '近期數據不足')}，"
                f"場均得{home_avg_f:.1f}分/失{home_avg_a:.1f}分（淨分差 {home_avg_f - home_avg_a:+.1f}）；"
                f"客隊{away_form.get('win_loss', '近期數據不足')}，"
                f"場均得{away_avg_f:.1f}分/失{away_avg_a:.1f}分（淨分差 {away_avg_f - away_avg_a:+.1f}）。"
                f"{home_team_strength_sentence}"
                f"{away_team_strength_sentence}"
                f"{matchup_insight}"
            ),
            # 🆕 [fix] fallback 也要過 reconcile，避免未來賽事（無先發數據 → CPBL SP 404）
            # 走 fallback 時算出平手比分（如 4-4）被原樣寫入，造成棒球平手異常。
            # 統一用 _reconcile_predicted_score 確保 favorite 勝 1 分以上。
            "predicted_score": self._reconcile_predicted_score(
                f"{home_predicted}-{away_predicted}", home_prob, 1 - home_prob,
                features.get('league', '')
            ),
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
        if self.conn and not getattr(self.conn, 'closed', False):
            try:
                self.cur.close()
                self.conn.close()
            except Exception:
                pass
        self.conn = None
        self.cur = None

if __name__ == "__main__":
    pass
    engine.cur.execute("SELECT game_id FROM predictx.games WHERE match_date = '2026-06-09' LIMIT 1")
    res = engine.cur.fetchone()
    if res:
        game_id = res['game_id']
        analysis = engine.analyze_game(game_id)
        print(json.dumps(analysis, indent=2, ensure_ascii=False))
    engine.close()
