#!/usr/bin/env python3
"""
NBA 季前賽回補腳本（2026-10-09）
===============================
目的：把美東 10/03 ~ 10/16 的 NBA 賽程（含季前賽 preseason）補進 production DB。

背景：
- 2026-10-01 加的 season.type=1 過濾，讓季前賽全部抓不到（DB 0 場）
- 本日移除過濾後，補齊過濾期間漏掉的歷史場次 + 未來場次
- DB match_date 存「美東日期」，App 顯示端 +1 天

安全閘：
- 只寫入成功解析隊名的場次（insert_games 會自動 skip 無法解析的隊名）
- 印出逐日抓取數與上傳結果供人工核對
"""
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ingest.nba import NBAIngester  # noqa: E402

START = date(2026, 10, 3)
END = date(2026, 10, 16)

ing = NBAIngester()
all_games = []
day = START
while day <= END:
    ds = day.strftime("%Y-%m-%d")
    try:
        g = ing.fetch_games(ds)
        print(f"  {ds} → {len(g)} 場", flush=True)
        all_games.extend(g)
    except Exception as e:
        print(f"  {ds} → FAIL: {e}", flush=True)
    day += timedelta(days=1)

print(f"\n總計抓取: {len(all_games)} 場")
preseason = sum(1 for g in all_games)
print(f"準備上傳: {preseason} 場")

# 逐場列出（人工核對）
print("\n--- 明細 ---")
for g in sorted(all_games, key=lambda z: (z["match_date"], z["away_team"])):
    print(f"  {g['match_date']} | {g['away_team']} @ {g['home_team']} | {g['status']} "
          f"| {g.get('away_team_score')}-{g.get('home_team_score')}")

print("\n--- 上傳 ---")
ok = ing.upload(all_games)
print("upload_ok:", ok)
if hasattr(ing, "close"):
    ing.close()
