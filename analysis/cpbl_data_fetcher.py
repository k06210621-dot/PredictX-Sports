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
        self.conn = None
        self.cur = None
        if conn:
            self.conn = conn
            self.cur = conn.cursor(cursor_factory=RealDictCursor)
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
                pass  # DB 連線失敗不影響 HTTP-based 方法（如 get_today_starting_pitchers）
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept-Language": "zh-TW,zh;q=0.9",
        })
        # Railway Python SSL 環境無法驗證 cpbl.com.tw 憑證，全域關閉驗證
        self.session.verify = False
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
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
        """從 CPBL 官網抓取打擊排行榜（舊版，只抓前頁）"""
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

    def get_hitting_leaderboard_from_sportify(self):
        """從 sportify.tw 抓取完整的 CPBL 打擊排行榜（含 OPS/OBP/SLG）

        Returns:
            list of dict: [{name, team_en, pa, h, hr, rbi, bb, avg, obp, slg, ops}, ...]
            若抓取失敗回傳 None
        """
        try:
            url = "https://sportify.tw/zh-CN/stats/batting?league=cpbl&season=2026&type=1"
            # sportify.tw 需要 TLS 1.2+，Railway 環境可能不支援，關閉 SSL 驗證
            resp = self.session.get(url, timeout=15, verify=False)
            if resp.status_code != 200:
                print(f"  ⚠ sportify.tw returned HTTP {resp.status_code}")
                return None

            self.fetched_sources.append("sportify.tw")
            soup = BeautifulSoup(resp.text, 'lxml')
            tables = soup.find_all('table')
            if not tables:
                return None

            # Sportify 有兩個表格：第一個是 PA 排序，第二個是 OPS 排序
            # 我們抓取第一個表格（預設按 PA 排序）
            table = tables[0]
            rows = table.find('tbody').find_all('tr') if table.find('tbody') else table.find_all('tr')[1:]

            hitters = []
            for row in rows:
                cells = row.find_all('td')
                if len(cells) < 10:
                    continue

                # 解析球員姓名和球隊
                # 格式：「富 张育成 富邦悍将」或「统 陈傑憲 统一狮」
                team_cell = cells[1].get_text(strip=True)
                
                # 球隊縮寫對照
                team_code_map = {
                    '富': 'Fubon Guardians',
                    '乐': 'Rakuten Monkeys',
                    '统': 'Uni-President 7-ELEVEn Lions',
                    '台': 'TSG Hawks',
                    '中': 'CTBC Brothers',
                    '味': 'Wei Chuan Dragons',
                }
                
                # 取出球隊縮寫（第一個字）
                team_code = team_cell[0] if team_cell else ''
                team_en = team_code_map.get(team_code, '')
                
                # 球員姓名：通常在球隊縮寫和全名之間，需要解析 HTML
                name_link = cells[1].find('a')
                name = name_link.get_text(strip=True) if name_link else ''
                
                # 解析數據欄位
                pa = cells[2].get_text(strip=True)
                hits = cells[3].get_text(strip=True)
                hr = cells[4].get_text(strip=True)
                rbi = cells[5].get_text(strip=True)
                bb = cells[6].get_text(strip=True)
                avg = cells[7].get_text(strip=True)
                obp = cells[8].get_text(strip=True)
                slg = cells[9].get_text(strip=True)
                ops = cells[10].get_text(strip=True) if len(cells) > 10 else None

                # 轉換為數值
                def to_float(val):
                    try:
                        return float(val) if val else None
                    except:
                        return None

                def to_int(val):
                    try:
                        return int(val) if val else None
                    except:
                        return None

                hitters.append({
                    'name': name,
                    'team_en': team_en,
                    'pa': to_int(pa),
                    'hits': to_int(hits),
                    'hr': to_int(hr),
                    'rbi': to_int(rbi),
                    'bb': to_int(bb),
                    'avg': to_float(avg),
                    'obp': to_float(obp),
                    'slg': to_float(slg),
                    'ops': to_float(ops),
                })

            return hitters

        except Exception as e:
            print(f"  ⚠ sportify.tw fetch error: {e}")
            return None

    def get_top_batters(self, team_en, top_n=5):
        """取得 CPBL 指定球隊前 N 名主力打者（依 RBI 排序）

        預設使用 cpbl.com.tw（Railway 相容），
        若需 OPS/OBP/SLG 等進階數據，可手動啟用 sportify.tw 數據源。

        Args:
            team_en: 球隊英文名（如 'CTBC Brothers'）
            top_n: 取前 N 名（預設 5）

        Returns:
            list of dict: [{name, avg, obp, slg, ops, hr, rbi, hits, ab}, ...]
            若抓取失敗回傳空陣列
        """
        # 預設使用 cpbl.com.tw（Railway 相容）
        # sportify.tw 需要 TLS 1.2+，在舊版 LibreSSL 環境會失敗
        hitters = self.get_hitting_leaderboard()
        source = 'cpbl.com.tw'
        
        # 嘗試 sportify.tw（若需要進階數據）
        # 註：在本地 macOS 可能成功，但在 Railway 會因 SSL 限制失敗
        # if not hitters or source == 'cpbl.com.tw':
        #     sportify_hitters = self.get_hitting_leaderboard_from_sportify()
        #     if sportify_hitters:
        #         hitters = sportify_hitters
        #         source = 'sportify.tw'
        
        if not hitters:
            return []

        # 過濾指定球隊
        team_hitters = [h for h in hitters if h.get('team_en') == team_en]

        # 依 RBI 排序（降冪）
        team_hitters.sort(key=lambda x: int(x.get('rbi', 0) or 0), reverse=True)

        # 取前 N 名，格式化成與 MLB 一致的結構
        result = []
        for h in team_hitters[:top_n]:
            name = h.get('name', '')
            avg = h.get('avg')
            obp = h.get('obp')
            slg = h.get('slg')
            ops = h.get('ops')
            hr = int(h.get('hr', 0) or 0)
            rbi = int(h.get('rbi', 0) or 0)
            hits = int(h.get('hits', 0) or 0)
            
            # 計算 AB（打數）= PA - BB - HBP（粗略估算）
            pa = int(h.get('pa', 0) or 0)
            bb = int(h.get('bb', 0) or 0)
            ab = max(0, pa - bb)  # 粗略估算

            result.append({
                'name': name,
                'position': '',  # cpbl.com.tw 無守備位置
                'avg': avg,
                'obp': obp,
                'slg': slg,
                'ops': ops,
                'hr': hr,
                'rbi': rbi,
                'hits': hits,
                'ab': ab,
            })

        self.fetched_sources.append(source)
        return result

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

        # 🆕 主力打者數據（依 RBI 取前 5 名）
        home_top5 = self.get_top_batters(home_team_name, top_n=5) or []
        away_top5 = self.get_top_batters(away_team_name, top_n=5) or []

        return {
            "home_team_name": home_team_name,
            "away_team_name": away_team_name,
            "players": {"home": home_ps, "away": away_ps},
            "hitting_leaders": {"home": home_hitters[:5], "away": away_hitters[:5]},
            "top_batters": {"home": home_top5, "away": away_top5},  # 🆕 新增
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
            date_str = str(match_date).replace('-', '/')

        try:
            # 1. 重新取得首頁以獲取最新的 __RequestVerificationToken
            # 使用 requests + verify=False 繞過 Railway SSL 限制
            print(f"  [CPBL SP] Fetching cpbl.com.tw homepage for token...", flush=True)
            home_resp = self.session.get("https://www.cpbl.com.tw/", timeout=10)
            if home_resp.status_code != 200:
                print(f"  [CPBL SP] Homepage returned HTTP {home_resp.status_code}", flush=True)
                return None

            token_match = re.search(
                r'__RequestVerificationToken"\s*type="hidden"\s*value="([^"]+)"',
                home_resp.text
            )
            if not token_match:
                print(f"  [CPBL SP] Token not found in homepage HTML", flush=True)
                return None
            token = token_match.group(1)
            print(f"  [CPBL SP] Token found, calling API for date={date_str}", flush=True)

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
                verify=False,
            )
            if resp.status_code != 200:
                print(f"  [CPBL SP] API returned HTTP {resp.status_code}", flush=True)
                # 印出部分 body 方便 Railway 診斷
                body_preview = (resp.text or '')[:200].replace('\n', ' ')
                print(f"  [CPBL SP] Body preview: {body_preview}", flush=True)
                # Retry 一次：重新拿 token 再試
                if resp.status_code == 404:
                    print(f"  [CPBL SP] Retrying with fresh token...", flush=True)
                    home2 = self.session.get("https://www.cpbl.com.tw/", timeout=10)
                    token_match2 = re.search(
                        r'__RequestVerificationToken"\s*type="hidden"\s*value="([^"]+)"',
                        home2.text
                    )
                    if token_match2:
                        resp = self.session.post(
                            "https://www.cpbl.com.tw/home/getdetaillist",
                            data={
                                "GameDate": date_str,
                                "KindCode": "A",
                                "GameSno": "",
                                "__RequestVerificationToken": token_match2.group(1),
                            },
                            timeout=15,
                            verify=False,
                            headers={"Referer": "https://www.cpbl.com.tw/"},
                        )
                        if resp.status_code != 200:
                            print(f"  [CPBL SP] Retry still HTTP {resp.status_code}", flush=True)
                            return None
                        print(f"  [CPBL SP] Retry succeeded with HTTP {resp.status_code}", flush=True)
                    else:
                        return None
                else:
                    return None

            result = resp.json()
            if not result.get('Success'):
                print(f"  [CPBL SP] API returned Success=False", flush=True)
                return None

            games_raw = result.get('GameADetailJson')
            if not games_raw:
                print(f"  [CPBL SP] No GameADetailJson in response", flush=True)
                return None
            games = json.loads(games_raw)
            if not games:
                print(f"  [CPBL SP] Empty games array", flush=True)
                return None

            print(f"  [CPBL SP] Got {len(games)} games from API", flush=True)

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