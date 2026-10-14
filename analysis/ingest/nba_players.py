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
    from psycopg2.extras import execute_values
    conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()

    # ==================================================================
    # 🆕 [2026-10-12] 改為「批量寫入」——修效能瓶頸
    #
    # 舊版逐筆 upsert（每球員 2 次往返 + 每隊 2 次停用查詢）：
    #   615 人 × 2 ≈ 1230 次 DB 往返，經 Railway public proxy 實測 >7 分鐘，
    #   在 cron（agent 工具逾時上限 600s）下有逾時失敗風險。
    # 新版：全部改為 execute_values 批量 → 常數次往返（實測 <10 秒）。
    # ==================================================================

    # ① 隊名 → team_id（1 次查詢，取代原本每隊各查一次）
    cur.execute("SELECT team_id::text AS tid, english_name FROM predictx.teams WHERE league = %s",
                (LEAGUE_CODE,))
    trows = cur.fetchall()

    def _map_team(espn_name):
        espn_l = (espn_name or "").lower()
        for r in trows:
            if espn_l == (r["english_name"] or "").lower():
                return r["tid"]
        if espn_l == "la clippers":  # ESPN 用 LA 縮寫
            for r in trows:
                if (r["english_name"] or "").lower() == "los angeles clippers":
                    return r["tid"]
        for r in trows:
            for kw in (r["english_name"] or "").lower().split():
                if kw and kw in espn_l:
                    return r["tid"]
        return None

    # ② 攤平所有要寫入的球員（同時套用「單隊 roster >= 8 人」安全閘）
    staged = []              # (external_id, name, position, jersey, team_id)
    team_roster_ids = {}     # team_id -> set(external_id)
    for t in teams:
        name = t["name"]
        if result["roster_sizes"].get(name, -1) < 8:
            result["errors"].append(f"{name}: roster < 8 人（{result['roster_sizes'].get(name)}），跳過")
            continue
        roster = rosters.get(name)
        if not roster:
            continue
        tid = _map_team(name)
        if not tid:
            result["errors"].append(f"找不到球隊 {name}")
            continue
        ids = set()
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
            ids.add(str(espn_id))
            staged.append((str(espn_id), full_name, position, jersey_int, tid))
        team_roster_ids[tid] = ids

    # external_id 去重（同一人理論上不會出現在兩隊，但保險）
    seen_ext = set()
    staged_u = []
    for row in staged:
        if row[0] in seen_ext:
            continue
        seen_ext.add(row[0])
        staged_u.append(row)

    try:
        # ③ players 批量 upsert（1 次往返）
        if staged_u:
            execute_values(cur, """
                INSERT INTO predictx.players
                    (external_id, player_name, position, jersey_number, created_at, updated_at)
                VALUES %s
                ON CONFLICT (external_id) DO UPDATE
                  SET player_name = EXCLUDED.player_name,
                      position = EXCLUDED.position,
                      jersey_number = EXCLUDED.jersey_number,
                      updated_at = NOW()
            """, [(e, n, p, j) for e, n, p, j, _ in staged_u],
                template="(%s, %s, %s, %s, NOW(), NOW())")

        # ④ 取回 player_id 對照（1 次查詢）
        cur.execute("SELECT player_id::text AS pid, external_id FROM predictx.players WHERE external_id = ANY(%s)",
                    (list(seen_ext),))
        pid_by_ext = {r["external_id"]: r["pid"] for r in cur.fetchall()}

        # ⑤ 既有 player_teams（本聯盟，1 次查詢）
        cur.execute("""
            SELECT pt.player_id::text AS pid, pt.team_id::text AS tid, pt.is_active
            FROM predictx.player_teams pt
            JOIN predictx.teams tt ON pt.team_id = tt.team_id
            WHERE tt.league = %s
        """, (LEAGUE_CODE,))
        existing = {(r["pid"], r["tid"]): r["is_active"] for r in cur.fetchall()}

        # ⑥ 計算需 INSERT / 需復活 / 需停用
        to_insert, to_reactivate = [], []
        for ext, _n, _p, _j, tid in staged_u:
            pid = pid_by_ext.get(ext)
            if not pid:
                continue
            key = (pid, tid)
            if key in existing:
                if not existing[key]:
                    to_reactivate.append((pid, tid))
                    existing[key] = True
            else:
                to_insert.append((pid, tid))
                existing[key] = True

        ext_by_pid = {v: k for k, v in pid_by_ext.items()}
        stale = []
        for (pid, tid), is_active in existing.items():
            if not is_active or tid not in team_roster_ids:
                continue
            ext = ext_by_pid.get(pid)
            if ext is not None and ext not in team_roster_ids[tid]:
                stale.append((pid, tid))

        # ⑦ 批量執行（各 1 次往返）
        if to_insert:
            execute_values(cur, """
                INSERT INTO predictx.player_teams (player_id, team_id, is_active) VALUES %s
            """, to_insert, template="(%s::uuid, %s::uuid, true)")
            result["players_inserted"] = len(to_insert)
        if to_reactivate:
            execute_values(cur, """
                UPDATE predictx.player_teams pt SET is_active = true
                FROM (VALUES %s) AS v(pid, tid)
                WHERE pt.player_id = v.pid::uuid AND pt.team_id = v.tid::uuid
            """, to_reactivate, template="(%s, %s)")
        if stale:
            execute_values(cur, """
                UPDATE predictx.player_teams pt SET is_active = false
                FROM (VALUES %s) AS v(pid, tid)
                WHERE pt.player_id = v.pid::uuid AND pt.team_id = v.tid::uuid
            """, stale, template="(%s, %s)")
            result["deactivated"] = len(stale)

        conn.commit()
        result["teams_processed"] = len(team_roster_ids)
        logger.info(f"  ✓ 批量寫入完成：{len(team_roster_ids)} 隊 / {len(staged_u)} 人 "
                    f"/ new={result['players_inserted']} reactivated={len(to_reactivate)} "
                    f"/ deactivated={result['deactivated']}")
    except Exception as e:
        result["errors"].append(f"批量寫入失敗: {e}")
        conn.rollback()
    finally:
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
