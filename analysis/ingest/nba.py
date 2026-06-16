#!/usr/bin/env python3
"""
ingest/nba.py
=============
NBA fetcher — 從 ESPN 公開 scoreboard API 抓賽程
"""

import logging
from typing import List, Dict, Any
from datetime import datetime
from .base import BaseIngester

LOGGER = logging.getLogger("ingest.nba")

ESPN_NBA_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"


class NBAIngester(BaseIngester):
    league_code = "NBA"
    league_days_ahead = 2
    source_name = "espn_nba"

    def fetch_games(self, target_date: str) -> List[Dict[str, Any]]:
        """ESPN scoreboard 用 YYYYMMDD 格式"""
        dt = datetime.strptime(target_date, "%Y-%m-%d")
        date_param = dt.strftime("%Y%m%d")
        url = f"{ESPN_NBA_SCOREBOARD}?dates={date_param}"
        resp = self.session.get(url, timeout=20)
        if resp.status_code != 200:
            raise RuntimeError(f"ESPN NBA HTTP {resp.status_code}")

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
            games.append({
                "season": dt.year,
                "match_date": target_date,
                "home_team": home,
                "away_team": away,
                "status": mapped,
            })
        return games
