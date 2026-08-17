#!/usr/bin/env python3
"""
ingest/cpbl_standings.py
========================
從 CPBL 官網抓取中華職棒 6 隊戰績（含主場、客場、近十場、連勝/連敗）。

資料來源：複用 CPBLDataFetcher.get_team_standings()
（從 https://www.cpbl.com.tw/standings/season 抓取）

寫入：predictx.cpbl_team_standings 表（首次執行會自動建表）

抓取欄位：
  - team_id (UUID, 對應 predictx.teams)
  - season (INT)
  - rank (INT)
  - games_played (INT)
  - wins, losses, ties (INT)
  - pct (NUMERIC)
  - home_wins, home_losses, home_ties (INT)
  - away_wins, away_losses, away_ties (INT)
  - l10_wins, l10_losses, l10_ties (INT)
  - streak_wins (TEXT, e.g. '勝1' or '敗1')
  - source, updated_at

呼叫方式：
  python3 cpbl_standings.py              # 跑當前球季 (2026)
  python3 cpbl_standings.py --season 2025  # 跑指定球季
  python3 cpbl_standings.py --dry-run    # 只抓不寫
"""
import os
import sys
import json
import logging
import argparse
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

LEAGUE_CODE = "CPBL"


def fetch_data_via_fetcher() -> Optional[dict]:
    """透過 CPBLDataFetcher 抓取戰績資料。"""
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    try:
        from cpbl_data_fetcher import CPBLDataFetcher
    except ImportError as e:
        logger.error(f"無法 import CPBLDataFetcher: {e}")
        return None

    fetcher = CPBLDataFetcher()
    # fetch_team_standings() 不需要 DB 連線，直接 GET 網站
    result = fetcher.get_team_standings()
    if not result:
        return None
    return result.get("standings", {})


def parse_team_stats(team_name: str, data: dict) -> dict:
    """從 CPBLDataFetcher 回傳的 stats dict 抽取主要戰績欄位。"""
    # wl_record 格式: "W-T-L" (CPBL 與其他聯盟相反)
    wl = data.get("wl_record", "0-0-0")
    parts = wl.split("-")
    wins = int(parts[0]) if len(parts) > 0 else 0
    ties = int(parts[1]) if len(parts) > 1 else 0
    losses = int(parts[2]) if len(parts) > 2 else 0

    h2h = data.get("h2h", {})
    home = h2h.get("主場戰績", {})
    away = h2h.get("客場戰績", {})
    l10 = h2h.get("近十場戰績", {})
    streak = h2h.get("連勝/連敗", {})

    return {
        "team_en": team_name,
        "rank": int(data.get("rank", 0)),
        "games_played": int(data.get("games", 0)),
        "wins": wins,
        "ties": ties,
        "losses": losses,
        "pct": float(data.get("win_pct", 0.0)),
        "home_wins": int(home.get("wins", 0)),
        "home_ties": int(home.get("ties", 0)),
        "home_losses": int(home.get("losses", 0)),
        "away_wins": int(away.get("wins", 0)),
        "away_ties": int(away.get("ties", 0)),
        "away_losses": int(away.get("losses", 0)),
        "l10_wins": int(l10.get("wins", 0)),
        "l10_ties": int(l10.get("ties", 0)),
        "l10_losses": int(l10.get("losses", 0)),
        "streak_text": str(streak.get("wins", "")) if streak else "",
    }


def ensure_table(cur) -> None:
    """建立 cpbl_team_standings 表（如果不存在）。"""
    cur.execute("""
        CREATE TABLE IF NOT EXISTS predictx.cpbl_team_standings (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            team_id UUID NOT NULL REFERENCES predictx.teams(team_id),
            season INT NOT NULL,
            rank INT,
            games_played INT NOT NULL,
            wins INT NOT NULL,
            losses INT NOT NULL,
            ties INT NOT NULL DEFAULT 0,
            pct NUMERIC(4, 3) NOT NULL,
            home_wins INT,
            home_losses INT,
            home_ties INT DEFAULT 0,
            away_wins INT,
            away_losses INT,
            away_ties INT DEFAULT 0,
            l10_wins INT,
            l10_losses INT,
            l10_ties INT DEFAULT 0,
            streak_text TEXT,
            source TEXT DEFAULT 'cpbl.com.tw',
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            UNIQUE(team_id, season)
        );

        CREATE INDEX IF NOT EXISTS idx_cpbl_team_standings_season
            ON predictx.cpbl_team_standings (season);
    """)


def map_team_id(team_en: str, cur) -> Optional[str]:
    """將 CPBLDataFetcher 給的英文名對應到 predictx.teams.team_id。"""
    cur.execute(
        "SELECT team_id, english_name FROM predictx.teams WHERE league = %s",
        (LEAGUE_CODE,),
    )
    rows = cur.fetchall()
    target = team_en.lower()

    # 1. 完全匹配
    for r in rows:
        if (r["english_name"] or "").lower() == target:
            return r["team_id"]

    # 2. 部分包含
    for r in rows:
        db_name = (r["english_name"] or "").lower()
        if target in db_name or db_name in target:
            return r["team_id"]

    # 3. 別名對應
    ALIASES = {
        "wei chuan dragons": "Wei Chuan Dragons",
        "rakuten monkeys": "Rakuten Monkeys",
        "ctbc brothers": "CTBC Brothers",
        "uni-president 7-eleven lions": "Uni-President 7-ELEVEn Lions",
        "tsg hawks": "TSG Hawks",
        "fubon guardians": "Fubon Guardians",
    }
    target_alias = ALIASES.get(target)
    if target_alias:
        for r in rows:
            if (r["english_name"] or "").lower() == target_alias.lower():
                return r["team_id"]

    return None


def upsert_team_standing(cur, team_id: str, season: int, data: dict) -> str:
    """寫入或更新球隊戰績。回傳 'INSERT' 或 'UPDATE'。"""
    cur.execute("""
        SELECT id FROM predictx.cpbl_team_standings
        WHERE team_id = %s AND season = %s
    """, (team_id, season))
    existing = cur.fetchone()

    if existing:
        cur.execute("""
            UPDATE predictx.cpbl_team_standings
            SET rank = %s,
                games_played = %s,
                wins = %s,
                losses = %s,
                ties = %s,
                pct = %s,
                home_wins = %s,
                home_losses = %s,
                home_ties = %s,
                away_wins = %s,
                away_losses = %s,
                away_ties = %s,
                l10_wins = %s,
                l10_losses = %s,
                l10_ties = %s,
                streak_text = %s,
                source = %s,
                updated_at = NOW()
            WHERE team_id = %s AND season = %s
        """, (
            data["rank"],
            data["games_played"],
            data["wins"],
            data["losses"],
            data["ties"],
            data["pct"],
            data["home_wins"],
            data["home_losses"],
            data["home_ties"],
            data["away_wins"],
            data["away_losses"],
            data["away_ties"],
            data["l10_wins"],
            data["l10_losses"],
            data["l10_ties"],
            data["streak_text"],
            "cpbl.com.tw",
            team_id, season,
        ))
        return "UPDATE"

    cur.execute("""
        INSERT INTO predictx.cpbl_team_standings (
            team_id, season, rank, games_played,
            wins, losses, ties, pct,
            home_wins, home_losses, home_ties,
            away_wins, away_losses, away_ties,
            l10_wins, l10_losses, l10_ties,
            streak_text, source, updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
    """, (
        team_id, season, data["rank"], data["games_played"],
        data["wins"], data["losses"], data["ties"], data["pct"],
        data["home_wins"], data["home_losses"], data["home_ties"],
        data["away_wins"], data["away_losses"], data["away_ties"],
        data["l10_wins"], data["l10_losses"], data["l10_ties"],
        data["streak_text"],
        "cpbl.com.tw",
    ))
    return "INSERT"


def run(season: int = 2026, dry_run: bool = False) -> dict:
    result = {"teams_fetched": 0, "teams_inserted": 0, "teams_updated": 0, "errors": []}

    logger.info("透過 CPBLDataFetcher 抓取 CPBL 戰績...")
    raw = fetch_data_via_fetcher()
    if not raw:
        result["errors"].append("抓取失敗")
        logger.error("❌ 抓取失敗")
        return result

    teams = [parse_team_stats(name, data) for name, data in raw.items()]
    logger.info(f"  解析出 {len(teams)} 隊")
    result["teams_fetched"] = len(teams)

    if dry_run:
        logger.info(f"\n=== DRY-RUN 模式：不寫入 DB ===")
        for t in teams:
            logger.info(
                f"  #{t['rank']} {t['team_en']:35} W:{t['wins']:>3} L:{t['losses']:>3} T:{t['ties']:>2} "
                f"PCT:{t['pct']:.3f} Home:{t['home_wins']}-{t['home_losses']} Away:{t['away_wins']}-{t['away_losses']} "
                f"L10:{t['l10_wins']}-{t['l10_losses']} Streak:{t['streak_text']}"
            )
        return result

    db_url = os.getenv("DATABASE_PUBLIC_URL") or os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL / DATABASE_PUBLIC_URL 未設定")

    import psycopg2
    import psycopg2.extras

    conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()

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
            team_id = map_team_id(t["team_en"], cur)
            if not team_id:
                result["errors"].append(f"找不到 team: {t['team_en']}")
                logger.warning(f"  ⚠️ 找不到 team: {t['team_en']}")
                continue

            action = upsert_team_standing(cur, team_id, season, t)
            if action == "INSERT":
                result["teams_inserted"] += 1
                verb = "NEW"
            else:
                result["teams_updated"] += 1
                verb = "UPD"
            logger.info(
                f"  {verb} #{t['rank']} {t['team_en']:35} W:{t['wins']:>3} L:{t['losses']:>3} T:{t['ties']:>2} PCT:{t['pct']:.3f}"
            )
        except Exception as e:
            result["errors"].append(f"{t['team_en']}: {e}")
            logger.error(f"  ❌ {t['team_en']}: {e}")
            conn.rollback()

    conn.commit()
    cur.close()
    conn.close()

    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--season", type=int, default=2026)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    out = run(season=args.season, dry_run=args.dry_run)
    print("\n=== 結果 ===")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    sys.exit(0 if not out.get("errors") else 1)
