"""
PredictX Sports — CPBL DataFetcher 強化版
從 cpbl.com.tw 爬取打擊排行榜 + 戰績 + 投打數據
"""
import requests
import os
import re
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from bs4 import BeautifulSoup
from datetime import datetime

DB_CONFIG = {
    "dbname": "sports_db", "user": "jero",
    "password": "", "host": "localhost", "port": 5432
}

TEAM_MAP = {
    "樂天桃猿": "Rakuten Monkeys",
    "味全龍": "Wei Chuan Dragons",
    "台鋼雄鷹": "TSG Hawks",
    "統一7-ELEVEn獅": "Uni-President 7-ELEVEn Lions",
    "中信兄弟": "CTBC Brothers",
    "富邦悍將": "Fubon Guardians",
}

class CPBLDataFetcher:
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
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept-Language": "zh-TW,zh;q=0.9",
        })
        self.fetched_sources = []
        self._init_session()

    def _init_session(self):
        try:
            self.session.get("https://www.cpbl.com.tw/", timeout=10)
        except Exception:
            pass

    def get_players_from_rankings(self):
        resp = self.session.get("https://stats.cpbl.com.tw/rankings", timeout=15)
        if resp.status_code != 200:
            return None
        self.fetched_sources.append("stats.cpbl.com.tw")
        parts = re.findall(r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', resp.text, re.DOTALL)
        if not parts:
            return None
        data = json.loads(parts[0])
        items = data.get('mainEntity', {}).get('itemListElement', [])
        players_by_team = {}
        for item in items:
            player = item.get('item', {})
            team_cn = player.get('affiliation', {}).get('name', 'Unknown')
            team_en = TEAM_MAP.get(team_cn, team_cn)
            pid = player.get('url', '').split('/')[-1]
            name = player.get('name', '')
            if team_en not in players_by_team:
                players_by_team[team_en] = []
            players_by_team[team_en].append({"name": name, "id": pid})
        return players_by_team

    def get_hitting_leaderboard(self):
        resp = self.session.get("https://www.cpbl.com.tw/stats/recordall", timeout=15)
        if resp.status_code != 200:
            return None
        self.fetched_sources.append("cpbl.com.tw")
        soup = BeautifulSoup(resp.text, 'lxml')
        table = soup.find('table')
        if not table:
            return None
        rows = table.find_all('tr')
        hitters = []
        for row in rows[1:]:
            cells = row.find_all('td')
            if len(cells) >= 15:
                raw = cells[0].get_text(strip=True)
                team_cn = ''
                name = raw
                for tc in sorted(TEAM_MAP.keys(), key=len, reverse=True):
                    if tc in raw:
                        team_cn = tc
                        name = raw.replace(tc, '').lstrip('0123456789')
                        break
                if not team_cn:
                    name = raw.lstrip('0123456789')
                team_en = TEAM_MAP.get(team_cn, '')
                rank = raw[0] if raw[0].isdigit() else '?'
                hitters.append({
                    'rank': rank, 'name': name, 'team_en': team_en,
                    'avg': cells[1].get_text(strip=True),
                    'games': cells[2].get_text(strip=True),
                    'pa': cells[3].get_text(strip=True),
                    'ab': cells[4].get_text(strip=True),
                    'runs': cells[5].get_text(strip=True),
                    'rbi': cells[6].get_text(strip=True),
                    'hits': cells[7].get_text(strip=True),
                    'hr': cells[11].get_text(strip=True),
                    'bb': cells[12].get_text(strip=True),
                    'so': cells[13].get_text(strip=True),
                    'sb': cells[14].get_text(strip=True),
                })
        return hitters

    def get_team_standings(self):
        resp = self.session.get("https://www.cpbl.com.tw/standings/season", timeout=15)
        if resp.status_code != 200:
            return None
        self.fetched_sources.append("cpbl.com.tw")
        soup = BeautifulSoup(resp.text, 'lxml')
        tables = soup.find_all('table')
        if len(tables) < 3:
            return None

        # Table 0: standings + H2H
        standings = {}
        rows = tables[0].find_all('tr')
        header_cells = rows[0].find_all('th')
        team_headers = [c.get_text(strip=True) for c in header_cells[6:]] if len(header_cells) > 6 else []
        for row in rows[1:]:
            cells = row.find_all('td')
            if not cells:
                continue
            raw = cells[0].get_text(strip=True)
            team_cn = raw[1:]
            team_en = TEAM_MAP.get(team_cn, '')
            if not team_en:
                continue
            h2h = {}
            for idx, h_team_cn in enumerate(team_headers):
                if idx + 6 < len(cells):
                    val = cells[idx + 6].get_text(strip=True)
                    if val:
                        parts = val.split('-')
                        h2h[h_team_cn] = {
                            'wins': parts[0] if len(parts) > 0 else '0',
                            'ties': parts[1] if len(parts) > 1 else '0',
                            'losses': parts[2] if len(parts) > 2 else '0',
                        }
            standings[team_en] = {
                'rank': raw[0], 'games': cells[1].get_text(strip=True),
                'wl_record': cells[2].get_text(strip=True),
                'win_pct': cells[3].get_text(strip=True),
                'h2h': h2h,
            }

        # Table 1: pitching
        pitching = {}
        rows = tables[1].find_all('tr')
        for row in rows[1:]:
            cells = row.find_all('td')
            if not cells:
                continue
            team_cn = cells[0].get_text(strip=True)
            team_en = TEAM_MAP.get(team_cn, '')
            if not team_en:
                continue
            er = int(cells[11].get_text(strip=True)) if len(cells) > 11 else 0
            ip_bf = int(cells[2].get_text(strip=True)) if len(cells) > 2 else 1
            pitching[team_en] = {
                'era': round(er * 9 / (ip_bf / 3), 2) if ip_bf > 0 else 0,
                'hits_allowed': cells[4].get_text(strip=True),
                'hr_allowed': cells[5].get_text(strip=True),
                'bb': cells[6].get_text(strip=True),
                'so': cells[7].get_text(strip=True),
                'runs_allowed': cells[10].get_text(strip=True),
            }

        # Table 2: batting
        batting = {}
        rows = tables[2].find_all('tr')
        for row in rows[1:]:
            cells = row.find_all('td')
            if not cells:
                continue
            team_cn = cells[0].get_text(strip=True)
            team_en = TEAM_MAP.get(team_cn, '')
            if not team_en:
                continue
            batting[team_en] = {
                'games': cells[1].get_text(strip=True),
                'runs': cells[2].get_text(strip=True),
                'hits': cells[4].get_text(strip=True),
                'hr': cells[5].get_text(strip=True),
                'so': cells[7].get_text(strip=True),
                'bb': cells[8].get_text(strip=True),
                'obp': cells[10].get_text(strip=True) if len(cells) > 10 else '.000',
            }

        return {'standings': standings, 'pitching': pitching, 'batting': batting}

    def get_local_team_id(self, team_name):
        self.cur.execute(
            "SELECT team_id FROM predictx.teams WHERE english_name ILIKE %s AND league='CPBL'",
            (f'%{team_name.split()[-1]}%',)
        )
        row = self.cur.fetchone()
        if row:
            return row['team_id']
        self.cur.execute(
            "SELECT team_id FROM predictx.teams WHERE english_name ILIKE %s AND league='CPBL'",
            (f'%{team_name}%',)
        )
        row = self.cur.fetchone()
        return row['team_id'] if row else None

    def fetch_and_store_game_data(self, game_id, home_team_name, away_team_name):
        players = self.get_players_from_rankings()
        hitters = self.get_hitting_leaderboard()
        team_data = self.get_team_standings()

        home_ps = (players or {}).get(home_team_name, [])
        away_ps = (players or {}).get(away_team_name, [])
        home_hitters = [h for h in (hitters or []) if h['team_en'] == home_team_name]
        away_hitters = [h for h in (hitters or []) if h['team_en'] == away_team_name]

        home_stand = (team_data or {}).get('standings', {}).get(home_team_name, {})
        away_stand = (team_data or {}).get('standings', {}).get(away_team_name, {})
        home_pitch = (team_data or {}).get('pitching', {}).get(home_team_name, {})
        away_pitch = (team_data or {}).get('pitching', {}).get(away_team_name, {})
        home_bat = (team_data or {}).get('batting', {}).get(home_team_name, {})
        away_bat = (team_data or {}).get('batting', {}).get(away_team_name, {})

        return {
            "home_team_name": home_team_name,
            "away_team_name": away_team_name,
            "players": {"home": home_ps, "away": away_ps},
            "hitting_leaders": {"home": home_hitters[:5], "away": away_hitters[:5]},
            "standings": {"home": home_stand, "away": away_stand},
            "pitching": {"home": home_pitch, "away": away_pitch},
            "batting": {"home": home_bat, "away": away_bat},
            "sources": list(set(self.fetched_sources))
        }

    def get_today_starting_pitchers(self, match_date=None):
        """
        從 CPBL 官網 API 取得當日比賽的先發投手名單

        Args:
            match_date: datetime.date 或 "yyyy/MM/dd" 格式字串（預設為今天台北時間）

        Returns:
            dict: { "home_team_en": {"name": "投手名", "acnt": "..."},
                    "away_team_en": {"name": "投手名", "acnt": "..."} }
            若無資料或失敗回傳 None
        """
        from datetime import date

        if match_date is None:
            match_date = date.today()
        if hasattr(match_date, 'strftime'):
            date_str = match_date.strftime('%Y/%m/%d')
        else:
            # 字串格式如 "2026-07-05" → 轉為 "2026/07/05"
            date_str = str(match_date).replace('-', '/')

        try:
            # 1. 重新取得首頁以獲取最新的 __RequestVerificationToken
            home_resp = self.session.get("https://www.cpbl.com.tw/", timeout=10)
            if home_resp.status_code != 200:
                return None

            token_match = re.search(
                r'__RequestVerificationToken"\s*type="hidden"\s*value="([^"]+)"',
                home_resp.text
            )
            if not token_match:
                return None
            token = token_match.group(1)

            # 2. 呼叫 API 取得當日賽程 + 先發投手
            resp = self.session.post(
                "https://www.cpbl.com.tw/home/getdetaillist",
                data={
                    "GameDate": date_str,
                    "KindCode": "A",
                    "GameSno": "",
                    "__RequestVerificationToken": token,
                },
                timeout=15,
            )
            if resp.status_code != 200:
                return None

            result = resp.json()
            if not result.get('Success'):
                return None

            games_raw = result.get('GameADetailJson')
            if not games_raw:
                return None
            games = json.loads(games_raw)
            if not games:
                return None

            self.fetched_sources.append("cpbl.com.tw")

            # 3. 解析每場比賽的先發投手
            starters = {}
            for g in games:
                home_cn = g.get('HomeTeamName', '')
                away_cn = g.get('VisitingTeamName', '')
                home_en = TEAM_MAP.get(home_cn, home_cn)
                away_en = TEAM_MAP.get(away_cn, away_cn)

                home_pitcher = g.get('HomeFirstMover', '')
                away_pitcher = g.get('VisitingFirstMover', '')
                home_acnt = g.get('HomeFirstAcnt', '')
                away_acnt = g.get('VisitingFirstAcnt', '')

                if home_pitcher:
                    starters[home_en] = {
                        'name': home_pitcher,
                        'acnt': home_acnt,
                    }
                if away_pitcher:
                    starters[away_en] = {
                        'name': away_pitcher,
                        'acnt': away_acnt,
                    }

            return starters if starters else None

        except Exception as e:
            print(f"  ⚠ CPBL starting pitcher fetch error: {e}")
            return None

    def close(self):
        self.cur.close()
        self.conn.close()

    def get_cpbl_pitchers_from_sportify(self, season=2026):
        """
        從 sportify.tw 爬取 CPBL 全聯盟投手個人數據
        使用 curl 繞過 Python 3.9 SSL 限制
        """
        import subprocess, re, json
        
        url = f"https://sportify.tw/zh-TW/stats/pitching?season={season}&type=1&min=10&sort=whip&order=desc"
        
        try:
            # 使用系統 curl（支援現代 TLS）
            result = subprocess.run(
                ["curl", "-s", "--connect-timeout", "10", url],
                capture_output=True, text=True, timeout=20
            )
            html = result.stdout
            if result.returncode != 0 or not html:
                return None
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None
        
        self.fetched_sources.append("sportify.tw")
        
        match = re.search(r'__RESOLVED_RESOURCES\[3\]\s*=\s*"(.+?)";', html)
        if not match:
            return None
        
        raw = match.group(1)
        try:
            decoded = json.loads('"' + raw + '"')
            data = json.loads(decoded)
        except (json.JSONDecodeError, KeyError, TypeError):
            return None
        
        pitchers = data.get('Ok', {}).get('data', []) if isinstance(data, dict) else []
        if not pitchers:
            return None
        
        teams = {}
        for p in pitchers:
            tn = p.get('team_name', '')
            if not tn:
                continue
            
            team_cn_map = {
                "中信兄弟": "CTBC Brothers",
                "統一獅": "Uni-President 7-ELEVEn Lions",
                "富邦悍將": "Fubon Guardians",
                "味全龍": "Wei Chuan Dragons",
                "台鋼雄鷹": "TSG Hawks",
                "樂天桃猿": "Rakuten Monkeys",
            }
            team_en = tn
            for cn, en in team_cn_map.items():
                if cn in tn:
                    team_en = en
                    break
            
            if team_en not in teams:
                teams[team_en] = []
            
            ip_str = p.get('ip', '0')
            ip = 0
            if '.' in ip_str:
                parts = ip_str.split('.')
                ip = int(parts[0]) + int(parts[1]) / 3 if parts[1] else int(parts[0])
            else:
                try:
                    ip = float(ip_str)
                except (ValueError, TypeError):
                    ip = 0
            
            era_val = float(p.get('era', 0)) if p.get('era') else 0
            whip_val = float(p.get('whip', 0)) if p.get('whip') else 0
            
            teams[team_en].append({
                'name': p.get('player_name', '?'),
                'era': era_val,
                'whip': whip_val,
                'k': p.get('strikeouts', 0),
                'bb': p.get('bb', 0),
                'ip': round(ip, 1),
                'wins': p.get('wins', 0),
                'losses': p.get('losses', 0),
                'games': p.get('games', 0),
                'k_per_9': round(p.get('strikeouts', 0) * 9 / ip, 1) if ip > 0 else 0,
                'bb_per_9': round(p.get('bb', 0) * 9 / ip, 1) if ip > 0 else 0,
            })
        
        result = {}
        for team, ps in teams.items():
            ps.sort(key=lambda x: x['ip'], reverse=True)
            result[team] = ps[:5]
        
        return result