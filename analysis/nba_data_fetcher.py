"""
PredictX Sports — NBA DataFetcher
數據來源（2026-10-01 換源）：basketball-reference.com
- stats.nba.com（nba_api 後端）已失效：本機 + Railway 容器皆 timeout/500
- www.nba.com/stats 頁面 200 但統計表是 client-side 渲染，純 HTTP 爬不到
- basketball-reference.com 本機 + Railway 容器皆 200，advanced-team 表含
  ORtg/DRtg/NRtg/Pace/TS%/eFG%/TOV% 等 engine 消費欄位
"""
import re

import requests
from bs4 import BeautifulSoup

# DB 隊名 → basketball-reference 隊名別名（BR 用「LA Clippers」等縮寫）
BR_TEAM_ALIASES = {
    "Los Angeles Clippers": "LA Clippers",
}

def _br_url(season):
    """season '2025-26' → basketball-reference URL（用結束年）：NBA_2026.html"""
    end_year = int(season.split("-")[0]) + 1
    return f"https://www.basketball-reference.com/leagues/NBA_{end_year}.html"

# basketball-reference advanced-team 表固定欄位順序（0-based，Rk 在 index 0）
# 表頭：Rk, Team, Age, W, L, PW, PL, MOV, SOS, SRS, ORtg, DRtg, NRtg, Pace,
#       FTr, 3PAr, TS%, eFG%, TOV%, ORB%, FT/FGA, eFG%, TOV%, DRB%, FT/FGA, Arena, Attend., Attend./G
_ADV_COLS = {
    "team": 1, "wins": 3, "losses": 4,
    "off_rtg": 10, "def_rtg": 11, "net_rating": 12, "pace": 13,
    "ts_pct": 16, "efg_pct": 17, "tov_pct": 18, "orb_pct": 19,
}


def _to_float(value):
    """安全轉 float：空字串/None → 0.0；'%' 百分比 → 小數；'*' 註記 → 忽略"""
    if value is None:
        return 0.0
    s = str(value).strip()
    if not s:
        return 0.0
    s = s.replace("*", "").replace(",", "")
    if s.endswith("%"):
        try:
            return float(s[:-1]) / 100.0
        except ValueError:
            return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def _current_season():
    """動態賽季：8-12 月屬秋季新賽季（YYYY-YY+1），1-7 月屬春季賽季（YYYY-1-YY）。
    NBA 例行賽 10 月開幕、翌年 4-6 月結束。"""
    from datetime import date
    today = date.today()
    if today.month >= 8:
        return f"{today.year}-{str(today.year + 1)[2:]}"
    return f"{today.year - 1}-{str(today.year)[2:]}"


def _prev_season(season):
    """'2026-27' → '2025-26'（供球季剛開打、本季數據尚未產生時的 fallback）"""
    try:
        start = int(season.split("-")[0])
    except (ValueError, IndexError, AttributeError):
        from datetime import date
        return f"{date.today().year - 1}-{str(date.today().year)[2:]}"
    return f"{start - 1}-{str(start)[2:]}"


class NBADataFetcher:
    def __init__(self, conn=None):
        """conn 參數保留（與 engine 呼叫簽名相容），但 basketball-reference
        來源不寫 DB，故忽略。"""
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })
        self.fetched_sources = []

    # ---- 隊名匹配 ----
    @staticmethod
    def _norm_team(name):
        return (name or "").replace("*", "").strip()

    def _match_team(self, local_name, stats_map):
        """DB 隊名 → basketball-reference 隊名。
        優先順序：精確 → 別名表 → 別名精確 → 逐 token 包含匹配（唯一命中才算）。"""
        ln = self._norm_team(local_name)
        if not ln:
            return None
        if ln in stats_map:
            return ln
        alias = BR_TEAM_ALIASES.get(ln)
        if alias and alias in stats_map:
            return alias
        for token in ln.split():
            if len(token) >= 3:
                hits = [k for k in stats_map if token.lower() in k.lower()]
                if len(hits) == 1:
                    return hits[0]
        return None

    def _fetch_advanced_stats(self, season=None):
        """抓 basketball-reference 全聯盟進階數據 → {隊名: stats_dict}

        🆕 [2026-10-09] 賽季 fallback：球季剛開打時，本季 advanced-team 表
        是「30 列空殼」（W-L 全 0、ORtg/DRtg 全空）。原碼照樣回傳 30 筆全零
        數據 → 引擎注入 42 個 "0.0" 到 LLM prompt，等於沒有任何鑑別資訊，
        LLM 只能倒向主場優勢瞎猜（實測：模型預測主場 56.5% vs 實際 43.5%）。
        修法：本季有效隊伍數 < 10 時，自動退回上一季數據，並以 is_prev_season
        標記，讓 prompt 能明確標示「此為上季數據」。
        """
        season = season or _current_season()
        stats_map = self._parse_season(season)

        # 有效隊伍 = 有實際出賽紀錄（W+L > 0）
        valid = sum(1 for v in stats_map.values() if v["wins"] + v["losses"] > 0)
        if valid < 10:
            prev = _prev_season(season)
            print(f"  ⚠ NBA BR：{season} 僅 {valid} 隊有數據（球季剛開打），改用 {prev}")
            prev_map = self._parse_season(prev)
            prev_valid = sum(1 for v in prev_map.values() if v["wins"] + v["losses"] > 0)
            if prev_valid >= 10:
                for v in prev_map.values():
                    v["is_prev_season"] = True
                    v["data_season"] = prev
                self.fetched_sources.append("basketball-reference.com")
                return prev_map
            print(f"  ⚠ NBA BR：上季 {prev} 也僅 {prev_valid} 隊有數據，放棄")
            return {}

        for v in stats_map.values():
            v["is_prev_season"] = False
            v["data_season"] = season
        self.fetched_sources.append("basketball-reference.com")
        return stats_map

    def _parse_season(self, season):
        """解析單一賽季的 advanced-team 表 → {隊名: stats_dict}（無資料時回傳 {}）"""
        url = _br_url(season)
        try:
            resp = self.session.get(url, timeout=25)
            resp.raise_for_status()
        except Exception as e:
            print(f"  ⚠ NBA basketball-reference error ({season}): {e}")
            return {}
        soup = BeautifulSoup(resp.text, "lxml")
        table = soup.find("table", id="advanced-team")
        if not table:
            print(f"  ⚠ NBA basketball-reference: advanced-team 表不存在（{season}）")
            return {}
        stats_map = {}
        for tr in table.find("tbody").find_all("tr"):
            cells = tr.find_all(["th", "td"])
            if len(cells) < 20:
                continue
            team = self._norm_team(cells[_ADV_COLS["team"]].get_text(strip=True))
            if not team or team.lower() == "league average":
                continue
            wins = _to_float(cells[_ADV_COLS["wins"]].get_text())
            losses = _to_float(cells[_ADV_COLS["losses"]].get_text())
            gp = wins + losses
            stats_map[team] = {
                "off_rtg": _to_float(cells[_ADV_COLS["off_rtg"]].get_text()),
                "def_rtg": _to_float(cells[_ADV_COLS["def_rtg"]].get_text()),
                "net_rating": _to_float(cells[_ADV_COLS["net_rating"]].get_text()),
                "pace": _to_float(cells[_ADV_COLS["pace"]].get_text()),
                "ts_pct": _to_float(cells[_ADV_COLS["ts_pct"]].get_text()),
                "efg_pct": _to_float(cells[_ADV_COLS["efg_pct"]].get_text()),
                "tov_pct": _to_float(cells[_ADV_COLS["tov_pct"]].get_text()),
                "orb_pct": _to_float(cells[_ADV_COLS["orb_pct"]].get_text()),
                "win_pct": wins / gp if gp > 0 else 0.0,
                "wins": int(wins),
                "losses": int(losses),
            }
        return stats_map

    def get_top_players(self, team_name, top_n=5):
        """主力球員數據：stats.nba.com 已失效，v2 不再抓取。
        engine 不消費 NBA top_players（只消費 team_stats），回傳空 list 安全。"""
        return []

    def fetch_and_store_game_data(self, game_id, home_team_name, away_team_name, season=None):
        """為一場 NBA 比賽取得進階數據（basketball-reference 全聯盟表）。
        season=None → 動態賽季；指定（如 '2025-26'）供測試/手動驗證。
        回傳結構與舊版相容：{'team_stats': {'home': {...}, 'away': {...}},
                             'top_players': {'home': [], 'away': []},
                             'sources': [...]}
        """
        all_stats = self._fetch_advanced_stats(season)
        if not all_stats:
            return None

        home_key = self._match_team(home_team_name, all_stats)
        away_key = self._match_team(away_team_name, all_stats)

        if not home_key or not away_key:
            print(f"  ⚠ Cannot match NBA teams: {home_team_name} / {away_team_name}")
            print(f"     Matched: home={home_key}, away={away_key}")
            return None

        return {
            "home_team_name": home_team_name,
            "away_team_name": away_team_name,
            "team_stats": {"home": all_stats[home_key], "away": all_stats[away_key]},
            "top_players": {"home": [], "away": []},
            "sources": list(set(self.fetched_sources)),
            # 🆕 [2026-10-09] 賽季標記（供 prompt 標示是否為上季數據）
            "is_prev_season": bool(all_stats[home_key].get("is_prev_season")),
            "data_season": all_stats[home_key].get("data_season"),
        }

    def close(self):
        """關閉 session。"""
        try:
            self.session.close()
        except Exception:
            pass
