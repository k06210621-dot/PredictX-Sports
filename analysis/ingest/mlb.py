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
        # 🆕 [2026-07-28] 未來日期防護（與 CPBL 一致）：
        # 雖然 statsapi.mlb.com 對未來賽事只給 Preview 狀態，理論上安全
        # 但若 ingest 未來修改來源或對應邏輯變化，仍可能誤標 FINAL
        # 在 normalize 前先過濾：未來日期一律視為 SCHEDULED 且清空比分
        from datetime import date
        target_dt = datetime.strptime(target_date, "%Y-%m-%d").date()
        is_future = target_dt > date.today()

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
                # 🆕 [2026-09-28 修復] 延賽/取消判讀改用 detailedState
                # 根因：MLB Stats API 對 Postponed / Cancelled 的賽事，
                #   abstractGameState 仍回傳 "Final"（且無比分）。
                #   舊碼只讀 abstractGameState → 被當成 FINAL 寫入 DB，
                #   產生「status=FINAL 但比分 NULL」的錯誤狀態列。
                #   實證：9/22 Blue Jays @ Orioles（Postponed）、
                #        9/27 Orioles @ Yankees（Cancelled），
                #        兩者 abstractGameState 皆為 "Final"。
                # 影響：狀態標記錯誤 —— App 顯示「已完賽」但沒有比分，
                #   事實上是延賽/取消，應顯示為延賽。
                #   （註：延賽/平手導致「無驗證結果」是既有設計的預期行為，
                #     settlement_engine 有專門路徑標記 is_hit=None 並排除於
                #     命中率分母之外，此非本修復要處理的問題。）
                # 修法：先看 detailedState，延賽/取消優先映射為 POSTPONED，
                #   與 base.py _normalize 及 settlement_engine 的 POSTPONED
                #   處理路徑對齊，讓狀態如實反映賽事現況。
                status_obj = g.get("status", {}) or {}
                detailed_state = (status_obj.get("detailedState") or "").strip()
                status_code = status_obj.get("abstractGameState", "Preview")

                teams = g.get("teams", {}) or {}
                home_team_data = teams.get("home", {}).get("team", {})
                away_team_data = teams.get("away", {}).get("team", {})
                home = home_team_data.get("name")
                away = away_team_data.get("name")
                if not home or not away:
                    continue

                _ds_upper = detailed_state.upper()
                if _ds_upper in ("POSTPONED", "CANCELLED", "CANCELED",
                                 "SUSPENDED", "DELAYED"):
                    status = "POSTPONED"
                elif status_code == "Final":
                    status = "FINAL"
                elif status_code == "Live":
                    status = "LIVE"
                else:
                    status = "SCHEDULED"

                home_score = teams.get("home", {}).get("score")
                away_score = teams.get("away", {}).get("score")

                # 延賽/取消賽事不應帶比分（避免下游誤判為已完賽）
                if status == "POSTPONED":
                    home_score = None
                    away_score = None

                # 🆕 [2026-07-28] 未來日期防護：若 target_date 是未來日期
                # 一律強制 SCHEDULED 並清空比分，避免 settlement 提早結算
                if is_future:
                    status = "SCHEDULED"
                    home_score = None
                    away_score = None

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