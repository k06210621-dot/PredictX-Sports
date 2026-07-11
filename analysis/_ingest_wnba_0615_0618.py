#!/usr/bin/env python3
"""
補抓 6/15-6/18 WNBA 賽程+比分進 Railway 生產 DB。
從 ESPN API 抓取，對应 predictx.teams 的 english_name 寫入 predictx.games。
"""
import requests, json, psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

DB = dict(host='thomas.proxy.rlwy.net', port=49887, user='postgres',
          password='REDACTED', dbname='railway')

ESPN_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/scoreboard"

def main():
    conn = psycopg2.connect(cursor_factory=RealDictCursor, **DB)
    cur = conn.cursor()

    # 先撈 WNBA team name → team_id mapping
    cur.execute("SELECT team_id, english_name FROM predictx.teams WHERE league='WNBA'")
    team_map = {row['english_name']: row['team_id'] for row in cur.fetchall()}

    dates = ['20260615','20260616','20260617','20260618']
    inserted = 0
    skipped = 0

    for d in dates:
        match_date = f"{d[:4]}-{d[4:6]}-{d[6:]}"
        resp = requests.get(f"{ESPN_URL}?dates={d}", timeout=20)
        data = resp.json()
        events = data.get('events', [])
        print(f"\n{match_date}: {len(events)} games from ESPN")

        for ev in events:
            comps = ev.get('competitions', [{}])[0].get('competitors', [])
            home_name = away_name = None
            home_score = away_score = None
            for c in comps:
                name = c.get('team', {}).get('displayName', '')
                score = c.get('score')
                if c.get('homeAway') == 'home':
                    home_name = name
                    home_score = float(score) if score else None
                else:
                    away_name = name
                    away_score = float(score) if score else None

            if not home_name or not away_name:
                print(f"  [SKIP] missing team name")
                skipped += 1
                continue

            home_id = team_map.get(home_name)
            away_id = team_map.get(away_name)
            if not home_id or not away_id:
                print(f"  [SKIP] team not in DB: {home_name} or {away_name}")
                skipped += 1
                continue

            # 檢查是否已存在（同日同對戰）
            cur.execute("""
                SELECT game_id FROM predictx.games
                WHERE match_date = %s AND home_team_id = %s AND away_team_id = %s
            """, (match_date, home_id, away_id))
            existing = cur.fetchone()
            if existing:
                print(f"  [SKIP] {home_name} vs {away_name} on {match_date} already exists")
                skipped += 1
                continue

            # 寫入
            cur.execute("""
                INSERT INTO predictx.games (season, match_date, status, home_team_id, away_team_id,
                                           home_team_score, away_team_score)
                VALUES (2026, %s, 'FINAL', %s, %s, %s, %s)
                RETURNING game_id::text
            """, (match_date, home_id, away_id, home_score, away_score))
            gid = cur.fetchone()['game_id']
            conn.commit()
            print(f"  [INSERT] {gid[:8]} {home_name} {home_score}-{away_score} {away_name}")
            inserted += 1

    cur.close()
    conn.close()
    print(f"\n=== DONE inserted={inserted} skipped={skipped} ===")

if __name__ == '__main__':
    main()
