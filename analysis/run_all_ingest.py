#!/usr/bin/env python3
"""
run_all_ingest.py
=================
五大賽事自動 ingestion 主程式

設計：
- 5 個 fetcher（MLB / NPB / CPBL / NBA / FIFA）依序執行
- 排程最佳化：各聯盟對齊開打時間往前 6 小時 ingest
- 重試已在 BaseIngester.run() 內處理

Cron Schedule（Railway UTC, 台北 UTC+8）：
- 01:00 UTC = 09:00 台北 → MLB 當日（MLB 開打時間台北 09:00 之後）
- 09:00 UTC = 17:00 台北 → NPB 當日 + 明日（NPB 開打時間台北 18:00）
- 02:00 UTC = 10:00 台北 → CPBL 當日
- 06:00 UTC = 14:00 台北 → NBA 當日（NBA 開打台北上午 08:00 之後, 涵蓋跨日賽）
- 03:00 UTC = 11:00 台北 → FIFA 當日（歐洲下午場, 台北夜晚開打）

執行：
    python run_all_ingest.py                  # 全部跑
    python run_all_ingest.py --leagues MLB,NPB # 只跑指定
    python run_all_ingest.py --dry-run         # 只抓不上傳
"""

import os
import sys
import argparse
import logging
import time
from datetime import datetime

# 確保 analysis/ 在 sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ingest.mlb import MLBIngester
from ingest.npb import NPBIngester
from ingest.cpbl import CPBLIngester
from ingest.nba import NBAIngester
from ingest.fifa import FIFAIngester

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
)
LOGGER = logging.getLogger("run_all_ingest")

# 5 大賽事註冊表（加新聯盟只要在這加一行）
LEAGUE_REGISTRY = {
    "MLB":  (MLBIngester, "MLB 開打前 6hr ingest (台北 09:00)"),
    "NPB":  (NPBIngester, "NPB 開打前 6hr ingest (台北 17:00)"),
    "CPBL": (CPBLIngester, "CPBL 開打前 6hr ingest (台北 10:00)"),
    "NBA":  (NBAIngester, "NBA 開打前 6hr ingest (台北 14:00)"),
    "FIFA": (FIFAIngester, "FIFA 跨日 ingest (台北 11:00)"),
}


def main():
    parser = argparse.ArgumentParser(description='五大賽事自動 ingestion')
    parser.add_argument(
        "--leagues", type=str, default=",".join(LEAGUE_REGISTRY.keys()),
        help=f"指定聯盟（逗號分隔）, 預設全部。可選: {','.join(LEAGUE_REGISTRY.keys())}"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="只抓不上傳, 方便除錯"
    )
    args = parser.parse_args()

    selected = [s.strip().upper() for s in args.leagues.split(",") if s.strip()]
    for code in selected:
        if code not in LEAGUE_REGISTRY:
            LOGGER.error(f"❌ 不支援聯盟: {code}（可用: {','.join(LEAGUE_REGISTRY.keys())})")
            return 1

    LOGGER.info("=" * 60)
    LOGGER.info(f"=== 五大賽事 Ingestion Pipeline START === {datetime.now().isoformat()}")
    LOGGER.info(f"Selected leagues: {selected} | dry_run={args.dry_run}")
    LOGGER.info("=" * 60)

    start = time.time()
    results: dict = {}

    for code in selected:
        cls, desc = LEAGUE_REGISTRY[code]
        LOGGER.info(f"\n[{code}] {desc}")
        ingester = cls()
        try:
            ok = ingester.run(dry_run=args.dry_run)
            results[code] = "OK" if ok else "PARTIAL_FAIL"
        except Exception as e:
            LOGGER.error(f"[{code}] ❌ 整體失敗: {e}", exc_info=True)
            results[code] = "FAIL"
        finally:
            try:
                if hasattr(ingester, "close"):
                    ingester.close()
            except Exception:
                pass

    elapsed = time.time() - start
    LOGGER.info("\n" + "=" * 60)
    LOGGER.info(f"=== Pipeline END === 耗時 {elapsed:.1f}s")
    for code, status in results.items():
        LOGGER.info(f"  {code}: {status}")
    LOGGER.info("=" * 60)

    # 若全部失敗, exit 1（讓 cron 觸發告警）
    if all(s == "FAIL" for s in results.values()):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
