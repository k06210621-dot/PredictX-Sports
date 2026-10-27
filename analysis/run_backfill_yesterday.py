#!/usr/bin/env python3
"""
run_backfill_yesterday.py
=========================
「昨日補抓」主程式 — 每天定時補抓已完成賽事的最終比分

設計：
- 復用 ingest/ 的 BaseIngester 與各聯盟 fetcher
- 抓「昨日」單日，確保 MLB / NPB / NBA 賽事都已 Final
- 上傳時走既有 /api/insert_games，會自動 UPDATE 既有 game 的 score / status

Cron Schedule（Railway UTC, 台北 UTC+8）：
- 06:00 UTC = 14:00 台北
  → MLB 昨日（美東晚間場次台北凌晨結束，14:00 已 Final）
  → NPB 昨日（NPB 晚間 18:00 開打，台北 22:00 前結束，14:00 補抓昨日已 Final）
  → NBA 昨日（NBA 跨日賽，台北下午 14:00 已是美東 02:00，前一晚賽事都已 Final）
  → CPBL 昨日（CPBL 多為下午場，台北 14:00 抓昨日）

⚠️ 時區重要提醒：
- 本腳本 --date 與 base.backfill_yesterday() 內部 target_date 預設為「台北昨日」
- MLB 與 NBA 在 /api/games 已做 match_date + 1（美東→台北）
- 因此 ingest/ 端的 target_date 對 MLB/NBA 應「再往前一天」才會對到 API 顯示日期
- 為簡化使用，本腳本一律把 target_date 視為「API 顯示的日期」
  → 若要補抓 APP 顯示的 6/16 賽事，請傳 --date 2026-06-15（美東日期）
  → MLB 補抓「APP 昨日」實際要傳台北昨天 - 1 天

執行：
    python run_backfill_yesterday.py                  # 補抓台北昨日（MLB/NBA 自動 -1 天）
    python run_backfill_yesterday.py --date 2026-06-16 # 指定 API 顯示的日期
    python run_backfill_yesterday.py --leagues MLB    # 只跑指定聯盟
    python run_backfill_yesterday.py --dry-run        # 只抓不上傳
"""

import os
import sys
import argparse
import logging
import time
from datetime import datetime, timedelta

# 確保 analysis/ 在 sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ingest.mlb import MLBIngester
from ingest.npb import NPBIngester
from ingest.cpbl import CPBLIngester
from ingest.nba import NBAIngester

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
)
LOGGER = logging.getLogger("run_backfill_yesterday")

# 四大聯盟註冊表
LEAGUE_REGISTRY = {
    "MLB":  (MLBIngester,  "MLB 昨日補抓 (台北 14:00 抓美東晚間 Final)"),
    "NPB":  (NPBIngester,  "NPB 昨日補抓 (台北 14:00 抓前一晚 Final)"),
    "CPBL": (CPBLIngester, "CPBL 昨日補抓 (台北 14:00 抓昨日 Final)"),
    "NBA":  (NBAIngester,  "NBA 昨日補抓 (台北 14:00 抓美東前夜 Final)"),
}


def main():
    parser = argparse.ArgumentParser(description='昨日補抓主程式')
    parser.add_argument(
        "--date", type=str, default="",
        help="指定日期 (YYYY-MM-DD)，預設為昨日"
    )
    parser.add_argument(
        "--window-days", type=int, default=7,
        help="回溯補抓天數（D-N～D-1，預設 7 天；--date 指定時忽略此參數）"
    )
    parser.add_argument(
        "--leagues", type=str, default=",".join(LEAGUE_REGISTRY.keys()),
        help=f"指定聯盟（逗號分隔）, 預設全部。可選: {','.join(LEAGUE_REGISTRY.keys())}"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="只抓不上傳, 方便除錯"
    )
    args = parser.parse_args()

    target_date = args.date.strip()
    single_mode = bool(target_date)
    if single_mode:
        app_dates = [target_date]
    else:
        # 🆕 [2026-10-27 P2] 預設回溯 7 天做冪等重查，避免單日漏抓永久缺資料
        today = datetime.now()
        app_dates = [
            (today - timedelta(days=i)).strftime("%Y-%m-%d")
            for i in range(max(1, args.window_days), 0, -1)
        ]

    selected = [s.strip().upper() for s in args.leagues.split(",") if s.strip()]
    for code in selected:
        if code not in LEAGUE_REGISTRY:
            LOGGER.error(f"❌ 不支援聯盟: {code}（可用: {','.join(LEAGUE_REGISTRY.keys())}）")
            return 1

    # 時區換算：MLB/NBA 的資料存 match_date = 美東日期，
    # /api/games 查詢會 +1 顯示為台北日期。
    # 因此 ingest 端抓的 target_date 應為「美東日期」= APP 顯示日期 - 1 天。
    US_DATE_LEAGUES = {"MLB", "NBA"}

    def to_league_date(code: str, app_date: str) -> str:
        if code in US_DATE_LEAGUES:
            return (datetime.strptime(app_date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
        return app_date

    LOGGER.info("=" * 60)
    LOGGER.info(f"=== 補抓 Pipeline START === {datetime.now().isoformat()}")
    LOGGER.info(
        f"APP 日期: {app_dates[0]} ~ {app_dates[-1]}（{len(app_dates)} 天）| "
        f"leagues: {selected} | dry_run={args.dry_run}"
    )
    LOGGER.info("=" * 60)

    start = time.time()
    results: dict = {}

    for code in selected:
        cls, desc = LEAGUE_REGISTRY[code]
        LOGGER.info(f"\n[{code}] {desc}")
        ingester = cls()
        day_results = {}
        for app_date in app_dates:
            league_target = to_league_date(code, app_date)
            try:
                ok = ingester.backfill_yesterday(target_date=league_target, dry_run=args.dry_run)
            except Exception as e:
                LOGGER.error(f"[{code}] ❌ {app_date}（抓 {league_target}）失敗: {e}")
                ok = False
            day_results[app_date] = "OK" if ok else "FAIL"
        ok_count = sum(1 for v in day_results.values() if v == "OK")
        results[code] = "OK" if ok_count == len(day_results) else (
            "PARTIAL_FAIL" if ok_count else "FAIL"
        )
        LOGGER.info(
            f"[{code}] 補抓結果: " + " ".join(f"{d}={s}" for d, s in day_results.items())
        )
        try:
            if hasattr(ingester, "close"):
                ingester.close()
        except Exception:
            pass

    elapsed = time.time() - start
    LOGGER.info("\n" + "=" * 60)
    LOGGER.info(f"=== 昨日補抓 Pipeline END === 耗時 {elapsed:.1f}s")
    for code, status in results.items():
        LOGGER.info(f"  {code}: {status}")
    LOGGER.info("=" * 60)

    # 若全部失敗, exit 1（讓 cron 觸發告警）
    if all(s == "FAIL" for s in results.values()):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())