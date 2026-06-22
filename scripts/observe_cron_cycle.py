#!/usr/bin/env python3
"""
scripts/observe_cron_cycle.py
==============================
在 PredictX cron 觸發後（T+30 分鐘）自動驗證整個 pipeline 是否正常運作。

驗證項目：
1. health check
2. 各聯賽賽事筆數（cron 跑前 vs 跑後）
3. 驗證率變化
4. MLB 抽樣 audit（match_date 錯配 + 比分正確性）
"""
import json
import subprocess
import sys
import urllib.request
from datetime import datetime


def http_get_json(url, timeout=15):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read())


def section(title):
    print()
    print("=" * 70)
    print(f" {title}")
    print("=" * 70)


def check_health():
    section("1. Health Check")
    try:
        h = http_get_json("https://predictx-sports-production.up.railway.app/health")
        print(f"  status: {h.get('status')}")
        print(f"  database: {h.get('checks', {}).get('database')}")
        print(f"  env_vars: {h.get('checks', {}).get('env_vars')}")
        print(f"  thesportsdb_key: {h.get('checks', {}).get('thesportsdb_key')}")
        print(f"  server_time: {h.get('timestamp')}")
    except Exception as e:
        print(f"  ERROR: {e}")


def check_games_counts():
    section("2. 各聯賽賽事筆數（6/22 ~ 6/26）")
    for league in ["MLB", "NPB", "CPBL", "NBA"]:
        for d in ["2026-06-22", "2026-06-23", "2026-06-24", "2026-06-25", "2026-06-26"]:
            try:
                data = http_get_json(
                    f"https://predictx-sports-production.up.railway.app/api/games?league={league}&date={d}"
                )
                games = [g for g in data if g.get("match_date") == d]
                with_score = sum(1 for g in games if g.get("home_team_score") is not None)
                with_analysis = sum(1 for g in games if g.get("ai_predicted_score") is not None)
                print(f"  {league} {d}: total={len(games):>2}, score={with_score:>2}, analyzed={with_analysis:>2}")
            except Exception as e:
                print(f"  {league} {d}: ERROR {e}")


def check_settlement():
    section("3. Settlement 驗證率（總覽）")
    try:
        overall = http_get_json(
            "https://predictx-sports-production.up.railway.app/analytics/overall"
        )
        for r in overall:
            print(f"  {r.get('league'):<6}: analyzed={r.get('total_analyzed'):>4}, hits={r.get('total_hits'):>4}, rate={r.get('hit_rate', 0)*100:>5.1f}%")
    except Exception as e:
        print(f"  ERROR: {e}")


def run_audit(date_str: str):
    section(f"4. MLB audit {date_str}")
    try:
        result = subprocess.run(
            ["python3", "scripts/audit_mlb_match_dates.py", date_str],
            cwd="/Users/jero/PredictX Sports",
            capture_output=True,
            text=True,
            timeout=60,
        )
        output = result.stdout
        # 抓摘要部分
        lines = output.splitlines()
        for i, line in enumerate(lines):
            if line.startswith("AUDIT REPORT") or "DB records:" in line or "Issues found:" in line or "PHANTOM_MATCH" in line or "SCORE_MISMATCH" in line or "STATUS_MISMATCH" in line or line.startswith("✅") or "HIGH severity" in line:
                print(f"  {line[:200]}")
    except Exception as e:
        print(f"  ERROR: {e}")


def main():
    print(f"Observation started at {datetime.utcnow().isoformat()}Z")
    print(f"(Taipei: {(datetime.utcnow()).isoformat()}+08:00 approx)")

    check_health()
    check_games_counts()
    check_settlement()
    run_audit("2026-06-22")
    run_audit("2026-06-23")
    run_audit("2026-06-24")

    section("END")
    print(f"Observation finished at {datetime.utcnow().isoformat()}Z")


if __name__ == "__main__":
    main()
