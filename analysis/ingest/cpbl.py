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
import json
import logging
from typing import List, Dict, Any
from datetime import datetime, date
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


class CPBLIngester(BaseIngester):
    league_code = "CPBL"
    league_days_ahead = 2
    source_name = "thesportsdb_api"

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

    def fetch_games(self, target_date: str) -> List[Dict[str, Any]]:
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

        # 🆕 [2026-06-28] 跨日期退避（防止 TheSportsDB 限流 30 req/min）
        # 30 req/min = 2 秒/req，這裡每次 fetch 後 sleep 0.5 秒作為緩衝
        # base.py 的 run() 會呼叫多次 fetch_games（每次 1 日期），配合 INTER_LEAGUE_DELAY 雙重保險
        import time as _time
        _time.sleep(0.5)

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

        return games

    def _enrich_pitchers(self, games: List[Dict[str, Any]], target_date: str):
        """從 cpbl.com.tw API 取得當日先發投手並補入 games"""
        try:
            from cpbl_data_fetcher import CPBLDataFetcher
            fetcher = CPBLDataFetcher()
            # target_date 是 "YYYY-MM-DD"，需轉為 "YYYY/MM/DD"
            date_str = target_date.replace('-', '/')
            starters = fetcher.get_today_starting_pitchers(date_str)
            if starters:
                enriched = 0
                for g in games:
                    home = g.get('home_team')
                    away = g.get('away_team')
                    if home in starters:
                        g['home_pitcher'] = starters[home]
                        enriched += 1
                    if away in starters:
                        g['away_pitcher'] = starters[away]
                LOGGER.info(f"CPBL {target_date} 補入先發投手: {enriched} 筆")
            else:
                LOGGER.info(f"CPBL {target_date} 無先發投手資料（可能尚未公布）")
        except Exception as e:
            LOGGER.warning(f"CPBL pitcher enrichment failed: {e}")
