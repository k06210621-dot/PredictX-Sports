#!/usr/bin/env python3
"""
ingest/mlb_players.py
=====================
MLB 球員資料匯入腳本
從 MLB 官方 statsapi.mlb.com 抓取 30 隊 × ~26 人 = ~780 球員
"""
import os
import sys
import json
import time
import logging
import urllib.request

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

MLB_TEAMS_URL = "https://statsapi.mlb.com/api/v1/teams?sportId=1"
MLB_ROSTER_URL = "https://statsapi.mlb.com/api/v1/teams/{team_id}/roster?season={season}"
LEAGUE_CODE = "MLB"
SEASON = 2026


def fetch_json(url: str, timeout: int = 30) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "PredictX/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_teams() -> list:
    data = fetch_json(MLB_TEAMS_URL)
    return [{"mlb_id": t["id"], "name": t["name"], "abbrev": t.get("abbreviation", "")} for t in data.get("teams", [])]


def fetch_roster(mlb_team_id: int) -> list:
    data = fetch_json(MLB_ROSTER_URL.format(team_id=mlb_team_id, season=SEASON))
    return data.get("roster", [])


def map_team_id(mlb_team_name: str, cur) -> str:
    cur.execute(
        "SELECT team_id, english_name, abbreviation FROM predictx.teams WHERE league = %s",
        (LEAGUE_CODE,),
    )
    rows = cur.fetchall()
    # 優先用 mlb_team_name contains 對應 english_name
    for r in rows:
        en = r.get("english_name", "").lower()
        if mlb_team_name.lower() == en:
            return r["team_id"]
    for r in rows:
        en = r.get("english_name", "").lower()
        if mlb_team_name.lower() in en or en in mlb_team_name.lower():
            return r["team_id"]
    return None


def upsert_player(cur, external_id: str, name: str, position: str, jersey) -> str:
    cur.execute("SELECT player_id FROM predictx.players WHERE external_id = %s", (external_id,))
    row = cur.fetchone()
    if row:
        return row["player_id"]
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
        logger.info(f"MLB 球隊數: {len(teams)}")
        total = 0
        for t in teams[:3]:
            r = fetch_roster(t["mlb_id"])
            logger.info(f"  {t['name']:30s}  roster={len(r)}")
            total += len(r)
        logger.info(f"前 3 隊球員總數: {total}")
        return result

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL 未設定")
    import psycopg2, psycopg2.extras
    conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()
    teams = get_teams()
    logger.info(f"開始匯入 {len(teams)} 隊 MLB 球員")
    for t in teams:
        try:
            roster = fetch_roster(t["mlb_id"])
            team_id = map_team_id(t["name"], cur)
            if not team_id:
                result["errors"].append(f"找不到球隊 {t['name']}")
                continue
            inserted = 0
            for p in roster:
                person = p.get("person", {})
                pos = p.get("position", {})
                pid = upsert_player(
                    cur,
                    str(person.get("id")),
                    person.get("fullName"),
                    pos.get("abbreviation", ""),
                    p.get("jerseyNumber"),
                )
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
