#!/usr/bin/env python3
"""
ingest/nba_players.py
=====================
NBA 球員資料匯入腳本
從 ESPN site.api 抓 30 隊 × 15-17 人 = ~480 球員
"""
import os
import sys
import json
import time
import logging
import urllib.request

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

ESPN_TEAMS_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams"
ESPN_ROSTER_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{team_id}/roster"
LEAGUE_CODE = "NBA"

ESPN_TO_DB_ABBREV = {}  # 將用 english_name matching


def fetch_json(url: str, timeout: int = 30) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "PredictX/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_teams() -> list:
    data = fetch_json(ESPN_TEAMS_URL)
    teams = data.get("sports", [{}])[0].get("leagues", [{}])[0].get("teams", [])
    return [
        {
            "espn_id": t["team"]["id"],
            "name": t["team"].get("displayName", ""),
            "abbrev": t["team"].get("abbreviation", ""),
        }
        for t in teams
    ]


def fetch_roster(espn_team_id: str) -> list:
    data = fetch_json(ESPN_ROSTER_URL.format(team_id=espn_team_id))
    return data.get("athletes", [])


def map_team_id(espn_name: str, cur) -> str:
    cur.execute("SELECT team_id, english_name FROM predictx.teams WHERE league = %s", (LEAGUE_CODE,))
    rows = cur.fetchall()
    espn_l = espn_name.lower()
    for r in rows:
        en_l = r["english_name"].lower()
        if espn_l == en_l:
            return r["team_id"]
    for r in rows:
        en_l = r["english_name"].lower()
        # 移除城市名差異，例如 "Los Angeles Lakers" vs "LA Lakers"
        for kw in en_l.split():
            if kw and kw in espn_l:
                return r["team_id"]
    return None


def upsert_player(cur, external_id: str, name: str, position: str, jersey) -> str:
    cur.execute("SELECT player_id FROM predictx.players WHERE external_id = %s", (external_id,))
    if cur.fetchone():
        return cur.fetchone()["player_id"]
    cur.execute(
        """
        INSERT INTO predictx.players (external_id, player_name, position, jersey_number, created_at, updated_at)
        VALUES (%s, %s, %s, %s, NOW(), NOW())
        RETURNING player_id
        """,
        (external_id, name, position, jersey),
    )
    return cur.fetchone()["player_id"]


def upsert_player_team(cur, player_id: str, team_id: str) -> bool:
    cur.execute(
        "SELECT id FROM predictx.player_teams WHERE player_id = %s::uuid AND team_id = %s::uuid",
        (player_id, team_id),
    )
    if cur.fetchone():
        return False
    cur.execute(
        "INSERT INTO predictx.player_teams (player_id, team_id, is_active) VALUES (%s::uuid, %s::uuid, true)",
        (player_id, team_id),
    )
    return True


def run(dry_run: bool = False) -> dict:
    result = {"teams_processed": 0, "players_inserted": 0, "errors": []}
    if dry_run:
        teams = get_teams()
        logger.info(f"NBA 球隊數: {len(teams)}")
        total = 0
        for t in teams[:3]:
            r = fetch_roster(t["espn_id"])
            logger.info(f"  {t['name']:30s}  roster={len(r)}")
            total += len(r)
        return result

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL 未設定")
    import psycopg2, psycopg2.extras
    conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()
    teams = get_teams()
    logger.info(f"開始匯入 {len(teams)} 隊 NBA 球員")
    for t in teams:
        try:
            roster = fetch_roster(t["espn_id"])
            team_id = map_team_id(t["name"], cur)
            if not team_id:
                result["errors"].append(f"找不到球隊 {t['name']}")
                continue
            inserted = 0
            for a in roster:
                espn_id = a.get("id")
                full_name = a.get("fullName") or a.get("displayName")
                pos_obj = a.get("position", {})
                position = pos_obj.get("abbreviation", "") if isinstance(pos_obj, dict) else str(pos_obj)
                jersey = a.get("jersey", "")
                try:
                    jersey_int = int(jersey) if jersey else None
                except (ValueError, TypeError):
                    jersey_int = None
                if not espn_id or not full_name:
                    continue
                pid = upsert_player(cur, str(espn_id), full_name, position, jersey_int)
                if upsert_player_team(cur, pid, team_id):
                    inserted += 1
            conn.commit()
            result["teams_processed"] += 1
            result["players_inserted"] += inserted
            logger.info(f"  ✓ {t['name']:30s}  players_new={inserted}/{len(roster)}")
        except Exception as e:
            result["errors"].append(f"{t['name']}: {e}")
            conn.rollback()
    cur.close()
    conn.close()
    return result


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    out = run(dry_run=args.dry_run)
    print("\n=== 結果 ===")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    sys.exit(0 if not out.get("errors") else 1)
