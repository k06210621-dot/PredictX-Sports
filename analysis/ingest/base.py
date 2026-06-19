#!/usr/bin/env python3
"""
ingest/base.py
==============
通用 fetcher 介面 — 所有聯賽 fetcher 必繼承此 base class

設計：
- 各 fetcher 只負責「對單一日期抓資料」
- 重試、退避、上傳、降冪全在 BaseIngester 統一處理
- 加新聯盟只要新增一個 class，無需改主程式
"""

import os
import time
import logging
import requests
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from datetime import datetime, timedelta

LOGGER = logging.getLogger("ingest.base")


class BaseIngester(ABC):
    """所有賽事 ingestion fetcher 的 base class"""

    # 子類別需設定
    league_code: str = ""            # "MLB" / "NPB" / ...
    league_days_ahead: int = 2       # 一次抓今天到 +N 天
    source_name: str = ""            # 寫進日誌的標籤

    def __init__(self):
        self.cloud_url = os.getenv(
            "CLOUD_API_URL",
            "https://predictx-sports-production.up.railway.app",
        ).rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "application/json",
        })

    @abstractmethod
    def fetch_games(self, target_date: str) -> List[Dict[str, Any]]:
        """
        抓取指定日期（YYYY-MM-DD）的賽事
        回傳 list of dict，至少包含：
          - season: int
          - match_date: "YYYY-MM-DD"
          - home_team: str
          - away_team: str
          - status: "SCHEDULED" / "FINAL"
        """
        raise NotImplementedError

    def _normalize(self, game: Dict[str, Any]) -> Dict[str, Any]:
        """統一欄位格式為雲端 insert_games 端點要求"""
        status = str(game.get("status", "SCHEDULED")).upper()
        if status in ("FINISHED", "FINAL"):
            status = "FINAL"
        elif status in ("IN_PROGRESS", "LIVE"):
            status = "LIVE"
        elif status in ("POSTPONED",):
            status = "POSTPONED"
        else:
            status = "SCHEDULED"
        return {
            "season": game.get("season", datetime.now().year),
            "match_date": game.get("match_date"),
            "home_team": game.get("home_team"),
            "away_team": game.get("away_team"),
            "status": status,
            "home_team_score": game.get("home_team_score"),
            "away_team_score": game.get("away_team_score"),
        }

    def upload(self, games: List[Dict[str, Any]]) -> bool:
        """POST 到雲端 /api/insert_games"""
        normalized = [
            self._normalize(g) for g in games
            if g.get("home_team") and g.get("away_team") and g.get("match_date")
        ]
        if not normalized:
            LOGGER.info(f"[{self.league_code}] 無資料需上傳")
            return True

        endpoint = f"{self.cloud_url}/api/insert_games"
        try:
            resp = self.session.post(endpoint, json={"games": normalized}, timeout=60)
            if resp.status_code != 200:
                LOGGER.error(f"[{self.league_code}] ❌ HTTP {resp.status_code}: {resp.text[:200]}")
                return False
            r = resp.json()
            LOGGER.info(
                f"[{self.league_code}] ✅ 上傳 {len(normalized)} 場 → "
                f"inserted={r.get('inserted')}, skipped={r.get('skipped')}"
            )
            return True
        except Exception as e:
            LOGGER.error(f"[{self.league_code}] ❌ 上傳失敗: {e}")
            return False

    def run(self, dry_run: bool = False) -> bool:
        """
        主流程：對未來 league_days_ahead 天逐日抓 → 上傳
        重試機制：最多 3 次，指數退避（2/4/8 秒）
        """
        LOGGER.info(f"[{self.league_code}] ===== 開始抓取 =====")
        all_games: List[Dict[str, Any]] = []
        today = datetime.now()
        ok = True

        for i in range(self.league_days_ahead + 1):
            target = (today + timedelta(days=i)).strftime("%Y-%m-%d")
            delay = 2
            games_for_day: List[Dict[str, Any]] = []
            for attempt in range(1, 4):  # 3 次重試
                try:
                    games_for_day = self.fetch_games(target)
                    LOGGER.info(
                        f"[{self.league_code}] {target} 嘗試 #{attempt} → {len(games_for_day)} 場"
                    )
                    break
                except Exception as e:
                    LOGGER.warning(
                        f"[{self.league_code}] {target} 嘗試 #{attempt} 失敗: {e}"
                    )
                    if attempt < 3:
                        time.sleep(delay)
                        delay *= 2
                    else:
                        LOGGER.error(
                            f"[{self.league_code}] {target} 3 次都失敗，跳過此日期"
                        )
                        ok = False
            all_games.extend(games_for_day)

        run_today = today.strftime("%Y-%m-%d")
        today_games = [g for g in all_games if g.get("match_date") == run_today]
        if self.league_code == "NPB":
            npb_today = len(today_games)
            # 健全性檢查：6 月交流戰密集日，NPB 通常有 5-6 場；非交流戰期間可能僅 3 場（中央聯盟）
            # 若 NPB 抓取結果 < 3 場，幾乎一定是抓錯頁面
            if 0 < npb_today < 3:
                LOGGER.warning(
                    f"[{self.league_code}] {run_today} 只抓到 {npb_today} 場，"
                    f"可能是單一聯盟頁面（應含全 12 隊）。請檢查 fetcher 來源 URL。"
                )

        if dry_run:
            LOGGER.info(f"[{self.league_code}] (dry-run) 共 {len(all_games)} 場，不上傳")
            for g in all_games:
                LOGGER.info(
                    f"  {g.get('match_date')} {g.get('home_team')} vs {g.get('away_team')}"
                )
            return ok

        upload_ok = self.upload(all_games)
        return ok and upload_ok

    def backfill_yesterday(self, target_date: str = "", dry_run: bool = False) -> bool:
        """
        補抓昨日（或指定日期）賽事比分。
        用於每日定時補抓已完成賽事的最終比分，避免 cron 開打時間太早漏掉。

        與 run() 的差異：
        - 只抓單一日期（昨日），確保 API 回傳的是 Final 狀態帶 score
        - fetch_games() 子類別實作直接查詢單日即可
        - 上傳時仍走既有 /api/insert_games 端點，會自動 UPDATE 既有 game 的 score/status
        """
        if not target_date:
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            target_date = yesterday

        LOGGER.info(f"[{self.league_code}] ===== 昨日補抓 ===== {target_date}")
        games: List[Dict[str, Any]] = []
        delay = 2

        for attempt in range(1, 4):  # 3 次重試
            try:
                games = self.fetch_games(target_date)
                LOGGER.info(
                    f"[{self.league_code}] {target_date} 補抓 #{attempt} → {len(games)} 場"
                )
                break
            except Exception as e:
                LOGGER.warning(
                    f"[{self.league_code}] {target_date} 補抓 #{attempt} 失敗: {e}"
                )
                if attempt < 3:
                    time.sleep(delay)
                    delay *= 2
                else:
                    LOGGER.error(
                        f"[{self.league_code}] {target_date} 補抓 3 次都失敗"
                    )
                    return False

        if dry_run:
            final_count = sum(1 for g in games if g.get("status") == "FINAL")
            LOGGER.info(
                f"[{self.league_code}] (dry-run) {target_date} 共 {len(games)} 場，"
                f"其中 Final={final_count} 場"
            )
            for g in games:
                hs = g.get("home_team_score")
                a_s = g.get("away_team_score")
                LOGGER.info(
                    f"  {g.get('match_date')} {g.get('home_team')} vs "
                    f"{g.get('away_team')} [{g.get('status')}] {hs}-{a_s}"
                )
            return True

        return self.upload(games)
