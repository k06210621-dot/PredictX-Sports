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
        # 🆕 [2026-07-28] 未來日期防護（與 CPBL 一致）
        from datetime import date
        is_future = dt.date() > date.today()
        date_param = dt.strftime("%Y%m%d")
        url = f"{ESPN_NBA_SCOREBOARD}?dates={date_param}"
        resp = self.session.get(url, timeout=20)
        if resp.status_code != 200:
            raise RuntimeError(f"ESPN NBA HTTP {resp.status_code}")

        data = resp.json()
        games: List[Dict[str, Any]] = []
        for event in data.get("events", []):
            # 🆕 [2026-10-09] 季前賽改為一併匯入（原 2026-10-01 的 season.type=1 過濾已移除）
            # 使用者指示：NBA 季前賽賽程需寫入 DB，並顯示於 App 賽事卡片。
            # ESPN season.type：1=preseason、2=regular-season（含 NBA Cup）、3=post-season。
            # 季前賽為練兵陣容，AI 預測參考性較低 —— 交由分析層的信心校準處理，
            # 不在 ingest 層丟棄資料（2025-26 季前賽 61 場即完整入庫並產生分析）。
            season_type = (event.get("season") or {}).get("type")
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

            # 🆕 [2026-07-28] 未來日期防護：未來日期一律 SCHEDULED 且清空比分
            if is_future:
                mapped = "SCHEDULED"
                home_score = None
                away_score = None

            # 🆕 [2026-10-09] 未開打賽事不得帶比分：
            # ESPN 對 SCHEDULED 賽事回傳 score="0"（非缺值），若原樣寫入會讓 App
            # 顯示「0-0」而非「未開打」，與 MLB/NPB 的 NULL 慣例不一致。
            # 實證：WNBA 既有 3 筆 SCHEDULED 帶 0 分即為此因。
            if mapped == "SCHEDULED":
                home_score = None
                away_score = None

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
