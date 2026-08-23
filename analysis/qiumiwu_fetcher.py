"""
球迷屋 WNBA 數據爬蟲 - 作為 ESPN API 失效時的備用數據源
獨立模組，可單獨 import 使用
"""
import re
import requests

ESPN_TEAM_ID = {
    "Atlanta Dream": 20,
    "Chicago Sky": 19,
    "Connecticut Sun": 18,
    "Dallas Wings": 3,
    "Golden State Valkyries": 129689,
    "Indiana Fever": 5,
    "Las Vegas Aces": 17,
    "Los Angeles Sparks": 6,
    "Minnesota Lynx": 8,
    "New York Liberty": 9,
    "Phoenix Mercury": 11,
    "Seattle Storm": 14,
    "Washington Mystics": 16,
    "Portland Fire": 132052,
    "Toronto Tempo": 131935,
}


class QiumiwuWNBAFetcher:
    """球迷屋 WNBA 數據爬蟲"""

    BASE_URL = "https://www.qiumiwu.com/league/wnba/standings"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        })

    def fetch_standings(self):
        """抓取球迷屋 WNBA 積分榜

        Returns:
            dict: {team_name: stats_dict} 或 None
        """
        try:
            resp = self.session.get(self.BASE_URL, timeout=15)
            if resp.status_code != 200:
                print(f"  ⚠ 球迷屋 WNBA 積分榜 HTTP {resp.status_code}")
                return None
            return self._parse_standings(resp.text)
        except Exception as e:
            print(f"  ⚠ 球迷屋抓取失敗: {e}")
            return None

    def _parse_standings(self, html):
        """解析球迷屋積分榜 HTML"""
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            print("  ⚠ bs4 未安裝，球迷屋解析需要 beautifulsoup4")
            return None

        soup = BeautifulSoup(html, 'html.parser')
        stats_map = {}

        # 找到積分榜表格
        table = soup.find('table')
        if not table:
            table = soup.find('div', class_=re.compile(r'standings|ranking'))

        if not table:
            return None

        rows = table.find_all('tr')
        for row in rows:
            cols = row.find_all(['td', 'th'])
            if len(cols) < 10:
                continue

            try:
                rank_text = cols[0].get_text(strip=True)
                if not rank_text.isdigit():
                    continue

                team_cell = cols[1]
                team_name = team_cell.get_text(strip=True)
                team_name = re.sub(r'[🏆🥇🥈🥉]', '', team_name).strip()

                standard_name = self._match_team_name(team_name)
                if not standard_name:
                    continue

                cols_text = [col.get_text(strip=True) for col in cols]
                if len(cols_text) >= 14:
                    stats = {
                        'rank': int(cols_text[0]) if cols_text[0].isdigit() else 0,
                        'g': int(cols_text[2]) if cols_text[2].isdigit() else 0,
                        'wins': int(cols_text[3]) if cols_text[3].isdigit() else 0,
                        'losses': int(cols_text[4]) if cols_text[4].isdigit() else 0,
                        'win_pct': float(cols_text[5].replace('%', '')) / 100 if '%' in cols_text[5] else 0,
                        'home_record': cols_text[7] if len(cols_text) > 7 else '',
                        'road_record': cols_text[8] if len(cols_text) > 8 else '',
                        'pts_per_g': float(cols_text[9]) if cols_text[9].replace('.', '').isdigit() else 0,
                        'opp_pts_per_g': float(cols_text[10]) if cols_text[10].replace('.', '').isdigit() else 0,
                        'net_rtg': float(cols_text[11]) if cols_text[11].replace('.', '').replace('-', '').isdigit() else 0,
                        'last_10': cols_text[12] if len(cols_text) > 12 else '',
                        'streak': int(cols_text[13]) if cols_text[13].lstrip('-').isdigit() else 0,
                    }
                    stats_map[standard_name] = stats
            except Exception:
                continue

        return stats_map if stats_map else None

    def _match_team_name(self, qiumiwu_name):
        """球迷屋隊名 -> 標準隊名"""
        if qiumiwu_name in ESPN_TEAM_ID:
            return qiumiwu_name

        for espn_name in ESPN_TEAM_ID:
            if qiumiwu_name.lower() in espn_name.lower() or espn_name.lower() in qiumiwu_name.lower():
                return espn_name

        keyword_map = {
            'lynx': 'Minnesota Lynx',
            'valkyries': 'Golden State Valkyries',
            'aces': 'Las Vegas Aces',
            'sun': 'Connecticut Sun',
            'fever': 'Indiana Fever',
            'liberty': 'New York Liberty',
            'mystics': 'Washington Mystics',
            'wings': 'Dallas Wings',
            'dream': 'Atlanta Dream',
            'sparks': 'Los Angeles Sparks',
            'mercury': 'Phoenix Mercury',
            'storm': 'Seattle Storm',
            'sky': 'Chicago Sky',
            'fire': 'Portland Fire',
            'tempo': 'Toronto Tempo',
        }
        for keyword, standard in keyword_map.items():
            if keyword in qiumiwu_name.lower():
                return standard
        return None
