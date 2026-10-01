#!/usr/bin/env python3
"""
ingest/nba_players.py
=====================
NBA 球員資料匯入腳本
從 ESPN site.web.api 抓 30 隊 active roster。

2026-10-01 v2 修訂：
- 端點改 site.web.api.espn.com（site.api 對 Railway egress 動態封鎖，web 變體實測較穩）
- 修 upsert_player 的 fetchone() 連叫兩次 bug（第二次回 None → TypeError crash，
  這是名單自 7/3 停更後無法重跑的根因）
- 刷新時把「該隊舊名單中、新名單已不存在」的 player_teams 翻 is_active=false（轉隊/被裁）
- 安全閘：ESPN 必須回 30 隊、單隊 roster 必須 >= 8 人才執行寫入
"""
import os
import sys
import json
import logging
import urllib.request

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

ESPN_TEAMS_URL = "https://site.web.api.espn.com/apis/site/v2/sports/basketball/nba/teams"
ESPN_ROSTER_URL = "https://site.web.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{team_id}/roster"
LEAGUE_CODE = "NBA"
BROWSER_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def fetch_json(url: str, timeout: int = 30) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": BROWSER_UA})
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
    athletes = data.get("athletes", [])
    # 只留 Active 球員（季前 ESPN 偶爾混入非 active 狀態）
    return [a for a in athletes if (a.get("status") or {}).get("type") == "active"]


def map_team_id(espn_name: str, cur) -> str:
    cur.execute("SELECT team_id, english_name FROM predictx.teams WHERE league = %s", (LEAGUE_CODE,))
    rows = cur.fetchall()
    espn_l = espn_name.lower()
    for r in rows:
        if espn_l == r["english_name"].lower():
            return r["team_id"]
    # "LA Clippers" → "Los Angeles Clippers"（ESPN 用 LA 縮寫）
    if espn_l == "la clippers":
        for r in rows:
            if r["english_name"].lower() == "los angeles clippers":
                return r["team_id"]
    for r in rows:
        en_l = r["english_name"].lower()
        for kw in en_l.split():
            if kw and kw in espn_l:
                return r["team_id"]
    return None


def upsert_player(cur, external_id: str, name: str, position: str, jersey) -> str:
    """查 external_id 是否存在 → 存在則更新 position/jersey/updated_at，不存在則 INSERT。
    ⚠️ 舊版對已存在球員連叫兩次 fetchone()，第二次回 None → TypeError crash。"""
    cur.execute("SELECT player_id FROM predictx.players WHERE external_id = %s", (external_id,))
    row = cur.fetchone()
    if row:
        pid = row["player_id"]
        cur.execute(
            "UPDATE predictx.players SET player_name=%s, position=%s, jersey_number=%s, updated_at=NOW() WHERE player_id=%s",
            (name, position, jersey, pid),
        )
        return pid
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
    """已存在 (player_id, team_id) → 翻回 is_active=true；否則 INSERT。回傳是否新建。"""
    cur.execute(
        "SELECT id, is_active FROM predictx.player_teams WHERE player_id = %s::uuid AND team_id = %s::uuid",
        (player_id, team_id),
    )
    row = cur.fetchone()
    if row:
        if not row["is_active"]:
            cur.execute(
                "UPDATE predictx.player_teams SET is_active = true WHERE player_id = %s::uuid AND team_id = %s::uuid",
                (player_id, team_id),
            )
        return False
    cur.execute(
        "INSERT INTO predictx.player_teams (player_id, team_id, is_active) VALUES (%s::uuid, %s::uuid, true)",
        (player_id, team_id),
    )
    return True


def deactivate_missing(cur, team_id: str, roster_external_ids: set):
    """把該隊 active 名單中、新 roster 已不存在（轉隊/被裁）的球員翻 is_active=false。"""
    cur.execute(
        """
        SELECT p.external_id FROM predictx.player_teams pt
        JOIN predictx.players p ON p.player_id = pt.player_id
        WHERE pt.team_id = %s::uuid AND pt.is_active = true
        """,
        (team_id,),
    )
    stale_ids = [r["external_id"] for r in cur.fetchall()
                 if r["external_id"] not in roster_external_ids]
    if stale_ids:
        cur.execute(
            """
            UPDATE predictx.player_teams SET is_active = false
            WHERE team_id = %s::uuid AND is_active = true
              AND player_id IN (SELECT player_id FROM predictx.players WHERE external_id = ANY(%s))
            """,
            (team_id, stale_ids),
        )
    return len(stale_ids)


def run(dry_run: bool = False) -> dict:
    result = {"teams_processed": 0, "players_inserted": 0, "deactivated": 0,
              "roster_sizes": {}, "errors": []}

    teams = get_teams()
    logger.info(f"ESPN NBA 球隊數: {len(teams)}")
    if len(teams) != 30:
        err = f"ESPN 回傳 {len(teams)} 隊（預期 30）— 中止，防止部分寫入"
        logger.error(err)
        result["errors"].append(err)
        return result

    # 單輪抓取全部 roster 快取到記憶體（避免兩輪 60 次 HTTP 逾時）
    rosters = {}
    for t in teams:
        try:
            roster = fetch_roster(t["espn_id"])
            rosters[t["name"]] = roster
            result["roster_sizes"][t["name"]] = len(roster)
        except Exception as e:
            result["errors"].append(f"{t['name']}: roster 抓取失敗 {e}")
            result["roster_sizes"][t["name"]] = -1
            rosters[t["name"]] = None

    if dry_run:
        logger.info("\n=== DRY RUN（不寫入 DB）===")
        for name, n in result["roster_sizes"].items():
            logger.info(f"  {name:30s}  active={n}")
        return result

    db_url = os.getenv("DATABASE_PUBLIC_URL") or os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL / DATABASE_PUBLIC_URL 未設定")
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    import psycopg2, psycopg2.extras
    conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()

    for t in teams:
        name = t["name"]
        if result["roster_sizes"].get(name, -1) < 8:
            result["errors"].append(f"{name}: roster < 8 人（{result['roster_sizes'].get(name)}），跳過")
            continue
        roster = rosters.get(name)
        if not roster:
            continue
        try:
            team_id = map_team_id(name, cur)
            if not team_id:
                result["errors"].append(f"找不到球隊 {name}")
                continue
            roster_ids = set()
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
                roster_ids.add(str(espn_id))
                pid = upsert_player(cur, str(espn_id), full_name, position, jersey_int)
                if upsert_player_team(cur, pid, team_id):
                    inserted += 1
            deactivated = deactivate_missing(cur, team_id, roster_ids)
            conn.commit()
            result["teams_processed"] += 1
            result["players_inserted"] += inserted
            result["deactivated"] += deactivated
            logger.info(f"  ✓ {name:30s}  active={len(roster)}  new={inserted}  deactivated={deactivated}")
        except Exception as e:
            result["errors"].append(f"{name}: {e}")
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
    print(json.dumps({k: v for k, v in out.items() if k != "roster_sizes"},
                     ensure_ascii=False, indent=2))
    sys.exit(0 if not out.get("errors") else 1)
