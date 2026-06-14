"""
PredictX Sports — 全面足球資料源分析
針對 FIFA 目前 312 場僅有排程無比分的情況，尋找可用的即時資料源
"""
import requests

session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"})

print("=== 資料源分析報告 ===\n")

# 1. fbref.com — Cloudflare 封鎖，無法使用
print("1. fbref.com: ❌ Cloudflare 防護，無法程式化存取")

# 2. ESPN — 可使用但 FIFA 世界盃非賽季
print("2. ESPN API: ✅ 可存取但資料有限")
print("   FIFA World Cup: 只有 2 場排程賽事（非世界盃年份無實際比賽）")
print("   實際 FIFA 賽事在 2026年6月才開始")

# 3. 檢查 FIFA 資料實際狀況
print(f"\n3. 本地資料庫 FIFA 狀況:")
import psycopg2
from psycopg2.extras import RealDictCursor
conn = psycopg2.connect(dbname="sports_db", user="jero", host="localhost")
cur = conn.cursor(cursor_factory=RealDictCursor)
cur.execute("""
    SELECT COUNT(*) as total,
           COUNT(*) FILTER (WHERE status IN ('final','FINAL','finished')) as completed,
           COUNT(*) FILTER (WHERE status = 'SCHEDULED') as scheduled
    FROM predictx.games g
    JOIN predictx.teams t ON g.home_team_id = t.team_id
    WHERE t.league = 'FIFA'
""")
row = cur.fetchone()
print(f"   總場次: {row['total']}")
print(f"   已完賽: {row['completed']}")
print(f"   排程中: {row['scheduled']}")
print(f"   結論: 所有 312 場都是模擬排程資料，無實際比分")

cur.close()
conn.close()

# 4. 替代方案
print(f"\n4. 可行的 FIFA 資料源方案 (無 API Key):")
alternatives = [
    ("ESPN API (免費)", "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard", 
     "✅ 可用", "提供 FIFA 賽程與即時比分，但 2026世界盃在6月才開始，目前資料極少"),
    ("TheSportsDB (免費層)", "https://www.thesportsdb.com/free_sports_api",
     "✅ 可用", "提供 leagues/teams/players 資料庫，但歷史比分需付費"),
    ("ESPN 五大聯賽", "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/scoreboard",
     "✅ 可用", "英超/西甲/德甲/義甲/歐冠即時比分（目前為休賽季）"),
]

for name, url, status, note in alternatives:
    try:
        resp = session.get(url, timeout=10)
        actual_status = f"HTTP {resp.status_code}"
    except:
        actual_status = "Connection error"
    print(f"   {name}")
    print(f"    端點: {url}")
    print(f"    狀態: {status} ({actual_status})")
    print(f"    說明: {note}")
    print()

# 5. 最終建議
print("=== 最終建議 ===")
print("""
針對 FIFA 資料現狀，有兩個方向：

A) 等待 2026世界盃開賽（2026年6月11日）
   屆時 ESPN API 將有完整即時比分、小組排名、淘汰賽資料
   可直接整合至 AnalysisEngine

B) 加入其他足球聯賽
   雖然目前是休賽季，但 ESPN 支援:
   - English Premier League (eng.1)
   - Spanish La Liga (esp.1)  
   - German Bundesliga (ger.1)
   - Italian Serie A (ita.1)
   下季約 2026年8月開始，屆時可自動取得即時資料

目前建議：專注於 MLB/NBA/NPB/CPBL 四個已有即時資料的聯賽，
等 2026 FIFA World Cup 開賽後再整合 FIFA。
""")