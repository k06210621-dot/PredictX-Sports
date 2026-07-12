#!/usr/bin/env python3
"""
one_time_register_wnba_teams.py
===============================
一次性腳本：在 Railway PostgreSQL 註冊 WNBA 聯盟 + 15 支球隊
執行方式：railway run python analysis/one_time_register_wnba_teams.py
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor

# WNBA 15 支球隊（2026 賽季，含擴編隊伍）
WNBA_TEAMS = [
    ("Atlanta Dream", "ATL", "亞特蘭大夢想"),
    ("Chicago Sky", "CHI", "芝加哥天空"),
    ("Connecticut Sun", "CON", "康乃狄克太陽"),
    ("Dallas Wings", "DAL", "達拉斯飛翼"),
    ("Golden State Valkyries", "GSV", "金洲女武神"),
    ("Indiana Fever", "IND", "印第安納狂熱"),
    ("Las Vegas Aces", "LVA", "拉斯維加斯王牌"),
    ("Los Angeles Sparks", "LAS", "洛杉磯火花"),
    ("Minnesota Lynx", "MIN", "明尼蘇達山貓"),
    ("New York Liberty", "NYL", "紐約自由人"),
    ("Phoenix Mercury", "PHX", "鳳凰城水星"),
    ("Portland Fire", "POR", "波特蘭火焰"),
    ("Seattle Storm", "SEA", "西雅圖風暴"),
    ("Toronto Tempo", "TOR", "多倫多節奏"),
    ("Washington Mystics", "WAS", "華盛頓神秘人"),
]

def main():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("❌ DATABASE_URL 未設定")
        return 1

    conn = psycopg2.connect(db_url)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # 1. 註冊 WNBA 聯盟（如果不存在）
    cur.execute("SELECT league_id FROM predictx.leagues WHERE code = 'WNBA'")
    row = cur.fetchone()
    if row:
        league_id = row['league_id']
        print(f"✅ WNBA 聯盟已存在 (league_id={league_id})")
    else:
        cur.execute("""
            INSERT INTO predictx.leagues (code, name, sport_type, created_at, updated_at)
            VALUES ('WNBA', 'Women''s National Basketball Association', 'basketball', NOW(), NOW())
            RETURNING league_id
        """)
        league_id = cur.fetchone()['league_id']
        print(f"✅ WNBA 聯盟已建立 (league_id={league_id})")

    # 2. 註冊球隊
    inserted = 0
    skipped = 0
    for english_name, team_code, chinese_name in WNBA_TEAMS:
        cur.execute("SELECT team_id FROM predictx.teams WHERE english_name = %s AND league = 'WNBA'", (english_name,))
        existing = cur.fetchone()
        if existing:
            print(f"  ⏭ {english_name} 已存在 (team_id={existing['team_id']})")
            skipped += 1
            continue
        cur.execute("""
            INSERT INTO predictx.teams (league, english_name, chinese_name, team_code, abbreviation, created_at, updated_at)
            VALUES ('WNBA', %s, %s, %s, %s, NOW(), NOW())
            RETURNING team_id
        """, (english_name, chinese_name, team_code, team_code))
        team_id = cur.fetchone()['team_id']
        print(f"  ✅ {english_name} → team_id={team_id}")
        inserted += 1

    conn.commit()
    cur.close()
    conn.close()

    print(f"\n=== 完成 ===")
    print(f"  聯盟: WNBA (league_id={league_id})")
    print(f"  新增球隊: {inserted}")
    print(f"  已存在跳過: {skipped}")
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())