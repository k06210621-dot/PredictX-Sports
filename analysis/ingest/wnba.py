#!/usr/bin/env python3
"""
ingest/wnba.py
==============
WNBA fetcher — 從 ESPN 公開 scoreboard API 抓賽程
完全仿 NBA fetcher 結構（league_code = "WNBA"，ESPN path = "basketball/wnba"）

🆕 2026-07-03：僅用於資料收集驗證階段，未註冊到 cron，不會自動執行
"""

import logging
from typing import List, Dict, Any
from datetime import datetime
from .base import BaseIngester

LOGGER = logging.getLogger("ingest.wnba")

# ESPN WNBA public scoreboard endpoint（無需 API key）
ESPN_WNBA_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/scoreboard"


class WNBAIngester(BaseIngester):
    league_code = "WNBA"
    league_days_ahead = 2
    source_name = "espn_wnba"

    def fetch_games(self, target_date: str) -> List[Dict[str, Any]]:
        """ESPN scoreboard 用 YYYYMMDD 格式"""
        dt = datetime.strptime(target_date, "%Y-%m-%d")
        date_param = dt.strftime("%Y%m%d")
        url = f"{ESPN_WNBA_SCOREBOARD}?dates={date_param}"
        resp = self.session.get(url, timeout=20)
        if resp.status_code != 200:
            raise RuntimeError(f"ESPN WNBA HTTP {resp.status_code}")

        data = resp.json()
        games: List[Dict[str, Any]] = []
        for event in data.get("events", []):
            competitors = event.get("competitions", [{}])[0].get("competitors", [])
            home = away = None
            for c in competitors:
                team_name = c.get("team", {}).get("displayName") or c.get("team", {}).get("name")
                if c.get("homeAway") == "home":
                    home = team_name
                else:
                    away = team_name
            if not home or not away:
                continue
            status = event.get("status", {}).get("type", {}).get("name", "STATUS_SCHEDULED")
            if "FINAL" in status.upper():
                mapped = "FINAL"
            elif "IN_PROGRESS" in status.upper() or "LIVE" in status.upper():
                mapped = "LIVE"
            else:
                mapped = "SCHEDULED"

            # 抓比分（ESPN 在 competitors[].score）
            home_score = None
            away_score = None
            for c in competitors:
                score_str = c.get("score")
                if score_str is not None:
                    try:
                        score_val = int(score_str)
                        if c.get("homeAway") == "home":
                            home_score = score_val
                        else:
                            away_score = score_val
                    except (ValueError, TypeError):
                        pass

            games.append({
                "season": dt.year,
                "match_date": target_date,
                "home_team": home,
                "away_team": away,
                "status": mapped,
                "home_team_score": home_score,
                "away_team_score": away_score,
            })
        return games
