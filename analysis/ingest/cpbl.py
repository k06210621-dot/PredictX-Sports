#!/usr/bin/env python3
"""
ingest/cpbl.py
==============
CPBL fetcher — 從 cpbl.com.tw 內部 API (getdetaillist) 抓中職賽程

注意：cpbl.com.tw 前端是 AngularJS SPA, 直接 curl HTML 只能拿到
{{ game.HomeTeamName }} 模板。真實資料要 POST /home/getdetaillist
"""

import re
import json
import logging
from typing import List, Dict, Any
from datetime import datetime
from .base import BaseIngester

LOGGER = logging.getLogger("ingest.cpbl")

CPBL_API_URL = "https://www.cpbl.com.tw/home/getdetaillist"
CPBL_COOKIE_URL = "https://www.cpbl.com.tw/"

# 中職 6 隊中英對照（CPBL API 回傳中文隊名 → 英文全名）
TEAM_NAME_MAP = {
    "中信兄弟": "CTBC Brothers",
    "中信": "CTBC Brothers",
    "兄弟": "CTBC Brothers",
    "富邦悍將": "Fubon Guardians",
    "富邦": "Fubon Guardians",
    "悍將": "Fubon Guardians",
    "統一獅": "Uni-President Lions",
    "統一": "Uni-President Lions",
    "樂天桃猿": "Rakuten Monkeys",
    "樂天": "Rakuten Monkeys",
    "桃猿": "Rakuten Monkeys",
    "味全龍": "Wei Chuan Dragons",
    "味全": "Wei Chuan Dragons",
    "台鋼雄鷹": "TSG Hawks",
    "台鋼": "TSG Hawks",
    "雄鷹": "TSG Hawks",
}


def _resolve_team(text: str):
    for kw, full in TEAM_NAME_MAP.items():
        if kw in text:
            return full
    return None


class CPBLIngester(BaseIngester):
    league_code = "CPBL"
    league_days_ahead = 2
    source_name = "cpbl_api"

    def __init__(self):
        super().__init__()
        # CPBL API 需要先 GET 首頁拿 cookie
        self._cookie_obtained = False

    def _ensure_cookie(self):
        if self._cookie_obtained:
            return
        try:
            self.session.get(CPBL_COOKIE_URL, timeout=15)
            self._cookie_obtained = True
        except Exception as e:
            LOGGER.warning(f"CPBL cookie 取得失敗: {e}")

    def fetch_games(self, target_date: str) -> List[Dict[str, Any]]:
        """POST getdetaillist 拿指定日期的賽事"""
        self._ensure_cookie()
        dt = datetime.strptime(target_date, "%Y-%m-%d")

        try:
            resp = self.session.post(
                CPBL_API_URL,
                data={"gameDate": target_date},
                headers={
                    "X-Requested-With": "XMLHttpRequest",
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                },
                timeout=20,
            )
        except Exception as e:
            raise RuntimeError(f"CPBL API 連線失敗: {e}")

        if resp.status_code != 200:
            raise RuntimeError(f"CPBL API HTTP {resp.status_code}")

        try:
            data = resp.json()
        except json.JSONDecodeError as e:
            raise RuntimeError(f"CPBL API 回應非 JSON: {e}")

        if not data.get("Success"):
            LOGGER.info(f"CPBL {target_date} API Success=False（可能休兵日）")
            return []

        raw = data.get("GameADetailJson")
        if not raw:
            return []

        if isinstance(raw, str):
            try:
                game_list = json.loads(raw)
            except json.JSONDecodeError:
                return []
        else:
            game_list = raw

        games: List[Dict[str, Any]] = []
        for g in game_list:
            home_raw = g.get("HomeTeamName", "")
            away_raw = g.get("VisitingTeamName", "")
            home = _resolve_team(home_raw)
            away = _resolve_team(away_raw)
            if not home or not away:
                continue

            home_score_raw = g.get("HomeTotalScore")
            away_score_raw = g.get("VisitingTotalScore")
            home_score = int(home_score_raw) if (home_score_raw is not None and str(home_score_raw).lstrip('-').isdigit()) else None
            away_score = int(away_score_raw) if (away_score_raw is not None and str(away_score_raw).lstrip('-').isdigit()) else None

            # GameDate 有時帶 "T" 分隔符, 統一取前 10 碼
            raw_date = g.get("GameDate", "") or target_date
            try:
                game_date = datetime.fromisoformat(raw_date.replace("T", " ")[:10]).strftime("%Y-%m-%d")
            except (ValueError, TypeError):
                game_date = target_date

            status = "FINAL" if (home_score is not None and away_score is not None) else "SCHEDULED"
            games.append({
                "season": dt.year,
                "match_date": game_date,
                "home_team": home,
                "away_team": away,
                "status": status,
            })
        if not games:
            LOGGER.info(f"CPBL {target_date} API 回傳空（可能休兵日）")
        return games
