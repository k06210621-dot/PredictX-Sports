#!/usr/bin/env python3
"""
ingest/npb_standings.py
========================
從 npb.jp 抓取 NPB 球隊全季戰績（Pacific + Central League）。

資料來源：
  https://npb.jp/bis/eng/{year}/stats/std_p.html
  https://npb.jp/bis/eng/{year}/stats/std_c.html

寫入：predictx.npb_team_standings 表（首次執行會自動建表）

抓取欄位：
  - team_id (UUID, 對應 predictx.teams)
  - season (INT)
  - league (TEXT, 'Pacific' / 'Central')
  - games_played (INT)
  - wins, losses, ties (INT)
  - pct (NUMERIC)
  - gb (NUMERIC)
  - home_wins, home_losses (INT)
  - away_wins, away_losses (INT)
  - updated_at (TIMESTAMP)

呼叫方式：
  python3 npb_standings.py          # 跑當前球季 (2026)
  python3 npb_standings.py --year 2025  # 跑指定球季
  python3 npb_standings.py --dry-run  # 只抓不寫
"""
import os
import re
import sys
import json
import time
import urllib.request
import logging
import argparse

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

LEAGUE_CODE = "NPB"
NPB_URL_TEMPLATE = "https://npb.jp/bis/eng/{year}/stats/std_{league_letter}.html"

# JS 動態載入頁面 → 需要 User-Agent 偽裝成瀏覽器
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Safari/605.1.15",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,ja;q=0.8",
}

# 將 npb.jp 英文名 → DB teams team_id 的 mapping
TEAM_NAME_OVERRIDES = {
    "YOKOHAMA DeNA BAYSTARS": "Yokohama DeNA BayStars",  # npb.jp 大寫
    "Saitama Seibu Lions": "Saitama Seibu Lions",
}


def fetch_html(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parse_standings_table(html: str, league_name: str) -> list:
    """從 npb.jp 戰績頁 HTML 抽 6 隊球隊戰績。"""
    tables = re.findall(r"<table[^>]*>(.*?)</table>", html, re.DOTALL)
    teams = []
    seen = set()

    for table in tables:
        cells = re.findall(r"<td[^>]*>(.*?)</td>", table, re.DOTALL)
        cells = [re.sub(r"<.*?>", "", c).strip() for c in cells]

        # 16 個 cells 一組
        for i in range(0, len(cells), 16):
            row = cells[i:i + 16]
            if len(row) != 16 or not row[0]:
                continue

            team_name = row[0]
            if "***" in team_name or "Team" in team_name:
                continue

            # 過濾 Interleague（games < 50）
            try:
                g = int(row[1])
            except (ValueError, IndexError):
                continue
            if g < 50:
                continue

            # 統一 BayStars 名稱
            if "BAYSTARS" in team_name.upper():
                team_name = "Yokohama DeNA BayStars"

            if team_name in seen:
                continue
            seen.add(team_name)

            teams.append({
                "league": league_name,
                "team": team_name,
                "G": row[1],
                "W": row[2],
                "L": row[3],
                "T": row[4],
                "PCT": row[5],
                "GB": row[6],
                "Home": row[7],
                "Road": row[8],
            })
    return teams


def parse_home_away(record: str):
    """解析 '36-21' 或 '31-18(1)' 為 (wins, losses)。"""
    # 去掉 (1) 這種 extra
    record = re.sub(r"\(\d+\)", "", record).strip()
    parts = record.split("-")
    if len(parts) == 2:
        try:
            return int(parts[0]), int(parts[1])
        except ValueError:
            return None, None
    return None, None


def ensure_table(cur) -> None:
    """建立 npb_team_standings 表（如果不存在）。"""
    cur.execute("""
        CREATE TABLE IF NOT EXISTS predictx.npb_team_standings (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            team_id UUID NOT NULL REFERENCES predictx.teams(team_id),
            season INT NOT NULL,
            league TEXT NOT NULL,
            games_played INT NOT NULL,
            wins INT NOT NULL,
            losses INT NOT NULL,
            ties INT NOT NULL DEFAULT 0,
            pct NUMERIC(4, 3) NOT NULL,
            gb NUMERIC(5, 1),
            home_wins INT,
            home_losses INT,
            away_wins INT,
            away_losses INT,
            source TEXT DEFAULT 'npb.jp',
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            UNIQUE(team_id, season)
        );

        CREATE INDEX IF NOT EXISTS idx_npb_team_standings_league_season
            ON predictx.npb_team_standings (league, season);
    """)


from typing import Optional


def map_team_id(npb_name: str, cur) -> Optional[str]:
    """將 npb.jp 英文名對應到 predictx.teams.team_id。"""
    cur.execute(
        "SELECT team_id, english_name FROM predictx.teams WHERE league = %s",
        (LEAGUE_CODE,),
    )
    rows = [{'team_id': r['team_id'], 'name': r['english_name']} for r in cur.fetchall()]
    npb_lower = npb_name.lower()

    # 1. 完全匹配
    for r in rows:
        if r['name'].lower() == npb_lower:
            return r['team_id']

    # 2. 部分包含
    for r in rows:
        if npb_lower in r['name'].lower() or r['name'].lower() in npb_lower:
            return r['team_id']

    # 3. 特殊處理
    name_map = {
        "fukuoka softbank hawks": "Fukuoka SoftBank Hawks",
        "saitama seibu lions": "Saitama Seibu Lions",
        "hokkaido nippon-ham fighters": "Hokkaido Nippon-Ham Fighters",
        "orix buffaloes": "ORIX Buffaloes",
        "chiba lotte marines": "Chiba Lotte Marines",
        "tohoku rakuten golden eagles": "Tohoku Rakuten Golden Eagles",
        "hanshin tigers": "Hanshin Tigers",
        "yomiuri giants": "Yomiuri Giants",
        "tokyo yakult swallows": "Tokyo Yakult Swallows",
        "yokohama dena baystars": "Yokohama DeNA BayStars",
        "chunichi dragons": "Chunichi Dragons",
        "hiroshima toyo carp": "Hiroshima Toyo Carp",
    }
    target = name_map.get(npb_lower)
    if target:
        for r in rows:
            if r['name'].lower() == target.lower():
                return r['team_id']

    return None


def upsert_team_standing(cur, team_id: str, season: int, data: dict) -> str:
    """寫入或更新球隊戰績。回傳 'INSERT' 或 'UPDATE'。"""
    home_w, home_l = parse_home_away(data["Home"])
    away_w, away_l = parse_home_away(data["Road"])

    # 先查詢是否已存在
    cur.execute("""
        SELECT id FROM predictx.npb_team_standings
        WHERE team_id = %s AND season = %s
    """, (team_id, season))
    existing = cur.fetchone()

    if existing:
        cur.execute("""
            UPDATE predictx.npb_team_standings
            SET league = %s,
                games_played = %s,
                wins = %s,
                losses = %s,
                ties = %s,
                pct = %s,
                gb = %s,
                home_wins = %s,
                home_losses = %s,
                away_wins = %s,
                away_losses = %s,
                source = %s,
                updated_at = NOW()
            WHERE team_id = %s AND season = %s
        """, (
            data["league"],
            int(data["G"]),
            int(data["W"]),
            int(data["L"]),
            int(data["T"]),
            float(data["PCT"]),
            None if data["GB"] == "--" else float(data["GB"]),
            home_w, home_l, away_w, away_l,
            "npb.jp",
            team_id, season,
        ))
        return "UPDATE"

    cur.execute("""
        INSERT INTO predictx.npb_team_standings (
            team_id, season, league, games_played,
            wins, losses, ties, pct, gb,
            home_wins, home_losses, away_wins, away_losses,
            source, updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
    """, (
        team_id, season, data["league"], int(data["G"]),
        int(data["W"]), int(data["L"]), int(data["T"]),
        float(data["PCT"]), None if data["GB"] == "--" else float(data["GB"]),
        home_w, home_l, away_w, away_l,
        "npb.jp",
    ))
    return "INSERT"


def run(year: int = 2026, dry_run: bool = False) -> dict:
    result = {"teams_fetched": 0, "teams_inserted": 0, "teams_updated": 0, "errors": []}

    leagues = [
        ("Pacific", "p"),
        ("Central", "c"),
    ]

    all_teams = []
    for league_name, league_letter in leagues:
        url = NPB_URL_TEMPLATE.format(year=year, league_letter=league_letter)
        logger.info(f"抓取 {league_name} 戰績: {url}")
        try:
            html = fetch_html(url)
        except Exception as e:
            result["errors"].append(f"{league_name}: {e}")
            logger.error(f"  ❌ {e}")
            continue

        teams = parse_standings_table(html, league_name)
        logger.info(f"  解析出 {len(teams)} 隊")
        all_teams.extend(teams)
        time.sleep(1)  # 禮貌延遲

    result["teams_fetched"] = len(all_teams)

    if dry_run:
        logger.info(f"\n=== DRY-RUN 模式：不寫入 DB ===")
        for t in all_teams:
            logger.info(f"  {t['league']:10} {t['team']:30} W:{t['W']:>3} L:{t['L']:>3} PCT:{t['PCT']}")
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

    for t in all_teams:
        try:
            team_id = map_team_id(t["team"], cur)
            if not team_id:
                result["errors"].append(f"找不到 team: {t['team']}")
                logger.warning(f"  ⚠️ 找不到 team: {t['team']}")
                continue

            action = upsert_team_standing(cur, team_id, year, t)
            if action == "INSERT":
                result["teams_inserted"] += 1
                verb = "NEW"
            else:
                result["teams_updated"] += 1
                verb = "UPD"
            logger.info(f"  {verb} {t['league']:10} {t['team']:30} W:{t['W']:>3} L:{t['L']:>3} PCT:{t['PCT']}")
        except Exception as e:
            result["errors"].append(f"{t['team']}: {e}")
            logger.error(f"  ❌ {t['team']}: {e}")
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
