#!/usr/bin/env python3
"""
ingest/npb.py
=============
NPB fetcher — 從 npb.jp 官方網站抓賽程
"""

import re
import logging
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from .base import BaseIngester

LOGGER = logging.getLogger("ingest.npb")

NPB_DAILY_URL = "https://npb.jp/bis/eng/{year}/games/gm{date}.html"

NPB_TEAMS = {
    "Yomiuri":    "Yomiuri Giants",
    "Hanshin":    "Hanshin Tigers",
    "Chunichi":   "Chunichi Dragons",
    "DeNA":       "Yokohama DeNA BayStars",
    "Hiroshima":  "Hiroshima Toyo Carp",
    "Yakult":     "Tokyo Yakult Swallows",
    "Seibu":      "Saitama Seibu Lions",
    "Rakuten":    "Tohoku Rakuten Golden Eagles",
    "SoftBank":   "Fukuoka SoftBank Hawks",
    "Nippon-Ham": "Hokkaido Nippon-Ham Fighters",
    "Lotte":      "Chiba Lotte Marines",
    "ORIX":       "ORIX Buffaloes",
}


def _resolve_team(text: str):
    clean = re.sub(r'[0-9]', '', text).strip()
    if clean in NPB_TEAMS:
        return NPB_TEAMS[clean]
    for key, full in NPB_TEAMS.items():
        if key.lower() in clean.lower():
            return full
    return None


class NPBIngester(BaseIngester):
    league_code = "NPB"
    league_days_ahead = 1
    source_name = "npb_official"

    def fetch_games(self, target_date: str) -> List[Dict[str, Any]]:
        dt = datetime.strptime(target_date, "%Y-%m-%d")
        date_str = dt.strftime("%Y%m%d")
        url = NPB_DAILY_URL.format(year=dt.year, date=date_str)
        resp = self.session.get(url, timeout=20)
        if resp.status_code != 200:
            raise RuntimeError(f"NPB 官網 HTTP {resp.status_code}")

        soup = BeautifulSoup(resp.text, "lxml")
        gr = soup.find("div", class_="game_result")
        if not gr:
            LOGGER.info(f"NPB {target_date} 休兵日（無 game_result）")
            return []

        left_unit = gr.find("div", class_="left_unit")
        if not left_unit:
            return []
        units = left_unit.find_all("div", class_="unit")
        LOGGER.info(f"NPB {target_date} 找到 {len(units)} 場")

        games: List[Dict[str, Any]] = []
        for unit in units:
            team_left = unit.find("div", class_="team_left")
            team_right = unit.find("div", class_="team_right")
            if not team_left or not team_right:
                continue
            home_name_div = team_left.find("div", class_="team_name")
            away_name_div = team_right.find("div", class_="team_name")
            home_score_div = team_left.find("div", class_="score_text")
            away_score_div = team_right.find("div", class_="score_text")
            if not home_name_div or not away_name_div:
                continue

            home_full = _resolve_team(home_name_div.get_text(strip=True))
            away_full = _resolve_team(away_name_div.get_text(strip=True))
            if not home_full or not away_full:
                continue

            home_score_text = home_score_div.get_text(strip=True) if home_score_div else ""
            away_score_text = away_score_div.get_text(strip=True) if away_score_div else ""
            home_score = int(home_score_text) if home_score_text.isdigit() else None
            away_score = int(away_score_text) if away_score_text.isdigit() else None
            status = "FINAL" if (home_score is not None and away_score is not None) else "SCHEDULED"

            games.append({
                "season": dt.year,
                "match_date": target_date,
                "home_team": home_full,
                "away_team": away_full,
                "status": status,
            })
        return games


from datetime import datetime
