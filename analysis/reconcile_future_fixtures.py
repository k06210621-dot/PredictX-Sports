#!/usr/bin/env python3
"""
reconcile_future_fixtures.py
============================
未來賽程對帳（幽靈賽事清理）

背景（2026-10-30）：
- MLB 世界大賽 G6/G7、NPB 日本大賽 G5/G7 屬「如有必要」的條件式賽程
- 系列賽提前結束後，官方來源直接移除，但 DB 仍殘留 SCHEDULED → App 顯示幽靈賽事

策略（保守、避免誤刪）：
1. 只處理 status=SCHEDULED 的賽事
2. 逐日向官方來源確認（CPBL 官方 / NPB Yahoo / MLB StatsAPI / NBA ESPN）
3. 該日官方成功回傳「0 場」→ 當日 DB 的 SCHEDULED 皆為幽靈 → 設為 CANCELLED
4. 官方來源失敗（例外）→ 跳過該聯盟，不做任何變更
5. 官方有其他賽事但缺某一場 → 只記錄 warning，不自動取消（避免誤殺）

寫入方式：走既有 /api/insert_games（status=CANCELLED），不需要 DB 連線。
搭配 api_server 的 /api/games 過濾 CANCELLED，App 即不再顯示。

執行：
    python reconcile_future_fixtures.py                 # dry-run（預設）
    python reconcile_future_fixtures.py --apply         # 實際寫入
    python reconcile_future_fixtures.py --leagues MLB,NPB --days-ahead 7 --apply
"""
import os
import sys
import json
import time
import logging
import argparse
import urllib.request
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ingest.mlb import MLBIngester
from ingest.npb import NPBIngester
from ingest.cpbl import CPBLIngester
from ingest.nba import NBAIngester
from ingest.wnba import WNBAIngester

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
LOGGER = logging.getLogger("reconcile_future_fixtures")

API_BASE = os.getenv("PREDICTX_API", "https://predictx-sports-production.up.railway.app")
TW_TZ = timezone(timedelta(hours=8))
US_DATE_LEAGUES = {"MLB", "NBA", "WNBA"}  # API 顯示日期 = DB 日期 + 1
REGISTRY = {
    "MLB": MLBIngester,
    "NPB": NPBIngester,
    "CPBL": CPBLIngester,
    "NBA": NBAIngester,
    "WNBA": WNBAIngester,
}


def _api_get(path: str, timeout: int = 40):
    req = urllib.request.Request(f"{API_BASE}{path}", headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _api_post(path: str, payload: dict, timeout: int = 60):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{API_BASE}{path}", data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def fetch_official(ingester, league: str, date_str: str):
    """嚴格抓官方賽程；失敗會拋例外（呼叫端據此跳過，不做變更）"""
    if league == "CPBL":
        # 官方 getgamedatas（含延賽/季後賽），失敗即拋例外
        return ingester._fetch_games_official(date_str)
    if league == "NPB":
        # npb.jp 目前不可達，直接走 Yahoo（HTTP 失敗會拋例外）
        return ingester._fetch_games_yahoo(date_str)
    return ingester.fetch_games(date_str)


def reconcile_future_fixtures(leagues=None, days_ahead: int = 7, apply: bool = False) -> dict:
    today = datetime.now(TW_TZ).date()
    leagues = leagues or ["MLB", "NPB", "CPBL"]
    summary = {}

    for league in leagues:
        cls = REGISTRY.get(league)
        if not cls:
            continue
        ingester = cls()
        stats = {"checked_dates": 0, "cancelled": 0, "warnings": 0, "source_failed": 0, "cancelled_games": []}
        try:
            db_games = _api_get(f"/api/games?league={league}&days=14")
        except Exception as e:
            LOGGER.error(f"[{league}] 讀取 DB 賽事失敗: {e}")
            stats["source_failed"] += 1
            summary[league] = stats
            continue

        # API → DB 日期（MLB/NBA/WNBA 顯示 +1）
        scheduled = []
        for g in db_games:
            if (g.get("status") or "").upper() != "SCHEDULED":
                continue
            try:
                display = datetime.strptime(g["match_date"], "%Y-%m-%d").date()
            except (KeyError, ValueError):
                continue
            db_date = display - timedelta(days=1) if league in US_DATE_LEAGUES else display
            if today - timedelta(days=1) <= db_date <= today + timedelta(days=days_ahead):
                scheduled.append((db_date, g))

        by_date = {}
        for d, g in scheduled:
            by_date.setdefault(d, []).append(g)

        for d in sorted(by_date):
            try:
                official = fetch_official(ingester, league, d.strftime("%Y-%m-%d"))
            except Exception as e:
                stats["source_failed"] += 1
                LOGGER.warning(f"[{league}] {d} 官方來源失敗，跳過（不做變更）: {e}")
                continue
            stats["checked_dates"] += 1
            official_pairs = {
                ((o.get("home_team") or "").strip(), (o.get("away_team") or "").strip())
                for o in official
            }

            if not official:
                for g in by_date[d]:
                    rec = {
                        "game_id": g.get("game_id"),
                        "league": league,
                        "db_date": str(d),
                        "display_date": g.get("match_date"),
                        "home_team": g.get("home_team"),
                        "away_team": g.get("away_team"),
                    }
                    LOGGER.warning(
                        f"[{league}] 幽靈賽事（官方 0 場）: {d} "
                        f"{rec['away_team']} @ {rec['home_team']} → CANCELLED"
                    )
                    if apply:
                        try:
                            _api_post("/api/insert_games", {"games": [{
                                "season": d.year,
                                "match_date": str(d),
                                "home_team": rec["home_team"],
                                "away_team": rec["away_team"],
                                "status": "CANCELLED",
                            }]})
                            stats["cancelled"] += 1
                            stats["cancelled_games"].append(rec)
                        except Exception as e:
                            LOGGER.error(f"[{league}] 取消失敗 {rec['game_id']}: {e}")
                    else:
                        stats["cancelled"] += 1
                        stats["cancelled_games"].append(rec)
            else:
                for g in by_date[d]:
                    pair = ((g.get("home_team") or "").strip(), (g.get("away_team") or "").strip())
                    if pair not in official_pairs:
                        stats["warnings"] += 1
                        LOGGER.warning(
                            f"[{league}] {d} DB 有但官方賽程缺此場（不自動取消）: "
                            f"{pair[1]} @ {pair[0]}"
                        )
        summary[league] = stats
        LOGGER.info(
            f"[{league}] 完成：檢查 {stats['checked_dates']} 日、"
            f"取消 {stats['cancelled']} 場、警告 {stats['warnings']}、來源失敗 {stats['source_failed']}"
            f"{'（dry-run）' if not apply else ''}"
        )
        try:
            if hasattr(ingester, "close"):
                ingester.close()
        except Exception:
            pass

    return summary


def main():
    parser = argparse.ArgumentParser(description="未來賽程對帳 / 幽靈賽事清理")
    parser.add_argument("--leagues", default="MLB,NPB,CPBL", help="逗號分隔（預設 MLB,NPB,CPBL）")
    parser.add_argument("--days-ahead", type=int, default=7, help="往後檢查天數（預設 7）")
    parser.add_argument("--apply", action="store_true", help="實際寫入 CANCELLED（預設 dry-run）")
    args = parser.parse_args()

    leagues = [s.strip().upper() for s in args.leagues.split(",") if s.strip()]
    summary = reconcile_future_fixtures(leagues=leagues, days_ahead=args.days_ahead, apply=args.apply)
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
