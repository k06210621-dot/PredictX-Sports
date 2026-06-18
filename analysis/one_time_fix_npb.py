#!/usr/bin/env python3
"""
一次性修正 NPB 6/16 比分 + 觸發結算
用法：在 Railway Shell 執行：
    python analysis/one_time_fix_npb.py
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import psycopg2
from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    print("❌ DATABASE_URL 環境變數未設定")
    sys.exit(1)

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

# 1. 更新 NPB 6/16 兩場比分
print("=== 更新 NPB 6/16 比分 ===")

cur.execute("""
    UPDATE predictx.games 
    SET home_team_score = 0, away_team_score = 1, status = 'FINAL'
    WHERE match_date = '2026-06-16'
      AND home_team_id = (SELECT team_id FROM predictx.teams WHERE english_name = 'Hanshin Tigers')
      AND away_team_id = (SELECT team_id FROM predictx.teams WHERE english_name = 'Saitama Seibu Lions')
""")
print(f"  Hanshin vs Seibu (0-1): {cur.rowcount} 行更新")

cur.execute("""
    UPDATE predictx.games 
    SET home_team_score = 0, away_team_score = 2, status = 'FINAL'
    WHERE match_date = '2026-06-16'
      AND home_team_id = (SELECT team_id FROM predictx.teams WHERE english_name = 'Hiroshima Toyo Carp')
      AND away_team_id = (SELECT team_id FROM predictx.teams WHERE english_name = 'Hokkaido Nippon-Ham Fighters')
""")
print(f"  Hiroshima vs Nippon-Ham (0-2): {cur.rowcount} 行更新")

conn.commit()

# 2. 確認更新資料
cur.execute("""
    SELECT g.match_date, ht.english_name, at.english_name, g.home_team_score, g.away_team_score, g.status
    FROM predictx.games g
    JOIN predictx.teams ht ON g.home_team_id = ht.team_id
    JOIN predictx.teams at ON g.away_team_id = at.team_id
    WHERE g.match_date = '2026-06-16' AND (ht.league = 'NPB' OR at.league = 'NPB')
    ORDER BY g.match_date
""")
rows = cur.fetchall()
print(f"\n=== NPB 6/16 確認: {len(rows)} 場 ===")
for r in rows:
    print(f"  {r[0]}  {r[1]} vs {r[2]}: {r[3]}-{r[4]}  [{r[5]}]")

# 3. 觸發結算
print("\n=== 觸發結算 ===")
from settlement_engine import SettlementEngine
settler = SettlementEngine(conn=conn)
count = settler.settle_games(re_settle_all=True)
print(f"💰 結算完成: {count} 場")

cur.close()
conn.close()
print("✅ 全部完成")
