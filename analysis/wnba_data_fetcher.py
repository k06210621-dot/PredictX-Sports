"""
PredictX Sports — WNBA DataFetcher
從 basketball-reference.com 爬取 WNBA 進階數據（免費，無需 API Key）

數據來源：
- https://www.basketball-reference.com/wnba/years/2026.html
  - per_game-team: 場均數據（PTS, FG%, 3P%, FT%, REB, AST, STL, BLK, TOV）
  - per_poss-team: 每 100 回合數據（Pace, OffRtg, DefRtg）
  - advanced-team: 進階數據（NRtg, MOV, SOS, SRS）
"""
import os
import re
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from bs4 import BeautifulSoup

DB_CONFIG = {
    "dbname": "sports_db", "user": "jero",
    "password": "", "host": "localhost", "port": 5432
}

# basketball-reference.com 隊名 → DB 統一隊名
WNBA_TEAM_NAME_MAP = {
    "Las Vegas Aces": "Las Vegas Aces",
    "New York Liberty": "New York Liberty",
    "Minnesota Lynx": "Minnesota Lynx",
    "Connecticut Sun": "Connecticut Sun",
    "Seattle Storm": "Seattle Storm",
    "Phoenix Mercury": "Phoenix Mercury",
    "Chicago Sky": "Chicago Sky",
    "Dallas Wings": "Dallas Wings",
    "Atlanta Dream": "Atlanta Dream",
    "Indiana Fever": "Indiana Fever",
    "Los Angeles Sparks": "Los Angeles Sparks",
    "Washington Mystics": "Washington Mystics",
    "Golden State Valkyries": "Golden State Valkyries",
    "Portland Fire": "Portland Fire",
    "Toronto Tempo": "Toronto Tempo",
}


class WNBADataFetcher:
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
                pass
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        })
        self.fetched_sources = []
        self._stats_cache = None  # 快取全聯盟數據（同一次分析只抓一次）

    def _fetch_league_stats(self, season=2026):
        """抓取全聯盟進階數據（帶快取）"""
        if self._stats_cache is not None:
            return self._stats_cache

        url = f"https://www.basketball-reference.com/wnba/years/{season}.html"
        try:
            resp = self.session.get(url, timeout=20)
            if resp.status_code != 200:
                print(f"  ⚠ WNBA bball-ref HTTP {resp.status_code}")
                return {}
        except Exception as e:
            print(f"  ⚠ WNBA bball-ref fetch error: {e}")
            return {}

        soup = BeautifulSoup(resp.text, 'lxml')
        self.fetched_sources.append("basketball-reference.com")

        stats_map = {}

        # 1. per_game-team: 場均數據
        pg_table = soup.find('table', id='per_game-team')
        if pg_table:
            for row in pg_table.find_all('tr'):
                cells = row.find_all(['th', 'td'])
                if not cells:
                    continue
                team_link = row.find('a')
                if not team_link:
                    continue
                team_name = team_link.get_text(strip=True)
                if team_name not in WNBA_TEAM_NAME_MAP:
                    continue

                def _get(stat_name):
                    cell = row.find('td', {'data-stat': stat_name})
                    return cell.get_text(strip=True) if cell else '0'

                stats_map[team_name] = {
                    'g': int(_get('g') or 0),
                    'pts_per_g': float(_get('pts') or 0),
                    'opp_pts_per_g': float(_get('opp_pts_per_g') or 0),
                    'fg_pct': float(_get('fg_pct') or 0),
                    'fg3_pct': float(_get('fg3_pct') or 0),
                    'ft_pct': float(_get('ft_pct') or 0),
                    'orb_per_g': float(_get('orb') or 0),
                    'drb_per_g': float(_get('drb') or 0),
                    'trb_per_g': float(_get('trb') or 0),
                    'ast_per_g': float(_get('ast') or 0),
                    'stl_per_g': float(_get('stl') or 0),
                    'blk_per_g': float(_get('blk') or 0),
                    'tov_per_g': float(_get('tov') or 0),
                }

        # 2. advanced-team: OffRtg / DefRtg / NRtg / Pace / MOV / SOS / SRS
        adv_table = soup.find('table', id='advanced-team')
        if adv_table:
            for row in adv_table.find_all('tr'):
                team_link = row.find('a')
                if not team_link:
                    continue
                team_name = team_link.get_text(strip=True)
                if team_name not in stats_map:
                    continue

                def _get(stat_name):
                    cell = row.find('td', {'data-stat': stat_name})
                    return cell.get_text(strip=True) if cell else '0'

                stats_map[team_name]['off_rtg'] = float(_get('off_rtg') or 0)
                stats_map[team_name]['def_rtg'] = float(_get('def_rtg') or 0)
                net_raw = _get('net_rtg')
                stats_map[team_name]['net_rtg'] = float(net_raw.replace('+', '').replace('-', '') or 0) * (-1 if net_raw.startswith('-') else 1)
                stats_map[team_name]['pace'] = float(_get('pace') or 0)
                stats_map[team_name]['mov'] = float(_get('mov') or 0)
                stats_map[team_name]['sos'] = float(_get('sos') or 0)
                stats_map[team_name]['srs'] = float(_get('srs') or 0)
                stats_map[team_name]['wins'] = int(_get('wins') or 0)
                stats_map[team_name]['losses'] = int(_get('losses') or 0)
                stats_map[team_name]['ts_pct'] = float(_get('ts_pct') or 0)
                stats_map[team_name]['efg_pct'] = float(_get('efg_pct') or 0)
                stats_map[team_name]['tov_pct'] = float(_get('tov_pct') or 0)
                stats_map[team_name]['orb_pct'] = float(_get('orb_pct') or 0)

        self._stats_cache = stats_map
        return stats_map

    def _match_team(self, local_name):
        """比對本地隊名與 basketball-reference 隊名"""
        if local_name in WNBA_TEAM_NAME_MAP:
            return local_name
        # 用最後一個詞比對
        parts = local_name.split()[-1].lower()
        for br_name in WNBA_TEAM_NAME_MAP:
            if parts in br_name.lower():
                return br_name
        # 模糊比對
        for br_name in WNBA_TEAM_NAME_MAP:
            if local_name.lower()[:5] in br_name.lower() or br_name.lower()[:5] in local_name.lower():
                return br_name
        return None

    def fetch_and_store_game_data(self, game_id, home_team_name, away_team_name):
        """為一場 WNBA 比賽取得進階數據"""
        all_stats = self._fetch_league_stats()
        if not all_stats:
            return None

        home_key = self._match_team(home_team_name)
        away_key = self._match_team(away_team_name)

        if not home_key or not away_key:
            print(f"  ⚠ WNBA team match failed: {home_team_name}→{home_key}, {away_team_name}→{away_key}")
            return None

        home_stats = all_stats.get(home_key, {})
        away_stats = all_stats.get(away_key, {})

        if not home_stats or not away_stats:
            return None

        return {
            "home_team_name": home_team_name,
            "away_team_name": away_team_name,
            "team_stats": {"home": home_stats, "away": away_stats},
            "sources": list(set(self.fetched_sources)),
        }

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
