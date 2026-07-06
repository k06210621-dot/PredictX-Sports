#!/usr/bin/env python3
"""
One-time script: 匯入 npb_players.json 到 predictx.players + predictx.player_teams

用法：
  python3 import_npb_players.py          # 本地 DB
  python3 import_npb_players.py --railway # Railway (用 DATABASE_URL env)
"""
import json
import os
import sys
import uuid
import psycopg2

# team_code → DB team_id 對照
TEAM_CODE_TO_DB = {
    'G': 'Yomiuri Giants',
    'T': 'Hanshin Tigers',
    'D': 'Chunichi Dragons',
    'YB': 'Yokohama DeNA BayStars',
    'C': 'Hiroshima Toyo Carp',
    'S': 'Tokyo Yakult Swallows',
    'H': 'Fukuoka SoftBank Hawks',
    'L': 'Saitama Seibu Lions',
    'M': 'Chiba Lotte Marines',
    'E': 'Tohoku Rakuten Golden Eagles',
    'B': 'ORIX Buffaloes',
    'F': 'Hokkaido Nippon-Ham Fighters',
}

# kind → position
KIND_TO_POS = {
    'pitcher': 'P',
    'batter': 'IF/OF',
}

def get_db_connection():
    db_url = os.getenv('DATABASE_URL')
    if db_url:
        if db_url.startswith('postgres://'):
            db_url = db_url.replace('postgres://', 'postgresql://', 1)
        return psycopg2.connect(db_url)
    else:
        return psycopg2.connect(
            dbname='sports_db', user='jero', password='', host='localhost', port=5432
        )

def main():
    conn = get_db_connection()
    cur = conn.cursor()

    # 1. 取得 NPB team UUIDs
    cur.execute("""
        SELECT english_name, team_id FROM predictx.teams
        WHERE league = 'NPB' AND english_name NOT LIKE '%Deprecated%'
    """)
    team_name_to_id = {row[0]: row[1] for row in cur.fetchall()}
    print(f"NPB teams in DB: {len(team_name_to_id)}")

    # 2. 讀取 npb_players.json
    script_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(script_dir, 'npb_players.json')
    with open(json_path) as f:
        players = json.load(f)
    print(f"Players in JSON: {len(players)}")

    # 3. 檢查已存在的 NPB players（避免重複匯入）
    cur.execute("""
        SELECT COUNT(*) FROM predictx.players p
        JOIN predictx.player_teams pt ON p.player_id = pt.player_id
        JOIN predictx.teams t ON pt.team_id = t.team_id
        WHERE t.league = 'NPB' AND pt.is_active = true
    """)
    existing_row = cur.fetchone()
    existing = existing_row[0] if existing_row else 0
    if existing > 0:
        print(f"Already {existing} NPB players in DB. Skipping import.")
        cur.close()
        conn.close()
        return

    # 4. 匯入
    inserted_players = 0
    inserted_teams = 0
    skipped = 0

    for p in players:
        team_code = p.get('team_code')
        if not team_code:
            skipped += 1
            continue

        team_name = TEAM_CODE_TO_DB.get(team_code)
        if not team_name:
            print(f"  ⚠ Unknown team_code: {team_code}")
            skipped += 1
            continue

        team_id = team_name_to_id.get(team_name)
        if not team_id:
            print(f"  ⚠ Team not in DB: {team_name}")
            skipped += 1
            continue

        name_en = p.get('name_en', 'Unknown')
        kind = p.get('kind', 'batter')
        position = KIND_TO_POS.get(kind, 'IF/OF')

        player_id = str(uuid.uuid4())

        try:
            cur.execute("""
                INSERT INTO predictx.players (player_id, player_name, position)
                VALUES (%s, %s, %s)
            """, (player_id, name_en, position))
            inserted_players += 1

            cur.execute("""
                INSERT INTO predictx.player_teams (id, player_id, team_id, is_active)
                VALUES (%s, %s, %s, true)
            """, (str(uuid.uuid4()), player_id, team_id))
            inserted_teams += 1
        except Exception as e:
            print(f"  ⚠ Insert error for {name_en}: {e}")
            conn.rollback()
            skipped += 1

    conn.commit()
    print(f"\nDone: {inserted_players} players, {inserted_teams} team links, {skipped} skipped")

    # 5. 驗證
    cur.execute("""
        SELECT t.english_name, COUNT(p.player_id)
        FROM predictx.teams t
        JOIN predictx.player_teams pt ON t.team_id = pt.team_id
        JOIN predictx.players p ON pt.player_id = p.player_id
        WHERE t.league = 'NPB' AND pt.is_active = true
        GROUP BY t.english_name
        ORDER BY COUNT(p.player_id) DESC
    """)
    print("\nVerification:")
    for row in cur.fetchall():
        print(f"  {row[0]}: {row[1]} players")

    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
