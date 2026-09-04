"""
PredictX Sports — NPB DataFetcher
從 baseball-data.com 爬取 NPB 即時數據（免費，無需 API Key）
"""
import requests
import re
import json
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from bs4 import BeautifulSoup

DB_CONFIG = {
    "dbname": "sports_db", "user": "jero",
    "password": "", "host": "localhost", "port": 5432
}

# 日文隊名 → 英文隊名對照（含全稱）
TEAM_NAME_MAP = {
    "巨人": "Yomiuri Giants",
    "阪神": "Hanshin Tigers",
    "中日": "Chunichi Dragons",
    "DeNA": "Yokohama DeNA BayStars",
    "広島": "Hiroshima Toyo Carp",
    "ヤクルト": "Tokyo Yakult Swallows",
    "ソフトバンク": "Fukuoka SoftBank Hawks",
    "西武": "Saitama Seibu Lions",
    "ロッテ": "Chiba Lotte Marines",
    "オリックス": "ORIX Buffaloes",
    "楽天": "Tohoku Rakuten Golden Eagles",
    "日本ハム": "Hokkaido Nippon-Ham Fighters",
}

# npb.jp 官方「予告先発投手」頁面 logo alt 全稱 → 英文全名對照
NPB_OFFICIAL_TEAM_MAP = {
    "東京ヤクルトスワローズ": "Tokyo Yakult Swallows",
    "中日ドラゴンズ": "Chunichi Dragons",
    "広島東洋カープ": "Hiroshima Toyo Carp",
    "読売ジャイアンツ": "Yomiuri Giants",
    "東北楽天ゴールデンイーグルス": "Tohoku Rakuten Golden Eagles",
    "北海道日本ハムファイターズ": "Hokkaido Nippon-Ham Fighters",
    "オリックス・バファローズ": "ORIX Buffaloes",
    "千葉ロッテマリーンズ": "Chiba Lotte Marines",
    "福岡ソフトバンクホークス": "Fukuoka SoftBank Hawks",
    "埼玉西武ライオンズ": "Saitama Seibu Lions",
    "阪神タイガース": "Hanshin Tigers",
    "横浜DeNAベイスターズ": "Yokohama DeNA BayStars",
}

# 運彩報馬仔隊名縮寫 → 英文全名對照
LOTTONAVI_TEAM_MAP = {
    "中日": "Chunichi Dragons",
    "巨人": "Yomiuri Giants",
    "阪神": "Hanshin Tigers",
    "DeNA": "Yokohama DeNA BayStars",
    "広島": "Hiroshima Toyo Carp",
    "廣島": "Hiroshima Toyo Carp",
    "ヤクルト": "Tokyo Yakult Swallows",
    "養樂多": "Tokyo Yakult Swallows",
    "日本ハム": "Hokkaido Nippon-Ham Fighters",
    "日本火腿": "Hokkaido Nippon-Ham Fighters",
    "楽天": "Tohoku Rakuten Golden Eagles",
    "樂天": "Tohoku Rakuten Golden Eagles",
    "西武": "Saitama Seibu Lions",
    "ロッテ": "Chiba Lotte Marines",
    "羅德": "Chiba Lotte Marines",
    "オリックス": "ORIX Buffaloes",
    "歐力士": "ORIX Buffaloes",
    "ソフトバンク": "Fukuoka SoftBank Hawks",
    "軟體銀行": "Fukuoka SoftBank Hawks",
    "橫濱": "Yokohama DeNA BayStars",
}

# 英文隊名 → baseball-data.com 的 URL code
TEAM_URL_CODES = {
    "Yomiuri Giants": "g",
    "Hanshin Tigers": "t",
    "Chunichi Dragons": "d",
    "Yokohama DeNA BayStars": "yb",
    "Hiroshima Toyo Carp": "c",
    "Tokyo Yakult Swallows": "s",
    "Fukuoka SoftBank Hawks": "h",
    "Saitama Seibu Lions": "l",
    "Chiba Lotte Marines": "m",
    "ORIX Buffaloes": "bs",
    "Tohoku Rakuten Golden Eagles": "e",
    "Hokkaido Nippon-Ham Fighters": "f",
}

# 🆕 NPB 12 球場 Park Factor（依歷年得分手冊計算）
# 數值 > 1.0 = 打者友善（容易得分），< 1.0 = 投手友善
# 巨蛋球場普遍偏低（無風、無日曬），大阪京瓷巨蛋最低（投手戰）
NPB_PARK_FACTORS = {
    "Yokohama Stadium": 0.92,          # DeNA 主場（投手丘高、寬闊）
    "Tokyo Dome": 0.88,                # 巨人/養樂多（巨蛋）
    "Sapporo Dome": 0.86,              # 日本火腿（巨蛋）
    "Seibu Dome": 0.90,                # 西武（巨蛋）
    "Nagoya Dome": 0.92,               # 中日（巨蛋）
    "Osaka Dome": 0.85,                # 歐力士（巨蛋，太平洋聯盟最低）
    "Fukuoka Dome": 0.93,              # 軟銀（巨蛋）
    "Koshien Stadium": 1.15,           # 阪神（寬闊戶外，風勢影響）
    "Hiroshima Mazda Stadium": 1.05,   # 廣島（戶外，較中性）
    "Kamaishiden Recovery Stadium": 1.00,  # 樂天（岩手，戶外）
    "Zozo Marine Stadium": 1.02,       # 羅德（千葉，海風）
    "Meiji Jingu Stadium": 0.95,       # 養樂多（神宮球場，部分）
}
# Park Factor 球場對應表（球隊 → 主場）
NPB_TEAM_HOME_PARK = {
    "Yomiuri Giants": "Tokyo Dome",
    "Hanshin Tigers": "Koshien Stadium",
    "Chunichi Dragons": "Nagoya Dome",
    "Yokohama DeNA BayStars": "Yokohama Stadium",
    "Hiroshima Toyo Carp": "Hiroshima Mazda Stadium",
    "Tokyo Yakult Swallows": "Meiji Jingu Stadium",  # 部分賽事 Tokyo Dome
    "Fukuoka SoftBank Hawks": "Fukuoka Dome",
    "Saitama Seibu Lions": "Seibu Dome",
    "Chiba Lotte Marines": "Zozo Marine Stadium",
    "ORIX Buffaloes": "Osaka Dome",
    "Tohoku Rakuten Golden Eagles": "Kamaishiden Recovery Stadium",
    "Hokkaido Nippon-Ham Fighters": "Sapporo Dome",
}

class NPBDataFetcher:
    def __init__(self, conn=None):
        self.conn = None
        self.cur = None
        if conn:
            self.conn = conn
            self.cur = conn.cursor(cursor_factory=RealDictCursor)
        else:
            try:
                database_url = os.getenv('DATABASE_PUBLIC_URL') or os.getenv('DATABASE_URL')
                if database_url:
                    if database_url.startswith('postgres://'):
                        database_url = database_url.replace('postgres://', 'postgresql://', 1)
                    self.conn = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
                else:
                    self.conn = psycopg2.connect(**DB_CONFIG)
                self.cur = self.conn.cursor(cursor_factory=RealDictCursor)
            except Exception:
                pass  # DB 連線失敗不影響 HTTP-based 方法（如 get_today_starters）
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        })
        self.fetched_sources = []

    def _get_team_id_by_name(self, team_name):
        """透過英文隊名查詢 predictx.teams 的 team_id"""
        if not self.cur:
            return None
        try:
            self.cur.execute(
                "SELECT team_id FROM predictx.teams WHERE english_name ILIKE %s AND league = 'NPB'",
                (f'%{team_name}%',)
            )
            row = self.cur.fetchone()
            return row['team_id'] if row else None
        except Exception:
            return None

    def get_standings(self):
        """取得 NPB 聯盟排名
        優先從 npb_team_standings 表取（避免 baseball-data.com 403 問題），
        找不到再爬 baseball-data.com。
        """
        # 1) 先試 DB（更可靠）
        db_standings = self._get_standings_from_db()
        if db_standings:
            return db_standings
        
        # 2) Fallback 到 baseball-data.com 爬蟲
        try:
            resp = self.session.get("https://baseball-data.com/", timeout=15)
            if resp.status_code != 200:
                return {}
        except Exception:
            return {}
        
        soup = BeautifulSoup(resp.text, 'xml')
        self.fetched_sources.append("baseball-data.com")
        
        standings = {}
        tables = soup.find_all('table')
        for table in tables[:2]:
            rows = table.find_all('tr')
            league_name = "Central" if tables.index(table) == 0 else "Pacific"
            for row in rows[1:]:
                cells = row.find_all('td')
                if len(cells) >= 8:
                    jp_name = cells[1].get_text(strip=True)
                    en_name = TEAM_NAME_MAP.get(jp_name, jp_name)
                    standings[en_name] = {
                        "rank": cells[0].get_text(strip=True),
                        "games": cells[2].get_text(strip=True),
                        "wins": cells[3].get_text(strip=True),
                        "losses": cells[4].get_text(strip=True),
                        "ties": cells[5].get_text(strip=True),
                        "win_pct": cells[6].get_text(strip=True),
                        "league": league_name,
                    }
        return standings

    def _get_standings_from_db(self):
        """從 npb_team_standings 表讀取戰績（baseball-data.com 失敗時的 fallback）"""
        if not self.cur:
            return {}
        try:
            self.cur.execute("""
                SELECT t.english_name, s.rank, s.games_played, s.wins, s.losses, s.ties,
                       ROUND(s.wins::numeric / NULLIF(s.wins + s.losses + s.ties, 0), 3) as win_pct,
                       s.league
                FROM predictx.npb_team_standings s
                JOIN predictx.teams t ON s.team_id = t.team_id
                WHERE s.season = 2026 AND t.league = 'NPB'
            """)
            rows = self.cur.fetchall()
            if not rows:
                return {}
            self.fetched_sources.append("npb_team_standings (official verified)")
            standings = {}
            for row in rows:
                standings[row['english_name']] = {
                    "rank": str(row['rank']),
                    "games": str(row['games_played']),
                    "wins": str(row['wins']),
                    "losses": str(row['losses']),
                    "ties": str(row['ties']),
                    "win_pct": str(row['win_pct']),
                    "league": row['league'],
                }
            return standings
        except Exception:
            return {}

    def get_team_batting_stats(self, team_name):
        """取得 NPB 球隊打擊數據
        優先從 npb_team_batting 表取（含 OPS/SLG/OBP 等進階指標），
        找不到再回退 baseball-data.com 爬蟲（僅 AVG/HR）。
        """
        team_id = self._get_team_id_by_name(team_name)
        if team_id:
            try:
                self.cur.execute("""
                    SELECT games, runs, hits, home_runs, rbi, walks, strikeouts, total_bases,
                           obp, slg, avg
                    FROM predictx.npb_team_batting
                    WHERE team_id = %s AND season = 2026
                """, (team_id,))
                row = self.cur.fetchone()
                if row:
                    self.fetched_sources.append("npb_team_batting (official verified)")
                    return {
                        'games': row['games'],
                        'at_bats': None,
                        'runs': row['runs'],
                        'hits': row['hits'],
                        'doubles': None,
                        'triples': None,
                        'home_runs': row['home_runs'],
                        'rbi': row['rbi'],
                        'walks': row['walks'],
                        'strikeouts': row['strikeouts'],
                        'total_bases': row['total_bases'],
                        'obp': float(row['obp']) if row['obp'] is not None else None,
                        'slg': float(row['slg']) if row['slg'] is not None else None,
                        'avg': float(row['avg']) if row['avg'] is not None else None,
                        'hr': row['home_runs'],
                    }
            except Exception:
                pass
        
        # Fallback to baseball-data.com scraper
        code = TEAM_URL_CODES.get(team_name)
        if not code:
            return None
        
        url = f"https://baseball-data.com/stats/hitter-{code}/"
        resp = self.session.get(url, timeout=15)
        if resp.status_code != 200:
            return None
        
        soup = BeautifulSoup(resp.text, 'lxml')
        self.fetched_sources.append("baseball-data.com")
        
        # 加總所有球員數據
        totals = {}
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            for row in rows[1:]:  # 跳過表頭
                cells = row.find_all('td')
                if len(cells) >= 8:
                    row_data = [c.get_text(strip=True) for c in cells]
                    # 第3欄=打率, 第4欄=試合, 第5欄=打席, 第6欄=打數, 第7欄=安打, 第8欄=本塁打
                    try:
                        games = int(row_data[3]) if len(row_data) > 3 else 0
                        pa = int(row_data[4]) if len(row_data) > 4 else 0
                        ab = int(row_data[5]) if len(row_data) > 5 else 0
                        hits = int(row_data[6]) if len(row_data) > 6 else 0
                        hr = int(row_data[7]) if len(row_data) > 7 else 0
                        
                        totals['games'] = totals.get('games', 0) + games
                        totals['pa'] = totals.get('pa', 0) + pa
                        totals['ab'] = totals.get('ab', 0) + ab
                        totals['hits'] = totals.get('hits', 0) + hits
                        totals['hr'] = totals.get('hr', 0) + hr
                    except (ValueError, IndexError):
                        continue
        
        if totals.get('ab', 0) > 0:
            totals['avg'] = round(totals['hits'] / totals['ab'], 3)
        return totals

    def get_team_pitching_stats(self, team_name):
        """取得 NPB 球隊投球數據
        優先從 npb_team_pitching 表取，找不到再回退 baseball-data.com 爬蟲。
        """
        team_id = self._get_team_id_by_name(team_name)
        if team_id:
            try:
                self.cur.execute("""
                    SELECT games_played, wins, losses, ties, era, saves, holds,
                           complete_games, shutouts, hits_allowed, hr_allowed,
                           walks, hbp, strikeouts, runs_allowed, earned_runs, whip, dips,
                           avg_runs_allowed, avg_hits_allowed
                    FROM predictx.npb_team_pitching
                    WHERE team_id = %s AND season = 2026
                """, (team_id,))
                row = self.cur.fetchone()
                if row:
                    self.fetched_sources.append("npb_team_pitching (official verified)")
                    return {
                        'games': row['games_played'],
                        'wins': row['wins'],
                        'losses': row['losses'],
                        'ties': row['ties'],
                        'era': float(row['era']) if row['era'] is not None else None,
                        'saves': row['saves'],
                        'holds': row['holds'],
                        'complete_games': row['complete_games'],
                        'shutouts': row['shutouts'],
                        'hits_allowed': row['hits_allowed'],
                        'hr_allowed': row['hr_allowed'],
                        'walks': row['walks'],
                        'hbp': row['hbp'],
                        'strikeouts': row['strikeouts'],
                        'runs_allowed': row['runs_allowed'],
                        'earned_runs': row['earned_runs'],
                        'whip': float(row['whip']) if row['whip'] is not None else None,
                        'dips': float(row['dips']) if row['dips'] is not None else None,
                        'win_pct': round(row['wins'] / max(row['wins'] + row['losses'] + row['ties'], 1), 3),
                    }
            except Exception:
                pass
        
        # Fallback to baseball-data.com scraper
        code = TEAM_URL_CODES.get(team_name)
        if not code:
            return None
        
        url = f"https://baseball-data.com/stats/pitcher-{code}/"
        resp = self.session.get(url, timeout=15)
        if resp.status_code != 200:
            return None
        
        soup = BeautifulSoup(resp.text, "xml")
        self.fetched_sources.append("baseball-data.com")
        
        totals = {}
        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            for row in rows[1:]:
                cells = row.find_all("td")
                if len(cells) >= 10:
                    row_data = [c.get_text(strip=True) for c in cells]
                    try:
                        games = int(row_data[3]) if len(row_data) > 3 else 0
                        wins = int(row_data[4]) if len(row_data) > 4 else 0
                        losses = int(row_data[5]) if len(row_data) > 5 else 0
                        saves = int(row_data[6]) if len(row_data) > 6 else 0
                        
                        totals["games"] = totals.get("games", 0) + games
                        totals["wins"] = totals.get("wins", 0) + wins
                        totals["losses"] = totals.get("losses", 0) + losses
                        totals["saves"] = totals.get("saves", 0) + saves
                    except (ValueError, IndexError):
                        continue
        
        if totals.get("wins", 0) + totals.get("losses", 0) > 0:
            total_dec = totals["wins"] + totals["losses"]
            totals["win_pct"] = round(totals["wins"] / total_dec, 3)
        return totals

    def get_top_starters(self, team_name, top_n=5):
        """
        取得 NPB 球隊前 N 名先發投手個人數據
        從 baseball-data.com 投手頁面解析，以投球局數排序
        """
        code = TEAM_URL_CODES.get(team_name)
        if not code:
            return None
        
        url = f"https://baseball-data.com/stats/pitcher-{code}/"
        resp = self.session.get(url, timeout=15)
        if resp.status_code != 200:
            return None
        
        soup = BeautifulSoup(resp.text, "xml")
        self.fetched_sources.append("baseball-data.com")
        
        pitchers = []
        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            for row in rows[1:]:
                cells = row.find_all("td")
                if len(cells) >= 19:
                    cols = [c.get_text(strip=True) for c in cells]
                    try:
                        name = cols[1].replace("　", " ")
                        era_text = cols[2]
                        games = int(cols[3])
                        wins = int(cols[4])
                        losses = int(cols[5])
                        ip_text = cols[10]
                        k = int(cols[15])
                        bb = int(cols[13])
                        whip_text = cols[18]
                        
                        # 解析投球回 (如 "55.2" 表示 55又2/3局)
                        ip = 0
                        if "." in ip_text:
                            parts = ip_text.split(".")
                            ip = int(parts[0]) + int(parts[1]) / 3 if parts[1] else int(parts[0])
                        else:
                            ip = float(ip_text) if ip_text else 0
                        
                        era = float(era_text) if era_text else 0
                        whip = float(whip_text) if whip_text else 0
                        
                        # 過濾：至少先發過3場（近似：局數 > 15）才視為先發投手
                        if ip >= 5:  # 🆕 2026-07-18 放寬門檻
                            pitchers.append({
                                "name": name,
                                "era": era,
                                "whip": whip,
                                "k": k,
                                "bb": bb,
                                "ip": round(ip, 1),
                                "wins": wins,
                                "losses": losses,
                                "games": games,
                                "k_per_9": round(k * 9 / ip, 1) if ip > 0 else 0,
                                "bb_per_9": round(bb * 9 / ip, 1) if ip > 0 else 0,
                            })
                    except (ValueError, IndexError):
                        continue
        
        # 依投球局數排序（先發投手通常局數最多）
        pitchers.sort(key=lambda p: p["ip"], reverse=True)
        return pitchers[:top_n]

    def get_top_batters(self, team_name, top_n=5):
        """取得 NPB 球隊前 N 名主力打者（依 RBI 排序）

        優先從 DB 取（player_season_stats kind='hitter'），
        若 DB 無資料再 fallback 到 baseball-data.com 爬蟲。

        Args:
            team_name: NPB 球隊英文名（如 'Yomiuri Giants'）
            top_n: 取前 N 名（預設 5）

        Returns:
            list of dict: [{name, avg, hr, rbi, hits, ab}, ...]
        """
        batters = self.get_top_batters_from_db(team_name, top_n)
        if batters:
            self.fetched_sources.append("npb_hitter_rankings_2026 (DB)")
            return batters

        code = TEAM_URL_CODES.get(team_name)
        if not code:
            return []

        url = f"https://baseball-data.com/stats/hitter-{code}/"
        resp = self.session.get(url, timeout=15)
        if resp.status_code != 200:
            return []

        soup = BeautifulSoup(resp.text, 'html.parser')
        self.fetched_sources.append("baseball-data.com")
        
        batters = []
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            for row in rows[1:]:  # 跳過表頭
                cells = row.find_all('td')
                if len(cells) >= 9:
                    try:
                        name = cells[1].get_text(strip=True)
                        # 打率=2, 試合=3, 打席=4, 打數=5, 安打=6, 本塁打=7, 打點=8
                        avg_str = cells[2].get_text(strip=True)
                        ab_str = cells[5].get_text(strip=True)
                        hits_str = cells[6].get_text(strip=True)
                        hr_str = cells[7].get_text(strip=True)
                        rbi_str = cells[8].get_text(strip=True)

                        # 轉換為數值
                        avg = float(avg_str.replace("-", "0")) if avg_str else 0
                        ab = int(ab_str) if ab_str else 0
                        hits = int(hits_str) if hits_str else 0
                        hr = int(hr_str) if hr_str else 0
                        rbi = int(rbi_str) if rbi_str else 0

                        # baseball-data.com 無 OBP/SLG/OPS，設為 None
                        batters.append({
                            'name': name,
                            'position': '',
                            'avg': avg if avg > 0 else None,
                            'obp': None,
                            'slg': None,
                            'ops': None,
                            'hr': hr,
                            'rbi': rbi,
                            'hits': hits,
                            'ab': ab,
                            'source': 'baseball-data.com'
                        })
                    except (ValueError, IndexError):
                        continue

        # 依 RBI 排序（降冪）
        batters.sort(key=lambda x: x.get('rbi') or 0, reverse=True)
        return batters[:top_n]

    def get_top_batters_from_db(self, team_name, top_n=5):
        """從 DB 取 NPB 球隊前 N 名打者（依 RBI 排序）

        Args:
            team_name: NPB 球隊英文名（如 'Yomiuri Giants'）
            top_n: 取前 N 名（預設 5）

        Returns:
            list of dict: [{name, avg, hr, rbi, hits, ab, source}, ...]
            若 DB 無資料回傳空陣列
        """
        try:
            # 先取 team_id
            self.cur.execute(
                "SELECT team_id FROM predictx.teams WHERE english_name = %s AND league = 'NPB'",
                (team_name,)
            )
            team_row = self.cur.fetchone()
            if not team_row:
                return []
            team_id = team_row['team_id']

            # 取該隊打者 stats，依 RBI 排序
            self.cur.execute("""
                SELECT p.player_name, s.avg, s.b_hr, s.rbi, s.b_h, s.ab, s.obp, s.slg
                FROM predictx.player_season_stats s
                JOIN predictx.players p ON s.player_id = p.player_id
                JOIN predictx.player_teams pt ON p.player_id = pt.player_id
                LEFT JOIN predictx.player_aliases pa ON pa.player_id = p.player_id
                WHERE pt.team_id = %s
                  AND s.kind = 'hitter'
                  AND s.avg IS NOT NULL
                  AND s.rbi IS NOT NULL
                ORDER BY s.rbi DESC NULLS LAST, s.b_hr DESC NULLS LAST
                LIMIT %s
            """, (team_id, top_n))
            rows = self.cur.fetchall()
            if not rows:
                return []

            batters = []
            for r in rows:
                batters.append({
                    'name': r['player_name'],
                    'position': '',
                    'avg': float(r['avg']) if r['avg'] is not None else None,
                    'obp': float(r['obp']) if r['obp'] is not None else None,
                    'slg': float(r['slg']) if r['slg'] is not None else None,
                    'ops': (float(r['obp']) + float(r['slg'])) if (r['obp'] is not None and r['slg'] is not None) else None,
                    'hr': int(r['b_hr']) if r['b_hr'] is not None else 0,
                    'rbi': int(r['rbi']) if r['rbi'] is not None else 0,
                    'hits': int(r['b_h']) if r['b_h'] is not None else 0,
                    'ab': int(r['ab']) if r['ab'] is not None else 0,
                    'source': 'npb_hitter_rankings_2026 (DB)'
                })
            return batters
        except Exception as db_err:
            print(f"  ⚠ DB top_batters query error: {db_err}")
            return []

    def get_local_team_id(self, team_name):
        """查詢本地資料庫的 NPB 隊伍 ID"""
        """查詢本地資料庫的 NPB 隊伍 ID"""
        self.cur.execute(
            "SELECT team_id FROM predictx.teams WHERE english_name ILIKE %s AND league='NPB'",
            (f'%{team_name.split()[-1]}%',)
        )
        row = self.cur.fetchone()
        if row:
            return row['team_id']
        self.cur.execute(
            "SELECT team_id FROM predictx.teams WHERE english_name ILIKE %s AND league='NPB'",
            (f'%{team_name}%',)
        )
        row = self.cur.fetchone()
        return row['team_id'] if row else None

    def get_today_starters(self, match_date=None):
        """從 npb.jp 官方「予告先発投手」頁面爬取 NPB 當日先發投手名單
        
        Args:
            match_date: "YYYYMMDD" 格式字串（預設為今天）
        """
        if match_date is None:
            from datetime import date
            match_date = date.today().strftime('%Y%m%d')

        # 🆕 第一來源：npb.jp 官方公告頁（比 lottonavi 更可靠，Railway 不擋）
        official = self._get_starters_from_npb_official(match_date)
        if official:
            return official

        # 第二來源：lottonavi.com（Railway IP 常被 403）
        url = f"https://www.lottonavi.com/matches/npb/{match_date}"
        try:
            resp = self.session.get(url, timeout=15)
            if resp.status_code != 200:
                print(f"  ⚠ [npb-lottonavi] HTTP {resp.status_code} for {url}", flush=True)
                return None
            # 強制正確編碼（網站編碼偵測錯誤）
            if resp.encoding and resp.encoding.lower() in ('iso-8859-1', 'latin-1'):
                resp.encoding = 'utf-8'
        except Exception as lot_err:
            print(f"  ⚠ [npb-lottonavi] request error for {url}: {type(lot_err).__name__}: {lot_err}", flush=True)
            return None

        soup = BeautifulSoup(resp.text, 'lxml')
        if not soup.find_all('div', class_='table-responsive'):
            print(f"  ⚠ [npb-lottonavi] no .table-responsive divs found (HTML 結構可能改版), len(text)={len(resp.text)}", flush=True)
        self.fetched_sources.append("lottonavi.com")
        result = {}

        for div in soup.find_all('div', class_='table-responsive'):
            tables = div.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                if len(rows) < 4:
                    continue
                # 跳過標題行(0)和表頭行(1)，取資料行
                data_rows = rows[2:]
                if len(data_rows) < 2:
                    continue
                
                try:
                    # 第1筆資料 = 主隊（lottonavi 全部用 th 元素）
                    cells_home = data_rows[0].find_all(['th', 'td'])
                    # 第2筆資料 = 客隊  
                    cells_away = data_rows[1].find_all(['th', 'td'])
                    
                    if len(cells_home) < 5 or len(cells_away) < 5:
                        continue
                    
                    home_raw = cells_home[0].get_text(strip=True)
                    away_raw = cells_away[0].get_text(strip=True)
                    home_pitcher_name = cells_home[3].get_text(strip=True) if len(cells_home) > 3 else ""
                    away_pitcher_name = cells_away[3].get_text(strip=True) if len(cells_away) > 3 else ""
                    home_pitcher_rec = cells_home[4].get_text(strip=True) if len(cells_home) > 4 else ""
                    away_pitcher_rec = cells_away[4].get_text(strip=True) if len(cells_away) > 4 else ""
                    home_pitcher_era = cells_home[5].get_text(strip=True) if len(cells_home) > 5 else ""
                    away_pitcher_era = cells_away[5].get_text(strip=True) if len(cells_away) > 5 else ""
                    
                    home_en = self._resolve_lottonavi_team(home_raw)
                    away_en = self._resolve_lottonavi_team(away_raw)
                    if not home_en or not away_en:
                        continue
                    
                    result[f"{home_en}_vs_{away_en}"] = {
                        "home_team": home_en,
                        "away_team": away_en,
                        "home_pitcher": {"name": home_pitcher_name, "record": home_pitcher_rec, "era": home_pitcher_era},
                        "away_pitcher": {"name": away_pitcher_name, "record": away_pitcher_rec, "era": away_pitcher_era},
                    }
                except:
                    continue
        
        return result

    def _get_starters_from_npb_official(self, match_date):
        """從 npb.jp 官方「予告先発投手」頁面爬取當日先發投手

        URL: https://npb.jp/announcement/starter/
        頁面結構：每個 <div class="unit cl_N">（央聯）或 <div class="unit pl_N">（洋聯）
        代表一場賽事，內含：
          - <div class="team_left">  = 主隊先發投手（姓　名，全形空格 U+3000）
          - <div class="team_right"> = 客隊先發投手
          - <img alt="東京ヤクルトスワローズ"> = 主隊 logo
          - <img alt="中日ドラゴンズ"> = 客隊 logo
          - （球場）18:00 = 球場與開賽時間

        Args:
            match_date: "YYYYMMDD" 格式字串
        Returns:
            dict: {f"{home_en}_vs_{away_en}": {"home_team", "away_team",
                   "home_pitcher": {"name", ...}, "away_pitcher": {...}}}
            失敗或無資料時回傳 None（讓呼叫端 fallback 到 lottonavi）
        """
        url = "https://npb.jp/announcement/starter/"
        try:
            resp = self.session.get(url, timeout=15)
            if resp.status_code != 200:
                print(f"  ⚠ [npb-official] HTTP {resp.status_code} for {url}", flush=True)
                return None
            if resp.encoding and resp.encoding.lower() in ('iso-8859-1', 'latin-1'):
                resp.encoding = 'utf-8'
        except Exception as e:
            print(f"  ⚠ [npb-official] request error for {url}: {type(e).__name__}: {e}", flush=True)
            return None

        soup = BeautifulSoup(resp.text, 'lxml')

        # 定位當日段：格式「9月4日の予告先発投手」
        try:
            y, m, d = int(match_date[:4]), int(match_date[4:6]), int(match_date[6:8])
        except (ValueError, IndexError):
            return None
        target_text = f"{m}月{d}日の予告先発投手"
        idx = resp.text.find(target_text)
        if idx == -1:
            print(f"  ⚠ [npb-official] 找不到「{target_text}」段（可能尚未公布）", flush=True)
            return None

        # 只解析當日段之後的 HTML（避免抓到其他日期）
        chunk = resp.text[idx:]
        day_soup = BeautifulSoup(chunk, 'lxml')

        # 每場賽事 = <div class="unit cl_N"> 或 <div class="unit pl_N">
        units = day_soup.find_all('div', class_=re.compile(r'unit\s+(cl|pl)_\d+'))
        if not units:
            print(f"  ⚠ [npb-official] 未找到任何 unit cl/pl 賽事區塊", flush=True)
            return None

        self.fetched_sources.append("npb.jp/announcement/starter/")
        result = {}

        for u in units:
            left = u.find('div', class_='team_left')
            right = u.find('div', class_='team_right')
            logos = [img.get('alt', '') for img in u.find_all('img') if img.get('alt')]

            # 主客隊：logo 順序 [主隊, 客隊]
            home_en = None
            away_en = None
            for alt in logos:
                en = NPB_OFFICIAL_TEAM_MAP.get(alt)
                if en and home_en is None:
                    home_en = en
                elif en:
                    away_en = en
            if not home_en or not away_en:
                continue

            home_pitcher_name = left.get_text(strip=True) if left else ""
            away_pitcher_name = right.get_text(strip=True) if right else ""
            if not home_pitcher_name or not away_pitcher_name:
                continue

            result[f"{home_en}_vs_{away_en}"] = {
                "home_team": home_en,
                "away_team": away_en,
                "home_pitcher": {"name": home_pitcher_name, "record": "", "era": ""},
                "away_pitcher": {"name": away_pitcher_name, "record": "", "era": ""},
            }

        if not result:
            print(f"  ⚠ [npb-official] 解析到 0 場有效賽事", flush=True)
            return None

        print(f"  ✅ [npb-official] 取得 {len(result)} 場先發投手", flush=True)
        return result

    def _extract_lottonavi_teams(self, raw_text):
        """從 lottonavi 的對戰組合文字中提取主客隊"""
        # 範例: "中日龍 (央6) vs. 日本火腿鬥士 (洋4)"
        if 'vs.' in raw_text:
            parts = raw_text.split('vs.')
            if len(parts) == 2:
                return {'home': parts[0].strip(), 'away': parts[1].strip()}
        return None

    def _resolve_lottonavi_team(self, jp_name):
        """解析 lottonavi 隊名為英文全名"""
        # 移除括號內的資訊如 "(央6)"、"(洋4)"
        import re
        clean = re.sub(r'\(.*?\)', '', jp_name).strip()
        # 嘗試逐字比對
        for key, en in LOTTONAVI_TEAM_MAP.items():
            if key in clean:
                return en
        # 也試 TEAM_NAME_MAP
        for key, en in TEAM_NAME_MAP.items():
            if key in clean:
                return en
        return None

    def fetch_and_store_game_data(self, game_id, home_team_name, away_team_name):
        """為一場 NPB 比賽取得數據"""
        standings = self.get_standings()
        home_bat = self.get_team_batting_stats(home_team_name)
        home_pitch = self.get_team_pitching_stats(home_team_name)
        away_bat = self.get_team_batting_stats(away_team_name)
        away_pitch = self.get_team_pitching_stats(away_team_name)
        
        # 🆕 取得主力打者 Top 5
        home_top_batters = self.get_top_batters(home_team_name, 5)
        away_top_batters = self.get_top_batters(away_team_name, 5)

        home_stand = standings.get(home_team_name, {}) if standings else {}
        away_stand = standings.get(away_team_name, {}) if standings else {}

        # 🆕 主場球場修正（球隊 → 主場 → Park Factor）
        home_park = NPB_TEAM_HOME_PARK.get(home_team_name)
        park_factor = NPB_PARK_FACTORS.get(home_park, 1.0) if home_park else 1.0

        return {
            "home_team_name": home_team_name,
            "away_team_name": away_team_name,
            "standings": {"home": home_stand, "away": away_stand},
            "batting": {"home": home_bat or {}, "away": away_bat or {}},
            "pitching": {"home": home_pitch or {}, "away": away_pitch or {}},
            "top_batters": {"home": home_top_batters or [], "away": away_top_batters or []},
            "sources": list(set(self.fetched_sources)),
            # 🆕 Park Factor：>1.0 = 主場打者有利、<1.0 = 投手有利
            "home_park": home_park,
            "park_factor": park_factor,
        }

    def close(self):
        self.cur.close()
        self.conn.close()