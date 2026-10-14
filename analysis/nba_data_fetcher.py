"""
PredictX Sports — NBA DataFetcher
數據來源（2026-10-01 換源）：basketball-reference.com
- stats.nba.com（nba_api 後端）已失效：本機 + Railway 容器皆 timeout/500
- www.nba.com/stats 頁面 200 但統計表是 client-side 渲染，純 HTTP 爬不到
- basketball-reference.com 本機 + Railway 容器皆 200，advanced-team 表含
  ORtg/DRtg/NRtg/Pace/TS%/eFG%/TOV% 等 engine 消費欄位
"""
import re
import time
import threading

import requests
from bs4 import BeautifulSoup

# ======================================================================
# 🆕 [2026-10-12] 模組級賽季快取 —— 修「批次分析把 BR 打到限流/封鎖」的根因
#
# 問題實證：
#   1. analysis_engine.get_game_features() 每場都 new 一個 NBADataFetcher()，
#      且 _fetch_advanced_stats() 每次都對 BR 發 2 次請求（本季 + 上季 fallback）
#      → 66 場批次 = 132 次請求。
#   2. 實測 10-09 的三個批次成功率 100%，10-11 02 時起崩到 17% → 之後全 0%
#      （NBA 近 21 天 10/10 之後 0/29 場取得進階數據）。
#   3. 對照組：WNBA（ESPN 來源）同期 100% 成功、MLB（statsapi）100% 成功
#      → Railway 對外網路正常，唯獨 basketball-reference 取不到。
#   4. 本機 BR 連續 12 次請求全部 200 → 非全域封鎖，是 BR 對
#      資料中心 IP／高頻請求的阻擋。
#
# 修法：同一個 process 內，同一賽季只抓一次（6 小時 TTL），
#       132 次請求 → 2 次，徹底避開限流路徑。
# ======================================================================
_SEASON_CACHE = {}              # season -> (timestamp, stats_map)
_SEASON_CACHE_TTL = 6 * 3600    # 6 小時
_SEASON_CACHE_LOCK = threading.Lock()

# 供診斷端點讀取的統計
FETCH_STATS = {
    "cache_hit": 0,
    "cache_miss": 0,
    "br_ok": 0,
    "br_fail": 0,
    "last_br_status": None,     # HTTP 狀態碼（或例外字串）
    "last_error": None,
}


def _cache_get(season):
    """回傳快取中的賽季資料（過期回 None）"""
    ent = _SEASON_CACHE.get(season)
    if not ent:
        return None
    ts, data = ent
    if time.time() - ts > _SEASON_CACHE_TTL:
        return None
    return data


def _cache_put(season, data):
    with _SEASON_CACHE_LOCK:
        _SEASON_CACHE[season] = (time.time(), data)


def clear_season_cache():
    """清空快取（手動驗證 / 測試用）"""
    with _SEASON_CACHE_LOCK:
        _SEASON_CACHE.clear()


# ======================================================================
# 🆕 [2026-10-12] ESPN 備援來源（BR 被 Railway egress 阻擋時的後路）
#
# 背景：BR 對資料中心 IP 阻擋，NBA 進階數據自 10/10 起 0/29 全滅；
#       對照組 WNBA（ESPN 來源）100%、MLB（statsapi）100% → ESPN 可達。
# 做法：basketball-reference → ESPN 兩段式
#   ① 1 次 standings?season=<結束年> → 30 隊完整 W-L / 場均得分失分
#   ② 每隊 1 次 teams/{id}/statistics?season=<結束年> → 投籃/籃板/失誤
#   再以標準公式推導 OffRtg / DefRtg / NetRtg / Pace / TS% / eFG% / TOV%
# 快取：與 BR 同一套 6h TTL，整批最多 1 + 30 次請求（且為 API 非爬蟲，不易被封）
# ======================================================================
ESPN_STANDINGS_URL = "https://site.web.api.espn.com/apis/v2/sports/basketball/nba/standings"
ESPN_TEAMS_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams"
ESPN_TEAM_STATS_URL = ("https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
                       "/teams/{tid}/statistics")

# DB 隊名 → ESPN 顯示名（多數相同，僅少數縮寫差異）
ESPN_TEAM_ALIASES = {
    "Los Angeles Clippers": "LA Clippers",
    "Los Angeles Lakers": "Los Angeles Lakers",
    "Portland Trail Blazers": "Portland Trail Blazers",
}

_ESPN_CACHE = {}
_ESPN_TTL = 6 * 3600


def _espn_cache_get(key):
    ent = _ESPN_CACHE.get(key)
    if not ent:
        return None
    ts, data = ent
    if time.time() - ts > _ESPN_TTL:
        return None
    return data


def _espn_cache_put(key, data):
    with _SEASON_CACHE_LOCK:
        _ESPN_CACHE[key] = (time.time(), data)


def _espn_win_year(season):
    """'2025-26' → 2026（ESPN 的 season 參數用結束年）"""
    try:
        return int(season.split("-")[0]) + 1
    except (ValueError, IndexError, AttributeError):
        from datetime import date
        return date.today().year

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

    def _parse_season(self, season, _retries=3):
        """解析單一賽季的 advanced-team 表 → {隊名: stats_dict}（無資料時回傳 {}）

        🆕 [2026-10-12] 兩層強化（修 BR 限流/封鎖導致進階數據全滅）：
          ① 模組級快取（6h TTL）：同批次 132 次請求 → 2 次
          ② 指數退避重試（2s / 6s）：對抗 transient 限流
        失敗時回 {} 且**不快取**，避免把一次性失敗鎖住 6 小時。
        """
        # ---- ① 快取 ----
        cached = _cache_get(season)
        if cached is not None:
            FETCH_STATS["cache_hit"] += 1
            return cached
        FETCH_STATS["cache_miss"] += 1

        url = _br_url(season)
        resp = None
        last_err = None
        for attempt in range(1, _retries + 1):
            try:
                resp = self.session.get(url, timeout=25)
                FETCH_STATS["last_br_status"] = resp.status_code
                resp.raise_for_status()
                last_err = None
                break
            except Exception as e:
                last_err = e
                FETCH_STATS["last_error"] = f"{season} attempt{attempt}: {type(e).__name__}: {str(e)[:160]}"
                print(f"  ⚠ NBA BR 失敗（{season}, 第 {attempt}/{_retries} 次）: {e}")
                if attempt < _retries:
                    time.sleep(2 * (3 ** (attempt - 1)))   # 2s → 6s
        if last_err is not None or resp is None:
            FETCH_STATS["br_fail"] += 1
            print(f"  ⚠ NBA BR 放棄（{season}）：重試 {_retries} 次皆失敗")
            return {}

        soup = BeautifulSoup(resp.text, "lxml")
        table = soup.find("table", id="advanced-team")
        if not table:
            print(f"  ⚠ NBA basketball-reference: advanced-team 表不存在（{season}）")
            FETCH_STATS["br_fail"] += 1
            return {}
        stats_map = {}
        for tr in table.find("tbody").find_all("tr"):
            cells = tr.find_all(["th", "td"])
            if len(cells) < 20:
                continue
            # 🆕 [2026-10-12] 改用 data-stat 取值（原本用固定 index）：
            # BR 表在 ts_pct 與 efg_pct 之間插了 DUMMY 空欄，導致整段位移 ——
            # 實測 efg_pct 讀到空欄（prompt 長期顯示 EFG%: 0.000）、
            # tov_pct 讀到 efg_pct、orb_pct 讀到 tov_pct。
            # data-stat 是 BR 的穩定語意標籤，不受欄位增減影響。
            by = {}
            for c in cells:
                ds = c.get("data-stat")
                if ds and ds not in by:
                    by[ds] = c.get_text(strip=True)
            team = self._norm_team(by.get("team", ""))
            if not team or team.lower() == "league average":
                continue
            wins = _to_float(by.get("wins"))
            losses = _to_float(by.get("losses"))
            gp = wins + losses
            stats_map[team] = {
                "off_rtg": _to_float(by.get("off_rtg")),
                "def_rtg": _to_float(by.get("def_rtg")),
                "net_rating": _to_float(by.get("net_rtg")),
                "pace": _to_float(by.get("pace")),
                "ts_pct": _to_float(by.get("ts_pct")),
                "efg_pct": _to_float(by.get("efg_pct")),
                "tov_pct": _to_float(by.get("tov_pct")),
                "orb_pct": _to_float(by.get("orb_pct")),
                "win_pct": wins / gp if gp > 0 else 0.0,
                "wins": int(wins),
                "losses": int(losses),
            }
        # ② 只在真的解析出資料時才快取
        if stats_map:
            _cache_put(season, stats_map)
            FETCH_STATS["br_ok"] += 1
        else:
            FETCH_STATS["br_fail"] += 1
        return stats_map

    def get_top_players(self, team_name, top_n=5):
        """主力球員數據：stats.nba.com 已失效，v2 不再抓取。
        engine 不消費 NBA top_players（只消費 team_stats），回傳空 list 安全。"""
        return []

    # ---- ESPN 備援 ----
    def _espn_match(self, local_name, name_map):
        """DB 隊名 → ESPN 顯示名（精確 → 別名 → token 唯一命中）"""
        ln = self._norm_team(local_name)
        if not ln:
            return None
        if ln in name_map:
            return ln
        alias = ESPN_TEAM_ALIASES.get(ln)
        if alias and alias in name_map:
            return alias
        for token in ln.split():
            if len(token) >= 3:
                hits = [k for k in name_map if token.lower() in k.lower()]
                if len(hits) == 1:
                    return hits[0]
        return None

    def _espn_team_id_map(self):
        cached = _espn_cache_get("teams")
        if cached is not None:
            return cached
        try:
            r = self.session.get(ESPN_TEAMS_URL, timeout=25)
            r.raise_for_status()
            d = r.json()
            m = {t["team"]["displayName"]: t["team"]["id"]
                 for t in d["sports"][0]["leagues"][0]["teams"]}
            _espn_cache_put("teams", m)
            return m
        except Exception as e:
            print(f"  ⚠ ESPN teams 取得失敗: {e}")
            return {}

    def _espn_standings(self, year):
        key = f"standings:{year}"
        cached = _espn_cache_get(key)
        if cached is not None:
            return cached
        out = {}

        def _f(v):
            try:
                return float(str(v).replace("%", "")) if v not in (None, "", "-") else 0.0
            except (ValueError, TypeError):
                return 0.0

        try:
            r = self.session.get(ESPN_STANDINGS_URL, params={"season": year}, timeout=25)
            r.raise_for_status()
            d = r.json()
            for conf in d.get("children", []):
                for ent in (conf.get("standings") or {}).get("entries", []):
                    nm = ent["team"]["displayName"]
                    st = {s.get("name"): s.get("displayValue") for s in ent.get("stats", [])}
                    wins = int(_f(st.get("wins")))
                    losses = int(_f(st.get("losses")))
                    gp = wins + losses
                    out[nm] = {
                        "wins": wins, "losses": losses,
                        "win_pct": round(wins / gp, 3) if gp > 0 else 0.0,
                        "pf": _f(st.get("avgPointsFor")),
                        "pa": _f(st.get("avgPointsAgainst")),
                    }
            if out:
                _espn_cache_put(key, out)
        except Exception as e:
            print(f"  ⚠ ESPN standings 取得失敗: {e}")
        return out

    def _espn_team_rates(self, tid, year):
        key = f"team:{tid}:{year}"
        cached = _espn_cache_get(key)
        if cached is not None:
            return cached
        try:
            r = self.session.get(ESPN_TEAM_STATS_URL.format(tid=tid),
                                 params={"season": year}, timeout=25)
            r.raise_for_status()
            cats = (r.json().get("results") or {}).get("stats", {}).get("categories", [])
            s = {}
            for c in cats:
                for item in c.get("stats", []):
                    try:
                        s[item["name"]] = float(item.get("value"))
                    except (TypeError, ValueError):
                        pass
            fga = s.get("avgFieldGoalsAttempted", 0.0)
            fgm = s.get("avgFieldGoalsMade", 0.0)
            tpm = s.get("avgThreePointFieldGoalsMade", 0.0)
            fta = s.get("avgFreeThrowsAttempted", 0.0)
            oreb = s.get("avgOffensiveRebounds", 0.0)
            dreb = s.get("avgDefensiveRebounds", 0.0)
            tov = s.get("avgTurnovers", 0.0)
            pts = s.get("avgPoints", 0.0)
            if fga <= 0:
                return {}
            poss = fga + 0.44 * fta - oreb + tov
            if poss <= 0:
                return {}
            rates = {
                "pace": round(poss, 1),
                "efg_pct": round((fgm + 0.5 * tpm) / fga, 3),
                "ts_pct": round(pts / (2 * (fga + 0.44 * fta)), 3) if (fga + 0.44 * fta) > 0 else 0.0,
                "tov_pct": round(tov / (fga + 0.44 * fta + tov), 3) if (fga + 0.44 * fta + tov) > 0 else 0.0,
                "orb_pct": round(oreb / (oreb + dreb), 3) if (oreb + dreb) > 0 else 0.0,
                "_pts": pts,
            }
            _espn_cache_put(key, rates)
            return rates
        except Exception as e:
            print(f"  ⚠ ESPN team {tid} 取得失敗: {e}")
            return {}

    def _fetch_from_espn(self, home_name, away_name, season):
        """ESPN 備援：組出與 BR 相同結構的 team_stats。失敗回 None。

        賽季處理：先用「本季結束年」；若 ESPN 尚無（如 2027 未開打）→ 退回上一季。
        """
        ids = self._espn_team_id_map()
        if not ids:
            return None
        hk = self._espn_match(home_name, ids)
        ak = self._espn_match(away_name, ids)
        if not hk or not ak:
            print(f"  ⚠ ESPN 隊名無法匹配: {home_name}(→{hk}) / {away_name}(→{ak})")
            return None

        # 賽季選擇（與 BR 的「本季有效隊伍 < 10 → 退回上季」邏輯一致）：
        # ESPN 對「尚未開打」的球季仍會回 standings（但只有季前賽的 0-4 場），
        # 直接拿來算會得到無意義的指標；且 team statistics 端點對未開打球季回 404。
        # 故：本季累積場次 < 30 → 改用上一季。
        def _mature(y):
            st = self._espn_standings(y)
            if not st:
                return False, None
            mx = max((v["wins"] + v["losses"]) for v in st.values())
            return mx >= 30, st

        year = _espn_win_year(season)
        ok, std = _mature(year)
        data_season = season
        if not ok:
            prev = _prev_season(season)
            year = _espn_win_year(prev)
            ok2, std2 = _mature(year)
            if ok2:
                std, data_season = std2, prev
                print(f"  ℹ️ ESPN：本季樣本不足 → 改用 {prev}（ESPN season={year}）")
            elif std:
                data_season = season
            else:
                std = std2
        if not std:
            print("  ⚠ ESPN standings 無資料（本季與上季皆空）")
            return None

        out = {}
        for local_nm, espn_nm in ((home_name, hk), (away_name, ak)):
            rates = self._espn_team_rates(ids[espn_nm], year)
            if not rates:
                return None
            rec = std.get(espn_nm, {})
            pts = rates.pop("_pts", 0.0)
            pace = rates["pace"]
            off = pts / pace * 100 if pace else 0.0
            dfn = rec.get("pa", 0.0) / pace * 100 if pace else 0.0
            out[local_nm] = {
                "off_rtg": round(off, 1),
                "def_rtg": round(dfn, 1),
                "net_rating": round(off - dfn, 1),
                "pace": pace,
                "ts_pct": rates["ts_pct"],
                "efg_pct": rates["efg_pct"],
                "tov_pct": rates["tov_pct"],
                "orb_pct": rates["orb_pct"],
                "win_pct": rec.get("win_pct", 0.0),
                "wins": rec.get("wins", 0),
                "losses": rec.get("losses", 0),
            }
        return out, data_season

    def fetch_and_store_game_data(self, game_id, home_team_name, away_team_name, season=None):
        """為一場 NBA 比賽取得進階數據（全聯盟表）。

        來源鏈（2026-10-12 起）：basketball-reference → ESPN 備援
        season=None → 動態賽季；指定（如 '2025-26'）供測試/手動驗證。
        回傳結構與舊版相容：{'team_stats': {'home': {...}, 'away': {...}},
                             'top_players': {'home': [], 'away': []},
                             'sources': [...]}
        兩來源皆失敗時回 None（呼叫端會據此標記 features 缺資料）。
        """
        season = season or _current_season()

        # ---- 主來源：basketball-reference ----
        all_stats = self._fetch_advanced_stats(season)
        home_key = self._match_team(home_team_name, all_stats) if all_stats else None
        away_key = self._match_team(away_team_name, all_stats) if all_stats else None

        if all_stats and home_key and away_key:
            return {
                "home_team_name": home_team_name,
                "away_team_name": away_team_name,
                "team_stats": {"home": all_stats[home_key], "away": all_stats[away_key]},
                "top_players": {"home": [], "away": []},
                "sources": list(set(self.fetched_sources)),
                # 🆕 [2026-10-09] 賽季標記（供 prompt 標示是否為上季數據）
                "is_prev_season": bool(all_stats[home_key].get("is_prev_season")),
                "data_season": all_stats[home_key].get("data_season"),
                "source_kind": "basketball-reference",
            }

        # BR 失敗的兩種情形都要明確記錄（隊名匹配失敗 or 整表取不到）
        if not all_stats:
            print("  ⚠ NBA BR 無資料（被阻擋或解析失敗）→ 嘗試 ESPN 備援")
        else:
            print(f"  ⚠ Cannot match NBA teams: {home_team_name}(→{home_key}) / "
                  f"{away_team_name}(→{away_key}) → 嘗試 ESPN 備援")

        # ---- 備援：ESPN ----
        espn = self._fetch_from_espn(home_team_name, away_team_name, season)
        if espn:
            stats, data_season = espn
            self.fetched_sources.append("espn.com")
            print(f"  📡 NBA ESPN 備援成功（{data_season} 資料）")
            return {
                "home_team_name": home_team_name,
                "away_team_name": away_team_name,
                "team_stats": {"home": stats[home_team_name], "away": stats[away_team_name]},
                "top_players": {"home": [], "away": []},
                "sources": list(set(self.fetched_sources)),
                "is_prev_season": True,
                "data_season": f"{data_season}（ESPN 衍生指標）",
                "source_kind": "espn_derived",
            }

        print("  ⚠ NBA BR 與 ESPN 皆失敗 → 本次不注入進階數據（已記錄於 features）")
        return None

    def close(self):
        """關閉 session。"""
        try:
            self.session.close()
        except Exception:
            pass
