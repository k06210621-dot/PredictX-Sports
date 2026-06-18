#!/usr/bin/env python3
"""
一鍵修復 NBA 6/14 狀態 + 清除重複資料
Railway Shell 執行： python analysis/one_time_fix_nba.py
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import psycopg2
from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    print("❌ DATABASE_URL 未設定")
    sys.exit(1)

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

# 1. 檢查 NBA 6/14 所有賽事
cur.execute("""
    SELECT g.game_id, g.match_date, ht.english_name, at.english_name,
           g.home_team_score, g.away_team_score, g.status
    FROM predictx.games g
    JOIN predictx.teams ht ON g.home_team_id = ht.team_id
    JOIN predictx.teams at ON g.away_team_id = at.team_id
    WHERE g.match_date = '2026-06-14' AND ht.league = 'NBA'
    ORDER BY g.game_id
""")
rows = cur.fetchall()
print(f"NBA 6/14 賽事總數: {len(rows)}")
for r in rows:
    print(f"  {r[0][:12]}...  {r[1]}  {r[2]} vs {r[3]}: {r[4]}-{r[5]}  [{r[6]}]")

# 2. 找出重複並刪除多餘 game_id（保留第一個）
cur.execute("""
    SELECT MIN(game_id) as keep_id
    FROM predictx.games g
    JOIN predictx.teams ht ON g.home_team_id = ht.team_id
    JOIN predictx.teams at ON g.away_team_id = at.team_id
    WHERE g.match_date = '2026-06-14' AND ht.league = 'NBA'
    GROUP BY ht.english_name, at.english_name
    HAVING COUNT(*) > 1
""")
duplicate_groups = cur.fetchall()
print(f"\n重複群組: {len(duplicate_groups)}")

for group in duplicate_groups:
    keep_id = group[0]
    # 刪除該對戰組合中除了 keep_id 以外的 game_id
    cur.execute("""
        DELETE FROM predictx.game_analysis ga
        WHERE ga.game_id IN (
            SELECT g.game_id FROM predictx.games g
            JOIN predictx.teams ht ON g.home_team_id = ht.team_id
            JOIN predictx.teams at ON g.away_team_id = at.team_id
            WHERE g.match_date = '2026-06-14'
              AND ht.league = 'NBA'
              AND g.game_id != %s
              AND ht.english_name = (
                  SELECT ht2.english_name FROM predictx.games g2
                  JOIN predictx.teams ht2 ON g2.home_team_id = ht2.team_id
                  WHERE g2.game_id = %s
              )
        )
    """, (keep_id, keep_id))
    print(f"  已刪除 game_analysis 關聯: {cur.rowcount} 筆")

    cur.execute("""
        DELETE FROM predictx.games g
        WHERE g.game_id IN (
            SELECT g2.game_id FROM predictx.games g2
            JOIN predictx.teams ht2 ON g2.home_team_id = ht2.team_id
            JOIN predictx.teams at2 ON g2.away_team_id = at2.team_id
            WHERE g2.match_date = '2026-06-14'
              AND ht2.league = 'NBA'
              AND g2.game_id != %s
              AND ht2.english_name = (
                  SELECT ht3.english_name FROM predictx.games g3
                  JOIN predictx.teams ht3 ON g3.home_team_id = ht3.team_id
                  WHERE g3.game_id = %s
              )
        )
    """, (keep_id, keep_id))
    print(f"  已刪除 games 重複: {cur.rowcount} 筆")

# 3. 更新保留的賽事 status = FINAL
cur.execute("""
    UPDATE predictx.games g
    SET status = 'FINAL'
    WHERE g.match_date = '2026-06-14'
      AND g.game_id IN (
          SELECT MIN(g2.game_id)
          FROM predictx.games g2
          JOIN predictx.teams ht2 ON g2.home_team_id = ht2.team_id
          WHERE ht2.league = 'NBA'
          AND g2.match_date = '2026-06-14'
          GROUP BY g2.home_team_id, g2.away_team_id
      )
""")
print(f"\n✅ 更新 status = FINAL: {cur.rowcount} 行")
conn.commit()

# 4. 最終確認
cur.execute("""
    SELECT g.game_id, g.match_date, ht.english_name, at.english_name,
           g.home_team_score, g.away_team_score, g.status
    FROM predictx.games g
    JOIN predictx.teams ht ON g.home_team_id = ht.team_id
    JOIN predictx.teams at ON g.away_team_id = at.team_id
    WHERE g.match_date = '2026-06-14' AND ht.league = 'NBA'
    ORDER BY g.game_id
""")
rows = cur.fetchall()
print(f"\n📋 最終確認 — NBA 6/14: {len(rows)} 場")
for r in rows:
    print(f"  {r[0][:12]}...  {r[1]}  {r[2]} vs {r[3]}: {r[4]}-{r[5]}  [{r[6]}]")

cur.close()
conn.close()
print("\n✅ 完成")
