#!/usr/bin/env python3
"""
ingest/mlb_standings.py
========================
從 statsapi.mlb.com 抓取 MLB 30 隊全季戰績（6 個 division）。

資料來源：
  https://statsapi.mlb.com/api/v1/standings?leagueId=103,104&season={year}&standingsTypes=regularSeason

寫入：predictx.mlb_team_standings 表（首次執行會自動建表）

抓取欄位：
  - team_id (UUID, 對應 predictx.teams)
  - season (INT)
  - division (TEXT, 'AL East' / 'AL Central' / 'AL West' / 'NL East' / 'NL Central' / 'NL West')
  - league (TEXT, 'American' / 'National')
  - games_played, wins, losses, pct, gb, runs_scored, runs_allowed
  - home_wins, home_losses, away_wins, away_losses
  - l10_wins, l10_losses
  - source, updated_at

呼叫方式：
  python3 mlb_standings.py              # 跑當前球季 (2026)
  python3 mlb_standings.py --year 2025  # 跑指定球季
  python3 mlb_standings.py --dry-run    # 只抓不寫
"""
import os
import sys
import json
import time
import urllib.request
import logging
import argparse
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

LEAGUE_CODE = "MLB"
MLB_STANDINGS_URL = (
    "https://statsapi.mlb.com/api/v1/standings"
    "?leagueId=103,104&season={year}&standingsTypes=regularSeason"
)

HEADERS = {
    "User-Agent": "PredictX/1.0",
    "Accept": "application/json",
}


def fetch_json(url: str, timeout: int = 30) -> dict:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def parse_mlb_standings(data: dict) -> list:
    """從 MLB Stats API 回傳的 standings JSON 抽出 30 隊戰績。"""
    teams = []
    for record in data.get("records", []):
        league = record.get("league", {}) or {}
        division = record.get("division", {}) or {}
        league_id = league.get("id")
        division_id = division.get("id")

        # MLB API 沒有 league/division name，只能用 id 對應
        LEAGUE_MAP = {103: "American", 104: "National"}
        DIVISION_MAP = {
            201: "East", 202: "Central", 200: "West",
            204: "East", 205: "Central", 203: "West",
        }
        league_short = LEAGUE_MAP.get(league_id, f"Unknown-{league_id}")
        div_short = DIVISION_MAP.get(division_id, f"Unknown-{division_id}")

        for tr in record.get("teamRecords", []):
            team = tr.get("team", {}) or {}
            splits = {s.get("type"): s for s in tr.get("records", {}).get("splitRecords", [])}

            home = splits.get("home", {}) or {}
            away = splits.get("away", {}) or {}
            l10 = splits.get("lastTen", {}) or {}

            # gamesBack 可能是 "--" 或數字
            gb_raw = tr.get("gamesBack", "--")
            gb = None if gb_raw == "--" or gb_raw == "-" else float(gb_raw)

            teams.append({
                "team_mlb_id": team.get("id"),
                "team_name": team.get("name"),
                "league": league_short,
                "division": div_short,
                "G": int(tr.get("gamesPlayed", 0)),
                "W": int(tr.get("wins", 0)),
                "L": int(tr.get("losses", 0)),
                "PCT": float(tr.get("winningPercentage", 0.0)),
                "GB": gb,
                "RS": int(tr.get("runsScored", 0)),
                "RA": int(tr.get("runsAllowed", 0)),
                "home_wins": int(home.get("wins", 0)),
                "home_losses": int(home.get("losses", 0)),
                "away_wins": int(away.get("wins", 0)),
                "away_losses": int(away.get("losses", 0)),
                "l10_wins": int(l10.get("wins", 0)),
                "l10_losses": int(l10.get("losses", 0)),
            })
    return teams


def ensure_table(cur) -> None:
    """建立 mlb_team_standings 表（如果不存在）。"""
    cur.execute("""
        CREATE TABLE IF NOT EXISTS predictx.mlb_team_standings (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            team_id UUID NOT NULL REFERENCES predictx.teams(team_id),
            season INT NOT NULL,
            league TEXT NOT NULL,
            division TEXT NOT NULL,
            games_played INT NOT NULL,
            wins INT NOT NULL,
            losses INT NOT NULL,
            pct NUMERIC(4, 3) NOT NULL,
            gb NUMERIC(5, 1),
            runs_scored INT,
            runs_allowed INT,
            home_wins INT,
            home_losses INT,
            away_wins INT,
            away_losses INT,
            l10_wins INT,
            l10_losses INT,
            source TEXT DEFAULT 'statsapi.mlb.com',
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            UNIQUE(team_id, season)
        );

        CREATE INDEX IF NOT EXISTS idx_mlb_team_standings_league_season
            ON predictx.mlb_team_standings (league, season);
    """)


def map_team_id(team_name: str, team_mlb_id: Optional[int], cur) -> Optional[str]:
    """將 MLB Stats API 的 team_name 對應到 predictx.teams.team_id。"""
    cur.execute(
        "SELECT team_id, english_name, team_code FROM predictx.teams WHERE league = %s",
        (LEAGUE_CODE,),
    )
    rows = cur.fetchall()
    team_name_lower = team_name.lower()

    # 1. 先用 external_api_id (= MLB mlb_id) 對應
    if team_mlb_id is not None:
        for r in rows:
            code = r["team_code"]
            if code is not None and str(code) == str(team_mlb_id):
                return r["team_id"]

    # 2. 名稱模糊匹配
    for r in rows:
        db_name = (r["english_name"] or "").lower()
        if team_name_lower == db_name:
            return r["team_id"]
    for r in rows:
        db_name = (r["english_name"] or "").lower()
        if team_name_lower in db_name or db_name in team_name_lower:
            return r["team_id"]

    # 3. 特殊別名匹配
    ALIAS_MAP = {
        "d-backs": "Arizona Diamondbacks",
        "athletics": "Athletics",
        "red sox": "Boston Red Sox",
        "blue jays": "Toronto Blue Jays",
        "white sox": "Chicago White Sox",
    }
    target = ALIAS_MAP.get(team_name_lower)
    if target:
        for r in rows:
            if (r["english_name"] or "").lower() == target.lower():
                return r["team_id"]

    return None


def upsert_team_standing(cur, team_id: str, season: int, data: dict) -> str:
    """寫入或更新球隊戰績。回傳 'INSERT' 或 'UPDATE'。"""
    cur.execute("""
        SELECT id FROM predictx.mlb_team_standings
        WHERE team_id = %s AND season = %s
    """, (team_id, season))
    existing = cur.fetchone()

    if existing:
        cur.execute("""
            UPDATE predictx.mlb_team_standings
            SET league = %s,
                division = %s,
                games_played = %s,
                wins = %s,
                losses = %s,
                pct = %s,
                gb = %s,
                runs_scored = %s,
                runs_allowed = %s,
                home_wins = %s,
                home_losses = %s,
                away_wins = %s,
                away_losses = %s,
                l10_wins = %s,
                l10_losses = %s,
                source = %s,
                updated_at = NOW()
            WHERE team_id = %s AND season = %s
        """, (
            data["league"],
            data["division"],
            data["G"],
            data["W"],
            data["L"],
            data["PCT"],
            data["GB"],
            data["RS"],
            data["RA"],
            data["home_wins"],
            data["home_losses"],
            data["away_wins"],
            data["away_losses"],
            data["l10_wins"],
            data["l10_losses"],
            "statsapi.mlb.com",
            team_id, season,
        ))
        return "UPDATE"

    cur.execute("""
        INSERT INTO predictx.mlb_team_standings (
            team_id, season, league, division, games_played,
            wins, losses, pct, gb, runs_scored, runs_allowed,
            home_wins, home_losses, away_wins, away_losses,
            l10_wins, l10_losses,
            source, updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
    """, (
        team_id, season, data["league"], data["division"], data["G"],
        data["W"], data["L"], data["PCT"], data["GB"],
        data["RS"], data["RA"],
        data["home_wins"], data["home_losses"],
        data["away_wins"], data["away_losses"],
        data["l10_wins"], data["l10_losses"],
        "statsapi.mlb.com",
    ))
    return "INSERT"


def run(year: int = 2026, dry_run: bool = False) -> dict:
    result = {"teams_fetched": 0, "teams_inserted": 0, "teams_updated": 0, "errors": []}

    url = MLB_STANDINGS_URL.format(year=year)
    logger.info(f"抓取 MLB 戰績: {url}")
    try:
        data = fetch_json(url)
    except Exception as e:
        result["errors"].append(f"抓取失敗: {e}")
        logger.error(f"  ❌ {e}")
        return result

    teams = parse_mlb_standings(data)
    logger.info(f"  解析出 {len(teams)} 隊")
    result["teams_fetched"] = len(teams)

    if dry_run:
        logger.info(f"\n=== DRY-RUN 模式：不寫入 DB ===")
        for t in teams:
            logger.info(
                f"  {t['league']:9} {t['division']:8} {t['team_name']:30} "
                f"W:{t['W']:>3} L:{t['L']:>3} PCT:{t['PCT']:.3f} GB:{t['GB']} "
                f"Home:{t['home_wins']}-{t['home_losses']} Away:{t['away_wins']}-{t['away_losses']} L10:{t['l10_wins']}-{t['l10_losses']}"
            )
        return result

    db_url = os.getenv("DATABASE_PUBLIC_URL") or os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL / DATABASE_PUBLIC_URL 未設定")

    import psycopg2
    import psycopg2.extras

    conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()

    # 確保表存在
    try:
        ensure_table(cur)
        conn.commit()
    except Exception as e:
        result["errors"].append(f"建表失敗: {e}")
        logger.error(f"❌ 建表失敗: {e}")
        conn.rollback()
        cur.close()
        conn.close()
        return result

    for t in teams:
        try:
            team_id = map_team_id(t["team_name"], t["team_mlb_id"], cur)
            if not team_id:
                result["errors"].append(f"找不到 team: {t['team_name']}")
                logger.warning(f"  ⚠️ 找不到 team: {t['team_name']}")
                continue

            action = upsert_team_standing(cur, team_id, year, t)
            if action == "INSERT":
                result["teams_inserted"] += 1
                verb = "NEW"
            else:
                result["teams_updated"] += 1
                verb = "UPD"
            logger.info(
                f"  {verb} {t['league']:9} {t['division']:8} {t['team_name']:30} "
                f"W:{t['W']:>3} L:{t['L']:>3} PCT:{t['PCT']:.3f}"
            )
        except Exception as e:
            result["errors"].append(f"{t['team_name']}: {e}")
            logger.error(f"  ❌ {t['team_name']}: {e}")
            conn.rollback()

    conn.commit()
    cur.close()
    conn.close()

    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--year", type=int, default=2026)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    out = run(year=args.year, dry_run=args.dry_run)
    print("\n=== 結果 ===")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    sys.exit(0 if not out.get("errors") else 1)
