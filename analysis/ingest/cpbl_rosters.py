#!/usr/bin/env python3
"""
ingest/cpbl_rosters.py
=======================
CPBL roster 入庫腳本（一次性回填，可重複跑 idempotent）
從 stats.cpbl.com.tw/rankings 抓 6 隊現有球員名單，寫入：
  - predictx.players
  - predictx.player_teams
  - predictx.rosters
"""
import os, sys, json, logging, argparse

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("cpbl_rosters")

LEAGUE_CODE = "CPBL"
SEASON = 2026

# CPBL 6 隊英文名，用於從 teams 表查 team_id
CPBL_TEAMS_EN = (
    "Rakuten Monkeys",
    "Wei Chuan Dragons",
    "TSG Hawks",
    "Uni-President 7-ELEVEn Lions",
    "CTBC Brothers",
    "Fubon Guardians",
)


def fetch_players_json(out_path: str) -> dict:
    """Step 1：抓 CPBL 球員清單，存成 JSON"""
    # 加入 analysis 父目錄以便 import cpbl_data_fetcher
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if here not in sys.path:
        sys.path.insert(0, here)
    from cpbl_data_fetcher import CPBLDataFetcher
    fetcher = CPBLDataFetcher()
    players = fetcher.get_players_from_rankings() or {}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"season": SEASON, "players": players}, f, ensure_ascii=False, indent=2)
    return players


def ingest_from_json(json_path: str, db_url: str, roster_date: str) -> dict:
    """Step 2：從 JSON 讀資料並寫入 DB（idempotent）"""
    import psycopg2, psycopg2.extras

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    season = data.get("season", SEASON)
    players = data.get("players", {})

    result = {
        "teams_processed": 0,
        "players_inserted": 0,
        "players_existing": 0,
        "player_teams_inserted": 0,
        "rosters_inserted": 0,
        "errors": [],
    }

    conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()

    cur.execute(
        "SELECT team_id, english_name FROM predictx.teams WHERE english_name IN %s",
        (CPBL_TEAMS_EN,),
    )
    team_id_map = {r["english_name"]: r["team_id"] for r in cur.fetchall()}

    for team_en, ps in players.items():
        if team_en not in team_id_map:
            result["errors"].append(f"teams 表找不到 {team_en}")
            continue
        team_id = team_id_map[team_en]

        new_p = new_pt = new_r = existing = 0
        try:
            for p in ps:
                # 1. players
                cur.execute("SELECT player_id FROM predictx.players WHERE external_id = %s", (p["id"],))
                row = cur.fetchone()
                if row:
                    pid = row["player_id"]
                    existing += 1
                else:
                    cur.execute(
                        "INSERT INTO predictx.players (external_id, player_name, created_at, updated_at) "
                        "VALUES (%s, %s, NOW(), NOW()) RETURNING player_id",
                        (p["id"], p["name"]),
                    )
                    pid = cur.fetchone()["player_id"]
                    new_p += 1

                # 2. player_teams
                cur.execute(
                    "SELECT id FROM predictx.player_teams WHERE player_id = %s::uuid AND team_id = %s::uuid",
                    (pid, team_id),
                )
                if not cur.fetchone():
                    cur.execute(
                        "INSERT INTO predictx.player_teams (player_id, team_id, is_active) "
                        "VALUES (%s::uuid, %s::uuid, true)",
                        (pid, team_id),
                    )
                    new_pt += 1

                # 3. rosters
                cur.execute(
                    "INSERT INTO predictx.rosters (season, roster_date, team_id, player_uuid, is_active) "
                    "VALUES (%s, %s, %s::uuid, %s::uuid, true) "
                    "ON CONFLICT (season, team_id, player_uuid) DO NOTHING RETURNING player_uuid",
                    (season, roster_date, team_id, pid),
                )
                if cur.fetchone():
                    new_r += 1

            conn.commit()
            result["teams_processed"] += 1
            result["players_inserted"] += new_p
            result["players_existing"] += existing
            result["player_teams_inserted"] += new_pt
            result["rosters_inserted"] += new_r
            logger.info(
                f"  ✓ {team_en:30s}  players_new={new_p} pt_new={new_pt} rosters_new={new_r} existing={existing}"
            )
        except Exception as e:
            result["errors"].append(f"{team_en}: {e}")
            conn.rollback()
            logger.exception(f"  ✗ {team_en} failed")

    cur.close()
    conn.close()
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--fetch-only", action="store_true", help="只抓資料存 JSON")
    p.add_argument("--ingest-only", action="store_true", help="只從 JSON 寫入 DB")
    p.add_argument("--json", default="/tmp/cpbl_rosters.json")
    p.add_argument("--roster-date", default="2026-08-27")
    args = p.parse_args()

    db_url = os.getenv("DATABASE_URL")
    if not args.fetch_only and not db_url:
        print("DATABASE_URL 未設定", file=sys.stderr)
        sys.exit(1)

    if not args.ingest_only:
        logger.info(f"[Step 1] 抓 CPBL 球員清單 → {args.json}")
        players = fetch_players_json(args.json)
        total = sum(len(v) for v in players.values())
        logger.info(f"  抓到 {len(players)} 隊、{total} 名球員")

    if not args.fetch_only:
        logger.info(f"[Step 2] 寫入 DB（roster_date={args.roster_date}）")
        out = ingest_from_json(args.json, db_url, args.roster_date)
        print("\n=== 結果 ===")
        print(json.dumps(out, ensure_ascii=False, indent=2))
        sys.exit(0 if not out.get("errors") else 1)
