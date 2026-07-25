#!/usr/bin/env python3
import json, psycopg2
from psycopg2.extras import RealDictCursor

with open('/tmp/railway_pg.json') as f:
    pg = json.load(f)
DB_URL = f"postgresql://postgres:{pg['PGPASSWORD']}@thomas.proxy.rlwy.net:49887/railway"

conn = psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)
cur = conn.cursor(cursor_factory=RealDictCursor)

GID = '30990d93-e7c4-4cf7-a901-538420464e73'
cur.execute("""
    SELECT g.match_date, ht.english_name home, ta.english_name away,
           ga.analysis_data, ga.updated_at
    FROM predictx.game_analysis ga
    JOIN predictx.games g ON ga.game_id = g.game_id
    JOIN predictx.teams ht ON g.home_team_id = ht.team_id
    JOIN predictx.teams ta ON g.away_team_id = ta.team_id
    WHERE ga.game_id = %s::uuid
""", (GID,))
row = cur.fetchone()
if not row:
    print("未找到該場分析記錄")
else:
    ad = row['analysis_data'] or {}
    summary = ad.get('summary', '') or ''
    print(f"場次: {row['home']} vs {row['away']} ({row['match_date']})")
    print(f"updated_at: {row['updated_at']}")
    print(f"主隊勝率: {ad.get('home_win_probability')}")
    print(f"客隊勝率: {ad.get('away_win_probability')}")
    print(f"信心度: {ad.get('confidence')}")
    print(f"預測比分: {ad.get('predicted_score')}")
    print(f"summary 字數: {len(summary)}")
    print(f"model_used: {ad.get('model_used', 'N/A')}")
    # 關鍵判斷：是否走 fallback computed（模板化、無細節）
    print(f"\n--- 判斷 ---")
    print(f"含 [傷兵校正]: {'是' if '[傷兵校正]' in summary else '否'}")
    print(f"含 [投手參數校正]/[投手近況校正]: {'是' if ('[投手參數校正]' in summary or '[投手近況校正]' in summary) else '否'}")
    print(f"summary 是否為短模板 (<250字, fallback 特徵): {'是' if len(summary) < 250 else '否'}")
    print(f"\n--- summary 前 300 字 ---")
    print(summary[:300])

cur.close(); conn.close()
