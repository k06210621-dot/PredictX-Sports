#!/usr/bin/env python3
"""
ingest/fifa.py
==============
FIFA fetcher — 從 ESPN 公開 scoreboard API 抓足球賽程
注意：fbref.com 封鎖爬蟲, 改用 ESPN 公開端點
"""

import logging
from typing import List, Dict, Any
from datetime import datetime
from .base import BaseIngester

LOGGER = logging.getLogger("ingest.fifa")

ESPN_FOOTBALL_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard"

# 主要足球聯賽（fbref 封鎖後, 用 ESPN 備案）
LEAGUES = [
    ("eng.1", "Premier League"),
    ("esp.1", "La Liga"),
    ("ger.1", "Bundesliga"),
    ("ita.1", "Serie A"),
    ("fra.1", "Ligue 1"),
    ("uefa.champions", "UEFA Champions League"),
]


class FIFAIngester(BaseIngester):
    league_code = "FIFA"
    league_days_ahead = 2
    source_name = "espn_football"

    def fetch_games(self, target_date: str) -> List[Dict[str, Any]]:
        dt = datetime.strptime(target_date, "%Y-%m-%d")
        date_param = dt.strftime("%Y%m%d")
        games: List[Dict[str, Any]] = []

        for slug, _name in LEAGUES:
            url = f"{ESPN_FOOTBALL_SCOREBOARD.format(league=slug)}?dates={date_param}"
            try:
                resp = self.session.get(url, timeout=20)
                if resp.status_code != 200:
                    continue
                data = resp.json()
            except Exception as e:
                LOGGER.warning(f"  FIFA {slug} {target_date} 失敗: {e}")
                continue

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
