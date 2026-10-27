#!/usr/bin/env python3
"""
ingest/cpbl.py
==============
CPBL fetcher — 從 TheSportsDB API (League ID 5111) 抓中華職棒賽事

TheSportsDB 免費版 API:
- Base: https://www.thesportsdb.com/api/v1/json
- API Key: 123 (免費版)
- Rate limit: 30 req/min

關鍵端點:
- eventsday.php?d=YYYY-MM-DD&l=5111 → 當日所有 CPBL 賽事
"""

import os
import re
import json
import logging
from typing import List, Dict, Any
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
import requests
from .base import BaseIngester

LOGGER = logging.getLogger("ingest.cpbl")

# TheSportsDB CPBL League ID
CPBL_LEAGUE_ID = "5111"
DEFAULT_THESPORTSDB_KEY = "123"  # 免費版 default
API_BASE = "https://www.thesportsdb.com/api/v1/json"

# CPBL 6 隊中英對照（TheSportsDB 英文隊名 → DB 統一隊名）
TEAM_NAME_MAP = {
    "Uni-President Lions": "Uni-President 7-ELEVEn Lions",
    "CTBC Brothers": "CTBC Brothers",
    "Fubon Guardians": "Fubon Guardians",
    "Rakuten Monkeys": "Rakuten Monkeys",
    "Wei Chuan Dragons": "Wei Chuan Dragons",
    "TSG Hawks": "TSG Hawks",
}


def _normalize_team_name(english_name: str) -> str:
    """TheSportsDB 英文隊名 → DB 統一隊名"""
    return TEAM_NAME_MAP.get(english_name, english_name)


# 🆕 [2026-10-27 P1] 官方賽程中文隊名 → DB 統一隊名
OFFICIAL_TEAM_MAP = {
    "中信兄弟": "CTBC Brothers",
    "味全龍": "Wei Chuan Dragons",
    "統一7-ELEVEn獅": "Uni-President 7-ELEVEn Lions",
    "統一7-11獅": "Uni-President 7-ELEVEn Lions",
    "統一獅": "Uni-President 7-ELEVEn Lions",
    "樂天桃猿": "Rakuten Monkeys",
    "富邦悍將": "Fubon Guardians",
    "台鋼雄鷹": "TSG Hawks",
}

OFFICIAL_SCHEDULE_URL = "https://www.cpbl.com.tw/schedule"
OFFICIAL_GAMEDATA_URL = "https://www.cpbl.com.tw/schedule/getgamedatas"
PLACEHOLDER_PITCHERS = {"", "尚未公布", "未定", "TBD", "tbd", "-", "--", "---"}


class CPBLIngester(BaseIngester):
    league_code = "CPBL"
    league_days_ahead = 1  # CPBL 先發投手通常在開打前 1.5 天發布（PTT wewe0403 預告）；
                            # 抓今天 + 明天（day+0, day+1）即可，day+2 的 SP 還未公布。
    source_name = "cpbl_official+thesportsdb_fallback"

    def __init__(self):
        super().__init__()
        self.api_key = os.getenv("THESPORTSDB_API_KEY", DEFAULT_THESPORTSDB_KEY)
        self.api_base = API_BASE
        # TheSportsDB 用專用 session（不需要台灣網站的 cookie）
        self.tdb_session = requests.Session()
        self.tdb_session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "application/json",
        })
        # 🆕 [2026-10-27 P1] CPBL 官方賽程 session（TheSportsDB 季後賽覆蓋不全）
        self.official_session = requests.Session()
        self.official_session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120 Safari/537.36",
            "Accept-Language": "zh-TW",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": OFFICIAL_SCHEDULE_URL,
        })
        self._official_tokens: Dict[str, Any] = {}

    def _api_get(self, endpoint: str, params: Dict[str, Any] = None) -> Dict:
        """呼叫 TheSportsDB API"""
        url = f"{self.api_base}/{self.api_key}/{endpoint}"
        try:
            resp = self.tdb_session.get(url, params=params, timeout=20)
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 429:
                LOGGER.warning("TheSportsDB rate limit hit (429). 等待 60 秒...")
                import time
                time.sleep(60)
                resp = self.tdb_session.get(url, params=params, timeout=20)
                if resp.status_code == 200:
                    return resp.json()
            LOGGER.error(f"TheSportsDB API {endpoint}: HTTP {resp.status_code}")
            return {}
        except Exception as e:
            LOGGER.error(f"TheSportsDB API {endpoint} 失敗: {e}")
            return {}

    # ------------------------------------------------------------------
    # 🆕 [2026-10-27 P1] 官方賽程（主來源）
    # ------------------------------------------------------------------
    def _get_official_token(self, year: int, month: int) -> str:
        """取得 cpbl.com.tw getgamedatas 的 RequestVerificationToken（快取 30 分鐘）"""
        import time
        key = f"{year}-{month:02d}"
        ent = self._official_tokens.get(key)
        if ent and time.time() - ent[0] < 1800:
            return ent[1]
        resp = self.official_session.get(
            OFFICIAL_SCHEDULE_URL, params={"year": year, "month": month}, timeout=20
        )
        if resp.status_code != 200:
            raise RuntimeError(f"CPBL 官方賽程頁 HTTP {resp.status_code}")
        m = re.search(r"getgamedatas.*?RequestVerificationToken:\s*'([^']+)'", resp.text, re.S)
        if not m:
            raise RuntimeError("CPBL 官方賽程頁找不到 RequestVerificationToken")
        self._official_tokens[key] = (time.time(), m.group(1))
        return m.group(1)

    def _fetch_official_month(self, year: int, month: int) -> List[Dict[str, Any]]:
        """抓取官方整月賽程（GameDatas）"""
        token = self._get_official_token(year, month)
        resp = self.official_session.post(
            OFFICIAL_GAMEDATA_URL,
            data={"calendar": f"{year}/{month:02d}/01", "location": "", "kindCode": "", "teamNo": ""},
            headers={"RequestVerificationToken": token},
            timeout=30,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"CPBL getgamedatas HTTP {resp.status_code}")
        payload = resp.json()
        return json.loads(payload.get("GameDatas") or "[]")

    def _fetch_games_official(self, target_date: str) -> List[Dict[str, Any]]:
        """
        官方賽程 → 標準 games 格式
        - PresentStatus 0 = 延賽
        - 未來日期一律 SCHEDULED 且清空比分
        - 今日：開打後 3 小時視為 FINAL（避免 0-0 未開打誤判）
        """
        from datetime import datetime as _dt, date as _date
        from zoneinfo import ZoneInfo
        dt = _dt.strptime(target_date, "%Y-%m-%d")
        today = _dt.now(ZoneInfo("Asia/Taipei")).date()
        raw = self._fetch_official_month(dt.year, dt.month)
        games: List[Dict[str, Any]] = []
        for g in raw:
            if str(g.get("GameDate") or "")[:10] != target_date:
                continue
            home = OFFICIAL_TEAM_MAP.get((g.get("HomeTeamName") or "").strip())
            away = OFFICIAL_TEAM_MAP.get((g.get("VisitingTeamName") or "").strip())
            if not home or not away:
                LOGGER.debug(f"CPBL 官方跳過未知隊名: {g.get('HomeTeamName')} vs {g.get('VisitingTeamName')}")
                continue
            try:
                hs = int(g.get("HomeScore")) if g.get("HomeScore") is not None else None
                as_ = int(g.get("VisitingScore")) if g.get("VisitingScore") is not None else None
            except (TypeError, ValueError):
                hs = as_ = None
            try:
                status_code = int(g.get("PresentStatus") or 0)
            except (TypeError, ValueError):
                status_code = 0
            start = None
            try:
                start = _dt.fromisoformat(str(g.get("GameDateTimeS"))[:19]).replace(tzinfo=ZoneInfo("Asia/Taipei"))
            except Exception:
                pass

            if status_code == 0:
                status = "POSTPONED"
                hs = as_ = None
            elif dt.date() > today:
                status = "SCHEDULED"
                hs = as_ = None
            elif dt.date() < today:
                status = "FINAL" if (hs is not None and as_ is not None) else "SCHEDULED"
            else:
                now = _dt.now(ZoneInfo("Asia/Taipei"))
                if start and now < start:
                    status = "SCHEDULED"
                    hs = as_ = None
                elif start and now < start + timedelta(hours=3):
                    status = "LIVE"
                elif hs is not None and as_ is not None:
                    status = "FINAL"
                else:
                    status = "LIVE"

            game = {
                "season": int(g.get("Year") or dt.year),
                "match_date": target_date,
                "home_team": home,
                "away_team": away,
                "status": status,
                "home_team_score": hs,
                "away_team_score": as_,
            }
            hp = (g.get("HomePitcherName") or "").strip()
            ap = (g.get("VisitingPitcherName") or "").strip()
            if hp and hp not in PLACEHOLDER_PITCHERS:
                game["home_pitcher"] = hp
            if ap and ap not in PLACEHOLDER_PITCHERS:
                game["away_pitcher"] = ap
            games.append(game)
        return games

    def fetch_games(self, target_date: str) -> List[Dict[str, Any]]:
        """
        抓取指定日期（YYYY-MM-DD）的 CPBL 賽事
        主來源：cpbl.com.tw 官方 getgamedatas（含季後賽、延賽狀態、先發投手）
        備援：TheSportsDB（免費源季後賽覆蓋不全，2026-10-24~26 實測 0 場）
        """
        try:
            games = self._fetch_games_official(target_date)
            if games:
                LOGGER.info(f"CPBL 官方 {target_date} → {len(games)} 場")
                return games
            LOGGER.info(f"CPBL 官方 {target_date} → 0 場（休兵或尚無賽程），以 TheSportsDB 交叉確認")
        except Exception as e:
            LOGGER.warning(f"CPBL 官方來源失敗（{target_date}）: {e} → 改用 TheSportsDB")
        return self._fetch_games_thesportsdb(target_date)

    def _fetch_games_thesportsdb(self, target_date: str) -> List[Dict[str, Any]]:
        """
        抓取指定日期（YYYY-MM-DD）的 CPBL 賽事
        使用 TheSportsDB eventsday.php 端點
        """
        LOGGER.info(f"CPBL TheSportsDB: 抓取 {target_date} 賽事 (league_id={CPBL_LEAGUE_ID})")
        try:
            data = self._api_get(
                "eventsday.php",
                params={"d": target_date, "l": CPBL_LEAGUE_ID},
            )
        except Exception as e:
            raise RuntimeError(f"CPBL API 連線失敗: {e}")

        # 🆕 [2026-07-28] 增加請求間隔以遵守 TheSportsDB 30 req/min 限制
        # 30 req/min = 2 秒/req，這裡每次 fetch 後 sleep 2.0 秒作為緩衝
        # base.py 的 run() 會呼叫多次 fetch_games（每次 1 日期），此時無需額外間隔
        import time as _time
        _time.sleep(2.0)

        events = data.get("events", []) or []
        LOGGER.info(f"CPBL {target_date} API 回傳 {len(events)} 場賽事")

        if not events:
            return []

        games: List[Dict[str, Any]] = []
        for e in events:
            home_raw = e.get("strHomeTeam", "")
            away_raw = e.get("strAwayTeam", "")
            home = _normalize_team_name(home_raw)
            away = _normalize_team_name(away_raw)

            # 跳過不認識的隊伍（非 CPBL 賽事）
            if home not in TEAM_NAME_MAP.values() or away not in TEAM_NAME_MAP.values():
                LOGGER.debug(f"CPBL 跳過非中職賽事: {home_raw} vs {away_raw}")
                continue

            # 分數
            home_score_raw = e.get("intHomeScore")
            away_score_raw = e.get("intAwayScore")
            home_score = int(home_score_raw) if (home_score_raw is not None and str(home_score_raw).lstrip('-').isdigit()) else None
            away_score = int(away_score_raw) if (away_score_raw is not None and str(away_score_raw).lstrip('-').isdigit()) else None

            # 狀態: TheSportsDB 用 strStatus (FT=Finished, IN*=In Progress, NS=Not Started)
            # ⚠️ strPostponed 標記不可靠（2026-06-23 實證：CPBL 3 場標 postponed 但官網照打）
            # 修法：strPostponed=yes 僅在 strStatus 非 FT/IN 時才視為 POSTPONED
            status_raw = (e.get("strStatus") or "").upper()
            postponed = (e.get("strPostponed") or "no").lower() == "yes"

            # 日期
            date_event = e.get("dateEvent") or target_date

            # 🛡 未來日期防護（2026-06-27 實證：TheSportsDB 給 FT+0-0 但比賽在明天）
            # 解法：未來日期的比賽即使 TheSportsDB 標 FT 也不寫入 FINAL + 清掉比分
            date_is_future = False
            try:
                event_date = datetime.strptime(date_event, "%Y-%m-%d").date()
                today_taipei = datetime.now(ZoneInfo("Asia/Taipei")).date()
                date_is_future = event_date > today_taipei
            except (ValueError, TypeError):
                pass

            if postponed and status_raw not in ("FT", "IN", "IN_PROGRESS", "INPLAY"):
                status = "POSTPONED"
            elif status_raw == "FT" and home_score is not None and away_score is not None and not date_is_future:
                status = "FINAL"
            elif status_raw.startswith("IN"):
                status = "LIVE"
            else:
                status = "SCHEDULED"

            # 未來日期的比賽，比分也不應寫入
            if date_is_future:
                home_score = None
                away_score = None

            games.append({
                "season": datetime.now().year,
                "match_date": date_event,
                "home_team": home,
                "away_team": away,
                "status": status,
                "home_team_score": home_score,
                "away_team_score": away_score,
            })

        # 🆕 補先發投手（從 cpbl.com.tw API）
        self._enrich_pitchers(games, target_date)

        # 🆕 [2026-09-29] 補賽識別：TheSportsDB 對「補賽」保留 strPostponed=yes（殘留標記），
        # 導致補賽被誤標 POSTPONED、分析跳過（實證 9/30 補賽週 3 場官方照打卻被跳過）。
        # 區分信號：補賽會公布先發投手（PTT 預告），真延賽（颱風等）不會有先發預告。
        # 修法：已補到先發投手（非佔位符）的 POSTPONED 場次，改回 SCHEDULED。
        for g in games:
            if g.get('status') == 'POSTPONED':
                hp = g.get('home_pitcher')
                ap = g.get('away_pitcher')
                has_sp = bool(hp) or bool(ap)
                if has_sp:
                    g['status'] = 'SCHEDULED'
                    LOGGER.info(
                        f"CPBL 補賽識別: {g.get('home_team')} vs {g.get('away_team')} "
                        f"已公布先發投手，改標 SCHEDULED"
                    )

        return games

    def _enrich_pitchers(self, games: List[Dict[str, Any]], target_date: str):
        """從 cpbl.com.tw API 取得當日先發投手並補入 games"""
        try:
            from cpbl_data_fetcher import CPBLDataFetcher
            fetcher = CPBLDataFetcher()
            # target_date 是 "YYYY-MM-DD"，需轉為 "YYYY/MM/DD"
            date_str = target_date.replace('-', '/')
            starters = fetcher.get_today_starting_pitchers(date_str)

            # 🆕 [2026-08-26] 過濾佔位字串，避免 "TBD"/"尚未公布" 覆寫已正確的投手資料
            # 與 api_server._clean_pitcher_name 對齊
            PLACEHOLDERS = {'', '尚未公布', '未定', 'TBD', 'tbd', '-', '--', '---'}

            def _is_placeholder(value):
                if value is None:
                    return True
                if isinstance(value, dict):
                    name = value.get('name')
                    return not name or str(name).strip() in PLACEHOLDERS
                return str(value).strip() in PLACEHOLDERS

            if starters:
                enriched = 0
                for g in games:
                    home = g.get('home_team')
                    away = g.get('away_team')
                    if home in starters and not _is_placeholder(starters[home]):
                        g['home_pitcher'] = starters[home]
                        enriched += 1
                    if away in starters and not _is_placeholder(starters[away]):
                        g['away_pitcher'] = starters[away]
                LOGGER.info(f"CPBL {target_date} 補入先發投手: {enriched} 筆")
            else:
                LOGGER.info(f"CPBL {target_date} 無先發投手資料（可能尚未公布）")
        except Exception as e:
            LOGGER.warning(f"CPBL pitcher enrichment failed: {e}")
