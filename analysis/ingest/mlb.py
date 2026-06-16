#!/usr/bin/env python3
"""
ingest/mlb.py
=============
MLB fetcher — 從 statsapi.mlb.com 官方 API 抓賽程
"""

import re
import logging
from datetime import datetime
from typing import List, Dict, Any
from .base import BaseIngester

LOGGER = logging.getLogger("ingest.mlb")

MLB_SCHEDULE_URL = "https://statsapi.mlb.com/api/v1/schedule"


class MLBIngester(BaseIngester):
    league_code = "MLB"
    league_days_ahead = 2
    source_name = "mlb_statsapi"

    def fetch_games(self, target_date: str) -> List[Dict[str, Any]]:
        """從 MLB Stats API 抓指定日期賽程
        日期格式 YYYY-MM-DD, 回傳 schedule 內所有 games
        """
        params = {
            "sportId": 1,
            "startDate": target_date,
            "endDate": target_date,
            "hydrate": "team",
        }
        resp = self.session.get(MLB_SCHEDULE_URL, params=params, timeout=30)
        if resp.status_code != 200:
            raise RuntimeError(f"MLB API HTTP {resp.status_code}")

        data = resp.json()
        games: List[Dict[str, Any]] = []
        for date_block in data.get("dates", []):
            for g in date_block.get("games", []):
                status_code = g.get("status", {}).get("abstractGameState", "Preview")
                # Preview / Live / Final
                teams = g.get("teams", {})
                home = teams.get("home", {}).get("team", {}).get("name")
                away = teams.get("away", {}).get("team", {}).get("name")
                if not home or not away:
                    continue
                if status_code == "Final":
                    status = "FINAL"
                elif status_code == "Live":
                    status = "LIVE"
                else:
                    status = "SCHEDULED"
                games.append({
                    "season": datetime.now().year,
                    "match_date": target_date,
                    "home_team": home,
                    "away_team": away,
                    "status": status,
                })
        return games
