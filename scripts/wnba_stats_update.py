#!/usr/bin/env python3
"""
[知識沉澱] WNBA 球員資料自動化更新

需求:
  - 從 stats.wnba.com 抓取球員進階數據（含真實姓名、球隊、進階統計）
  - 每週更新一次（或賽季期間每日更新）
  - 儲存為 JSON 供 wnba_data_fetcher.get_top_players() 使用

實作步驟:
  1. 使用 Hermes browser_navigate 到 stats.wnba.com/players/advanced/
  2. 使用 browser_console 執行 JavaScript 抓取表格
  3. 解析球員數據並按球隊分組
  4. 保存到 /Users/jero/PredictX-Sports-backend/data/wnba_players_2026.json
  5. 修改 wnba_data_fetcher.get_top_players() 優先讀取 JSON 數據

使用方式:
  在 Hermes 對話中執行:
  ```
  browser_navigate(url="https://stats.wnba.com/players/advanced/?sort=PIE&dir=-1")
  browser_console(expression="EXTRACT_JS_CODE")
  # 解析結果並保存
  ```

或建立 cron job 自動更新:
  cronjob action=create schedule="every 7d" script="wnba_stats_update.py"
"""

import json
from pathlib import Path
from datetime import datetime

DATA_FILE = Path("/Users/jero/PredictX-Sports-backend/data/wnba_players_2026.json")

def load_wnba_players():
    """從 JSON 檔案載入 WNBA 球員數據"""
    if not DATA_FILE.exists():
        return {}
    
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_wnba_players(players_by_team):
    """保存球員數據到 JSON 檔案"""
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    data = {
        'last_updated': datetime.now().isoformat(),
        'season': 2026,
        'source': 'stats.wnba.com',
        'teams': players_by_team
    }
    
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"✓ Saved {len(players_by_team)} teams to {DATA_FILE}")

if __name__ == '__main__':
    # 範例：載入並顯示數據
    data = load_wnba_players()
    if data:
        print(f"Last updated: {data.get('last_updated', 'Unknown')}")
        print(f"Teams: {list(data.get('teams', {}).keys())}")
        
        # 顯示某個球隊的前 5 名球員
        for team_name, players in list(data.get('teams', {}).items())[:1]:
            print(f"\n{team_name} Top 5:")
            for i, p in enumerate(players[:5], 1):
                print(f"  {i}. {p['name']}: PIE={p.get('pie', 0):.1f}, TS%={p.get('ts_pct', 0):.3f}")
    else:
        print("No data yet. Run browser scraper first.")