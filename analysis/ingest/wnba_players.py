#!/usr/bin/env python3
"""
ingest/wnba_players.py
======================
WNBA 球員資料匯入腳本
從 ESPN 公開 API 抓取 15 隊 × 12-15 人 = ~200 球員 + per-game stats
寫入 predictx.players / predictx.player_teams

資料源：
  1. https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/teams
     → 15 支球隊 + ESPN team_id
  2. https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/teams/{id}/roster
     → 球員名單（12-15 人/隊）
  3. https://site.web.api.espn.com/apis/common/v3/sports/basketball/wnba/athletes/{player_id}
     → per-game stats（PPG, RPG, APG, SPG, BPG）

執行方式：
  DATABASE_URL=xxx python3 analysis/ingest/wnba_players.py --dry-run
  DATABASE_URL=xxx python3 analysis/ingest/wnba_players.py

Schema 對應：
  predictx.players.external_id  ←  ESPN player.id (字串)
  predictx.players.player_name  ←  ESPN player.fullName
  predictx.players.position     ←  ESPN player.position.abbreviation
  predictx.players.jersey_number ←  ESPN player.jersey
  predictx.player_teams         ←  多對多 (球員 ↔ 球隊)
"""
import os
import sys
import json
import time
import logging
import urllib.request

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

ESPN_TEAMS_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/teams"
ESPN_ROSTER_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/teams/{team_id}/roster"
ESPN_ATHLETE_URL = "https://site.web.api.espn.com/apis/common/v3/sports/basketball/wnba/athletes/{player_id}"

WNBA_LEAGUE_CODE = "WNBA"

# ESPN abbrev → DB abbrev (DB 存 3 字 ESPN 是 2-3 字)
ESPN_TO_DB_ABBREV = {
    "ATL": "ATL", "CHI": "CHI", "CON": "CON", "DAL": "DAL", "GS": "GSV",
    "IND": "IND", "LV": "LVA", "LA": "LAS", "MIN": "MIN", "NY": "NYL",
    "PHX": "PHX", "POR": "POR", "SEA": "SEA", "TOR": "TOR", "WSH": "WAS",
}


def fetch_json(url: str, timeout: int = 30) -> dict:
    req = urllib.request.Request(url, headers={
        "User-Agent": "PredictX/1.0",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_wnba_teams() -> list:
    data = fetch_json(ESPN_TEAMS_URL)
    teams = data.get("sports", [{}])[0].get("leagues", [{}])[0].get("teams", [])
    return [
        {
            "espn_id": t["team"]["id"],
            "espn_abbrev": t["team"].get("abbreviation", ""),
            "db_abbrev": ESPN_TO_DB_ABBREV.get(t["team"].get("abbreviation", ""), ""),
            "display_name": t["team"].get("displayName", ""),
        }
        for t in teams
    ]


def fetch_team_roster(espn_team_id: str) -> list:
    url = ESPN_ROSTER_URL.format(team_id=espn_team_id)
    data = fetch_json(url)
    return data.get("athletes", [])


def fetch_player_stats(espn_player_id: str) -> dict:
    url = ESPN_ATHLETE_URL.format(player_id=espn_player_id)
    try:
        data = fetch_json(url, timeout=15)
    except Exception as e:
        logger.warning(f"  ⚠ player {espn_player_id} stats fail: {e}")
        return {}
    athlete = data.get("athlete", {})
    stats_summary = athlete.get("statsSummary", {})
    stats = stats_summary.get("statistics", [])
    return {s.get("name"): s.get("value") for s in stats if s.get("name") and s.get("value") is not None}


def map_team_id(db_abbrev: str, cur) -> str:
    """用 DB 內存的 abbrev 直接查"""
    cur.execute(
        "SELECT team_id FROM predictx.teams WHERE league = %s AND abbreviation = %s",
        (WNBA_LEAGUE_CODE, db_abbrev),
    )
    row = cur.fetchone()
    return row["team_id"] if row else None


def upsert_player(cur, external_id: str, player_name: str, position: str, jersey) -> str:
    cur.execute(
        "SELECT player_id FROM predictx.players WHERE external_id = %s",
        (external_id,),
    )
    row = cur.fetchone()
    if row:
        return row["player_id"]
    cur.execute(
        """
        INSERT INTO predictx.players (external_id, player_name, position, jersey_number, created_at, updated_at)
        VALUES (%s, %s, %s, %s, NOW(), NOW())
        RETURNING player_id
        """,
        (external_id, player_name, position, jersey),
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
        """
        INSERT INTO predictx.player_teams (player_id, team_id, is_active)
        VALUES (%s::uuid, %s::uuid, true)
        """,
        (player_id, team_id),
    )
    return True


def run(dry_run: bool = False) -> dict:
    result = {"teams_processed": 0, "players_inserted": 0, "errors": []}

    if dry_run:
        teams = get_wnba_teams()
        logger.info(f"WNBA 球隊數: {len(teams)}")
        total_players = 0
        for t in teams:
            try:
                roster = fetch_team_roster(t["espn_id"])
                logger.info(f"  {t['display_name']:30s} ({t['espn_abbrev']:3s}→{t['db_abbrev']})  roster={len(roster)}")
                total_players += len(roster)
            except Exception as e:
                logger.warning(f"  ⚠ {t['display_name']}: {e}")
        logger.info(f"WNBA 球員總數: {total_players}")
        return result

    # 連 DB
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL 未設定")

    import psycopg2, psycopg2.extras
    conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()

    teams = get_wnba_teams()
    logger.info(f"開始匯入 {len(teams)} 隊 WNBA 球員資料")

    for t in teams:
        try:
            roster = fetch_team_roster(t["espn_id"])
            team_id = map_team_id(t["db_abbrev"], cur)
            if not team_id:
                result["errors"].append(f"找不到球隊 {t['espn_abbrev']}→{t['db_abbrev']}")
                continue
            team_inserted = 0
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
                    team_inserted += 1
                time.sleep(0.15)
            conn.commit()
            result["teams_processed"] += 1
            result["players_inserted"] += team_inserted
            logger.info(f"  ✓ {t['display_name']:30s}  players_new={team_inserted}/{len(roster)}")
        except Exception as e:
            result["errors"].append(f"{t['display_name']}: {e}")
            conn.rollback()

    cur.close()
    conn.close()
    return result


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true", help="只抓不寫入")
    args = p.parse_args()

    out = run(dry_run=args.dry_run)
    print("\n=== 結果 ===")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    sys.exit(0 if not out.get("errors") else 1)
