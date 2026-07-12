#!/usr/bin/env python3
"""
backfill_wnba_history.py
========================
一次性腳本：backfill 過去 14 天 WNBA 賽事（含最終比分）
用於測試 AI 分析與驗證成功率
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'analysis'))

import logging
logging.basicConfig(level=logging.INFO, format='%(message)s')

from datetime import datetime, timedelta
from ingest.wnba import WNBAIngester

def main():
    ingester = WNBAIngester()
    today = datetime.now()
    total_inserted = 0
    total_skipped = 0

    print("=== WNBA 14 天歷史 backfill ===\n")

    for d in range(1, 15):
        target = (today - timedelta(days=d)).strftime("%Y-%m-%d")
        try:
            games = ingester.fetch_games(target)
            final_games = [g for g in games if g.get('status') == 'FINAL']
            if games:
                print(f"{target}: {len(games)} 場 ({len(final_games)} FINAL)")
                for g in final_games:
                    print(f"  {g['home_team']} vs {g['away_team']} {g['home_team_score']}-{g['away_team_score']}")
                # 上傳到資料庫
                if final_games:
                    ok = ingester.upload(final_games)
                    if ok:
                        total_inserted += len(final_games)
                print()
            else:
                print(f"{target}: 0 場 (休賽日)\n")
        except Exception as e:
            print(f"❌ {target} 失敗: {e}\n")

    print(f"=== 完成 ===")
    print(f"  總共上傳: {total_inserted} 場 FINAL 賽事")
    return 0

if __name__ == "__main__":
    sys.exit(main())