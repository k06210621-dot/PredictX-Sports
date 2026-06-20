#!/usr/bin/env python3
"""
ingest/mlb.py
=============
MLB fetcher — 從 statsapi.mlb.com 官方 API 抓賽程 + 先發投手對位

hydrate 參數說明:
- team: 球隊資訊
- probablePitcher: 預定先發投手
- game(content): 賽事內容（用於進階數據）
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
        """從 MLB Stats API 抓指定日期賽程 + 先發投手
        日期格式 YYYY-MM-DD, 回傳 schedule 內所有 games
        """
        params = {
            "sportId": 1,
            "startDate": target_date,
            "endDate": target_date,
            "hydrate": "team,probablePitcher",  # 加 probablePitcher 抓先發投手
        }
        resp = self.session.get(MLB_SCHEDULE_URL, params=params, timeout=30)
        if resp.status_code != 200:
            raise RuntimeError(f"MLB API HTTP {resp.status_code}")

        data = resp.json()
        games: List[Dict[str, Any]] = []
        for date_block in data.get("dates", []):
            for g in date_block.get("games", []):
                status_code = g.get("status", {}).get("abstractGameState", "Preview")
                teams = g.get("teams", {})
                home_team_data = teams.get("home", {}).get("team", {})
                away_team_data = teams.get("away", {}).get("team", {})
                home = home_team_data.get("name")
                away = away_team_data.get("name")
                if not home or not away:
                    continue
                if status_code == "Final":
                    status = "FINAL"
                elif status_code == "Live":
                    status = "LIVE"
                else:
                    status = "SCHEDULED"

                home_score = teams.get("home", {}).get("score")
                away_score = teams.get("away", {}).get("score")

                # 先發投手（MLB API 用 hydrate=probablePitcher）
                home_pitcher = self._parse_pitcher(teams.get("home", {}).get("probablePitcher"))
                away_pitcher = self._parse_pitcher(teams.get("away", {}).get("probablePitcher"))

                games.append({
                    "season": datetime.now().year,
                    "match_date": target_date,
                    "home_team": home,
                    "away_team": away,
                    "status": status,
                    "home_team_score": home_score,
                    "away_team_score": away_score,
                    # 先發投手對位
                    "home_pitcher": home_pitcher,
                    "away_pitcher": away_pitcher,
                })
        return games

    def _parse_pitcher(self, pitcher_data: Dict[str, Any]) -> Dict[str, Any]:
        """解析投手資料為簡化結構"""
        if not pitcher_data:
            return {"name": "TBD", "id": None, "era": None, "wins": None, "losses": None}
        return {
            "name": pitcher_data.get("fullName", "TBD"),
            "id": pitcher_data.get("id"),
            "era": None,  # MLB API schedule 不回傳 ERA，需另外查
            "wins": None,
            "losses": None,
        }