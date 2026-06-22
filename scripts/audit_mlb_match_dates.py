#!/usr/bin/env python3
"""
scripts/audit_mlb_match_dates.py
================================
驗證雲端 PostgreSQL 中 MLB 賽事的 (home_team, away_team, match_date)
是否與 MLB Stats API 的一致。

不做任何修改 — 純查證並產出 report。
"""
import json
import os
import sys
import time
import urllib.request
from datetime import date, datetime, timedelta
from collections import defaultdict

MLB_SCHEDULE_URL = "https://statsapi.mlb.com/api/v1/schedule"
CLOUD_API = os.getenv("CLOUD_API_URL", "https://predictx-sports-production.up.railway.app").rstrip("/")


def fetch_cloud_mlb_games(taipei_date: str) -> list:
    """從雲端 API 拿指定台北日期的 MLB 賽事

    注意：API 對 MLB/NBA 會自動 +1 day（美東→台北）
    所以查 taipei_date=D 實際拿到 DB match_date=D-1 的賽事
    """
    url = f"{CLOUD_API}/api/games?league=MLB&date={taipei_date}"
    req = urllib.request.Request(url, headers={"User-Agent": "PredictX-Audit/1.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read().decode("utf-8"))
    return [g for g in data if g.get("match_date") == taipei_date]


def fetch_mlb_api_schedule(us_date: str) -> dict:
    """從 MLB Stats API 拿指定美東日期的 schedule，回傳 (home, away) -> game dict"""
    url = f"{MLB_SCHEDULE_URL}?sportId=1&startDate={us_date}&endDate={us_date}"
    req = urllib.request.Request(url, headers={"User-Agent": "curl/7.88.1"})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read().decode("utf-8"))
    pairs = {}
    for date_block in data.get("dates", []):
        for g in date_block.get("games", []):
            home = g.get("teams", {}).get("home", {}).get("team", {}).get("name", "")
            away = g.get("teams", {}).get("away", {}).get("team", {}).get("name", "")
            key = f"{home}|{away}"
            pairs[key] = {
                "home": home,
                "away": away,
                "home_score": g.get("teams", {}).get("home", {}).get("score"),
                "away_score": g.get("teams", {}).get("away", {}).get("score"),
                "detailed_state": g.get("status", {}).get("detailedState"),
            }
    return pairs


def normalize_name(name: str) -> str:
    """統一球隊名稱以容許些微差異"""
    return name.replace("á", "a").replace("é", "e").strip()


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "2026-06-19"
    # target 是台北日期；DB match_date = target - 1 day
    us_date = (date.fromisoformat(target) - timedelta(days=1)).isoformat()
    print(f"=== MLB match-date audit: 台北 {target} (美東 {us_date}) ===\n")

    print("Step 1: 從雲端 API 拉 DB 紀錄（台北日期）…")
    cloud_games = fetch_cloud_mlb_games(target)
    print(f"  DB records on 台北 {target} (DB match_date={us_date}): {len(cloud_games)}")

    print("Step 2: 從 MLB Stats API 拉官方 schedule（美東日期）…")
    api_pairs = fetch_mlb_api_schedule(us_date)
    print(f"  MLB API records on 美東 {us_date}: {len(api_pairs)}\n")

    # 比較
    cloud_pairs = {f"{normalize_name(g['home_team'])}|{normalize_name(g['away_team'])}": g for g in cloud_games}

    issues = []

    # 1. DB 裡有但 API 沒有的 (可能不存在)
    for key, cg in cloud_pairs.items():
        if key not in api_pairs:
            issues.append({
                "type": "PHANTOM_MATCH",
                "severity": "HIGH",
                "db_game_id": cg.get("game_id"),
                "matchup": f"{cg['away_team']} @ {cg['home_team']}",
                "db_status": cg.get("status"),
                "db_score": f"{cg.get('home_team_score')}-{cg.get('away_team_score')}",
                "note": "DB 記錄在 MLB 官方 schedule 中找不到",
            })

    # 2. DB 裡的比對與 API 不同 (比分錯誤或狀態錯誤)
    for key, cg in cloud_pairs.items():
        if key in api_pairs:
            api = api_pairs[key]
            db_h = cg.get("home_team_score")
            db_a = cg.get("away_team_score")
            api_h = api["home_score"]
            api_a = api["away_score"]

            if db_h is not None and api_h is not None:
                if int(db_h) != int(api_h) or int(db_a) != int(api_a):
                    issues.append({
                        "type": "SCORE_MISMATCH",
                        "severity": "HIGH",
                        "db_game_id": cg.get("game_id"),
                        "matchup": f"{cg['away_team']} @ {cg['home_team']}",
                        "db_score": f"{db_h}-{db_a}",
                        "api_score": f"{api_h}-{api_a}",
                    })

            if cg.get("status") == "FINAL" and api["detailed_state"] != "Final":
                issues.append({
                    "type": "STATUS_MISMATCH",
                    "severity": "MEDIUM",
                    "db_game_id": cg.get("game_id"),
                    "matchup": f"{cg['away_team']} @ {cg['home_team']}",
                    "db_status": cg.get("status"),
                    "api_status": api["detailed_state"],
                })

    # 報告
    print("=" * 70)
    print(f"AUDIT REPORT — {target}")
    print("=" * 70)
    print(f"DB records: {len(cloud_games)}")
    print(f"MLB API records: {len(api_pairs)}")
    print(f"Issues found: {len(issues)}\n")

    if not issues:
        print("✅ No issues found.")
        return

    by_type = defaultdict(list)
    for i in issues:
        by_type[i["type"]].append(i)

    for itype, items in by_type.items():
        print(f"\n--- {itype} ({len(items)}) ---")
        for i in items:
            print(json.dumps(i, ensure_ascii=False))

    # 摘要
    high = sum(1 for i in issues if i.get("severity") == "HIGH")
    print(f"\n摘要: HIGH severity = {high}, MEDIUM = {len(issues) - high}")


if __name__ == "__main__":
    main()
