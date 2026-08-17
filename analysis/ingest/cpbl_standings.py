#!/usr/bin/env python3
"""
ingest/cpbl_standings.py
========================
從 CPBL 官網抓取中華職棒 6 隊戰績（含 上半季、下半季、全年度 三種視角）。

資料來源：https://www.cpbl.com.tw/standings/seasonaction
  POST kindCode=A&seasonCode=1  # 上半季
  POST kindCode=A&seasonCode=2  # 下半季
  POST kindCode=A&seasonCode=0  # 全年度

寫入：predictx.cpbl_team_standings 表（首次執行會自動建表）

抓取欄位：
  - team_id (UUID, 對應 predictx.teams)
  - season (INT)
  - half_season (INT, 1=上半季, 2=下半季, 0=全年度)
  - rank, games_played, wins, losses, ties, pct
  - home_wins, home_losses, home_ties
  - away_wins, away_losses, away_ties
  - l10_wins, l10_losses, l10_ties
  - streak_text (e.g. '勝1' or '敗1')
  - source, updated_at

呼叫方式：
  python3 cpbl_standings.py                # 跑當前球季 (2026)，三個 season
  python3 cpbl_standings.py --season 2025  # 跑指定球季
  python3 cpbl_standings.py --half 1,2,0   # 指定抓哪些 season
  python3 cpbl_standings.py --dry-run      # 只抓不寫
"""
import os
import re
import sys
import json
import time
import subprocess
import urllib.parse
import logging
import argparse
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

LEAGUE_CODE = "CPBL"
STANDINGS_URL = "https://www.cpbl.com.tw/standings/season"
ACTION_URL = "https://www.cpbl.com.tw/standings/seasonaction"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Safari/605.1.15",
}

# 中文隊名 → 英文名對應（從 CPBL 官網）
TEAM_CN_TO_EN = {
    "味全龍": "Wei Chuan Dragons",
    "富邦悍將": "Fubon Guardians",
    "統一7-ELEVEn獅": "Uni-President 7-ELEVEn Lions",
    "中信兄弟": "CTBC Brothers",
    "樂天桃猿": "Rakuten Monkeys",
    "台鋼雄鷹": "TSG Hawks",
}


class CPBLClient:
    """CPBL 官網戰績抓取 client（使用 curl 處理 308 redirect）。"""

    def __init__(self):
        self.cookie_file = "/tmp/cpbl_cookies.txt"
        if os.path.exists(self.cookie_file):
            os.remove(self.cookie_file)
        self.token = None

    def _run_curl(self, args):
        """執行 curl，返回 stdout。"""
        result = subprocess.run(
            ["curl", "-s", "-L", "-c", self.cookie_file, "-b", self.cookie_file,
             "-H", f"User-Agent: {HEADERS['User-Agent']}"] + args,
            capture_output=True, text=True, timeout=30,
        )
        return result.stdout

    def _fetch_token(self):
        """從 standings/season 頁取得 CSRF token。"""
        stdout = self._run_curl([STANDINGS_URL])
        m = re.search(r'name="__RequestVerificationToken" type="hidden" value="([^"]+)"', stdout)
        if not m:
            raise RuntimeError("無法取得 CSRF token")
        return m.group(1)

    def fetch_season(self, season_code):
        """抓取指定 season 戰績 HTML。season_code: 1=上半季, 2=下半季, 0=全年度。"""
        if not self.token:
            self.token = self._fetch_token()

        data = (
            f"kindCode=A&seasonCode={season_code}&gameEndDate="
            f"&__RequestVerificationToken={urllib.parse.quote(self.token)}"
        )
        try:
            stdout = self._run_curl([
                "-X", "POST",
                ACTION_URL,
                "-H", "Content-Type: application/x-www-form-urlencoded",
                "-d", data,
            ])
            return stdout
        except Exception as e:
            logger.error(f"❌ season={season_code} 抓取失敗: {e}")
            return None


def parse_standings_table(html: str) -> list:
    """從 CPBL 戰績 HTML 抽 6 隊戰績。

    表格結構（已驗證）：
      Row 0 (header): 排名(球隊) | 出賽數 | 勝-和-敗 | 勝率 | 勝差 | 淘汰指數 |
                      [6 隊對戰 (依排名順序的 6 個隊名)] | 主場戰績 | 客場戰績 | 連勝/連敗 | 近十場戰績
      Row 1+ (排名 1-6): 排名 | 出賽數 | W-T-L | 勝率 | 勝差 | 淘汰指數 |
              [6 個對戰戰績 (依排名順序對應 header 隊名)] | 主場 | 客場 | 連勝 | 近十場

    隊名對應：row 1+ 的「排名」欄位（cell 0）內有球隊連結 (e.g. <a href=...>味全龍</a>)
    """
    tables = re.findall(r"<table[^>]*>(.*?)</table>", html, re.DOTALL)
    if not tables:
        return []

    teams = []
    # 只處理第一個 table（戰績表），跳過投球、打擊、守備
    for tbl_idx, table in enumerate(tables):
        if tbl_idx > 0:
            break

        trs = re.findall(r"<tr[^>]*>(.*?)</tr>", table, re.DOTALL)
        rows = []
        for tr in trs:
            cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.DOTALL)
            cells = [re.sub(r"<.*?>", "", c).strip() for c in cells]
            rows.append(cells)

        if len(rows) < 2:
            continue

        header = rows[0]
        if len(header) < 13:
            continue

        # 解析 6 隊的資料 row（依 rank 1-6 順序）
        for idx, row in enumerate(rows[1:], start=1):
            if idx > 6:  # 只取前 6 隊
                break
            if len(row) < 13:
                continue

            # 從該 row 原始 HTML 抓出隊名（cell 0 內是 <a href...>隊名</a>）
            # row[0] 已被 strip，所以用原始 HTML 來找
            tr_html = trs[idx]  # idx 是 row 在 trs 內的索引
            anchor_match = re.search(r"<a[^>]*>([^<]+)</a>", tr_html)
            if anchor_match:
                team_cn = anchor_match.group(1).strip()
            else:
                team_cn = row[0].strip()

            if not team_cn or team_cn not in TEAM_CN_TO_EN:
                continue

            # 解析 W-T-L
            rank = idx
            games = row[1]
            wl_record = row[2]
            win_pct = row[3]
            gb = row[4]
            # 對戰欄位 6-11 (6 個)
            # 主場 12, 客場 13, 連勝 14, 近十場 15
            home = row[12] if len(row) > 12 else ""
            away = row[13] if len(row) > 13 else ""
            streak = row[14] if len(row) > 14 else ""
            l10 = row[15] if len(row) > 15 else ""

            parts = wl_record.split("-")
            try:
                wins = int(parts[0])
                ties = int(parts[1]) if len(parts) > 1 else 0
                losses = int(parts[2]) if len(parts) > 2 else 0
            except (ValueError, IndexError):
                continue

            def parse_wlt(s):
                if not s or "-" not in s:
                    return 0, 0, 0
                p = s.split("-")
                try:
                    return (
                        int(p[0]) if len(p) > 0 else 0,
                        int(p[1]) if len(p) > 1 else 0,
                        int(p[2]) if len(p) > 2 else 0,
                    )
                except (ValueError, IndexError):
                    return 0, 0, 0

            h_w, h_t, h_l = parse_wlt(home)
            a_w, a_t, a_l = parse_wlt(away)
            l10_w, l10_t, l10_l = parse_wlt(l10)

            try:
                pct_val = float(win_pct)
            except ValueError:
                pct_val = 0.0

            teams.append({
                "team_en": TEAM_CN_TO_EN[team_cn],
                "team_cn": team_cn,
                "rank": rank,
                "games_played": int(games) if games else 0,
                "wins": wins,
                "ties": ties,
                "losses": losses,
                "pct": pct_val,
                "home_wins": h_w,
                "home_ties": h_t,
                "home_losses": h_l,
                "away_wins": a_w,
                "away_ties": a_t,
                "away_losses": a_l,
                "l10_wins": l10_w,
                "l10_ties": l10_t,
                "l10_losses": l10_l,
                "streak_text": streak,
            })
    return teams


def ensure_table(cur, conn) -> None:
    """建立 cpbl_team_standings 表（含 half_season 欄位），並處理舊表遷移。"""
    # 1. 檢查表是否存在
    cur.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'predictx' AND table_name = 'cpbl_team_standings'
        ) as exists
    """)
    table_exists = cur.fetchone()['exists']

    if not table_exists:
        cur.execute("""
            CREATE TABLE predictx.cpbl_team_standings (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                team_id UUID NOT NULL REFERENCES predictx.teams(team_id),
                season INT NOT NULL,
                half_season INT NOT NULL DEFAULT 0,
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
                UNIQUE(team_id, season, half_season)
            );

            CREATE INDEX idx_cpbl_team_standings_season
                ON predictx.cpbl_team_standings (season, half_season);
        """)
        conn.commit()
        return

    # 2. 表存在：檢查 half_season 欄位
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = 'predictx' AND table_name = 'cpbl_team_standings'
        AND column_name = 'half_season'
    """)
    has_half_season = cur.fetchone()

    if not has_half_season:
        cur.execute("""
            ALTER TABLE predictx.cpbl_team_standings
            ADD COLUMN half_season INT NOT NULL DEFAULT 0
        """)
        conn.commit()

    # 3. 加 index
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_cpbl_team_standings_season
            ON predictx.cpbl_team_standings (season, half_season)
    """)
    conn.commit()

    # 4. 確保 unique constraint 是 (team_id, season, half_season)
    cur.execute("""
        SELECT conname FROM pg_constraint
        WHERE conrelid = 'predictx.cpbl_team_standings'::regclass
        AND contype = 'u'
    """)
    existing_constraints = [r['conname'] for r in cur.fetchall()]

    if 'cpbl_team_standings_team_id_season_half_key' not in existing_constraints:
        for old_constraint in ['cpbl_team_standings_team_id_season_key']:
            if old_constraint in existing_constraints:
                try:
                    cur.execute(f"ALTER TABLE predictx.cpbl_team_standings DROP CONSTRAINT {old_constraint}")
                    conn.commit()
                except Exception:
                    conn.rollback()
        try:
            cur.execute("""
                ALTER TABLE predictx.cpbl_team_standings
                ADD CONSTRAINT cpbl_team_standings_team_id_season_half_key
                UNIQUE (team_id, season, half_season)
            """)
            conn.commit()
        except Exception:
            conn.rollback()



def map_team_id(team_en: str, cur) -> Optional[str]:
    """將 team_en 對應到 predictx.teams.team_id。"""
    cur.execute(
        "SELECT team_id, english_name FROM predictx.teams WHERE league = %s",
        (LEAGUE_CODE,),
    )
    rows = cur.fetchall()
    target = team_en.lower()

    for r in rows:
        if (r["english_name"] or "").lower() == target:
            return r["team_id"]
    for r in rows:
        db_name = (r["english_name"] or "").lower()
        if target in db_name or db_name in target:
            return r["team_id"]

    return None


def upsert_team_standing(cur, team_id: str, season: int, half_season: int, data: dict) -> str:
    """寫入或更新球隊戰績。"""
    cur.execute("""
        SELECT id FROM predictx.cpbl_team_standings
        WHERE team_id = %s AND season = %s AND half_season = %s
    """, (team_id, season, half_season))
    existing = cur.fetchone()

    if existing:
        cur.execute("""
            UPDATE predictx.cpbl_team_standings
            SET rank = %s, games_played = %s, wins = %s, losses = %s, ties = %s, pct = %s,
                home_wins = %s, home_losses = %s, home_ties = %s,
                away_wins = %s, away_losses = %s, away_ties = %s,
                l10_wins = %s, l10_losses = %s, l10_ties = %s,
                streak_text = %s, source = %s, updated_at = NOW()
            WHERE team_id = %s AND season = %s AND half_season = %s
        """, (
            data["rank"], data["games_played"], data["wins"], data["losses"], data["ties"], data["pct"],
            data["home_wins"], data["home_losses"], data["home_ties"],
            data["away_wins"], data["away_losses"], data["away_ties"],
            data["l10_wins"], data["l10_losses"], data["l10_ties"],
            data["streak_text"], "cpbl.com.tw",
            team_id, season, half_season,
        ))
        return "UPDATE"

    cur.execute("""
        INSERT INTO predictx.cpbl_team_standings (
            team_id, season, half_season, rank, games_played,
            wins, losses, ties, pct,
            home_wins, home_losses, home_ties,
            away_wins, away_losses, away_ties,
            l10_wins, l10_losses, l10_ties,
            streak_text, source, updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
    """, (
        team_id, season, half_season, data["rank"], data["games_played"],
        data["wins"], data["losses"], data["ties"], data["pct"],
        data["home_wins"], data["home_losses"], data["home_ties"],
        data["away_wins"], data["away_losses"], data["away_ties"],
        data["l10_wins"], data["l10_losses"], data["l10_ties"],
        data["streak_text"], "cpbl.com.tw",
    ))
    return "INSERT"


def run(season: int = 2026, halfs: str = "1,2,0", dry_run: bool = False) -> dict:
    result = {"teams_fetched": 0, "teams_inserted": 0, "teams_updated": 0, "errors": []}

    halfs_list = [int(h) for h in halfs.split(",") if h.strip()]
    halfs_label = {0: "全年度", 1: "上半季", 2: "下半季"}

    client = CPBLClient()
    all_seasons_data = {}

    for half_season in halfs_list:
        label = halfs_label[half_season]
        logger.info(f"抓取 CPBL {season} {label} (seasonCode={half_season}) ...")
        html = client.fetch_season(half_season)
        if not html:
            result["errors"].append(f"{label} 抓取失敗")
            continue

        teams = parse_standings_table(html)
        logger.info(f"  解析出 {len(teams)} 隊")
        if len(teams) != 6:
            result["errors"].append(f"{label} 解析異常（只 {len(teams)} 隊）")
        all_seasons_data[half_season] = teams
        time.sleep(1)  # 禮貌延遲

    result["teams_fetched"] = sum(len(v) for v in all_seasons_data.values())

    if dry_run:
        logger.info(f"\n=== DRY-RUN 模式：不寫入 DB ===")
        for half_season, teams in all_seasons_data.items():
            label = halfs_label[half_season]
            logger.info(f"\n[{label}]")
            for t in teams:
                logger.info(
                    f"  #{t['rank']} {t['team_cn']:10} {t['team_en']:35} "
                    f"W:{t['wins']:>3} L:{t['losses']:>3} T:{t['ties']:>2} "
                    f"PCT:{t['pct']:.3f} G:{t['games_played']} "
                    f"Home:{t['home_wins']}-{t['home_losses']} Away:{t['away_wins']}-{t['away_losses']} "
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
        ensure_table(cur, conn)
        conn.commit()
    except Exception as e:
        result["errors"].append(f"建表失敗: {e}")
        logger.error(f"❌ 建表失敗: {e}")
        conn.rollback()
        cur.close()
        conn.close()
        return result

    for half_season, teams in all_seasons_data.items():
        label = halfs_label[half_season]
        logger.info(f"\n寫入 [{label}] ...")
        for t in teams:
            try:
                team_id = map_team_id(t["team_en"], cur)
                if not team_id:
                    result["errors"].append(f"找不到 team: {t['team_en']}")
                    logger.warning(f"  ⚠️ 找不到 team: {t['team_en']}")
                    continue

                action = upsert_team_standing(cur, team_id, season, half_season, t)
                if action == "INSERT":
                    result["teams_inserted"] += 1
                    verb = "NEW"
                else:
                    result["teams_updated"] += 1
                    verb = "UPD"
                logger.info(
                    f"  {verb} #{t['rank']} {t['team_cn']:10} {t['team_en']:35} "
                    f"W:{t['wins']:>3} L:{t['losses']:>3} T:{t['ties']:>2} PCT:{t['pct']:.3f}"
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
    p.add_argument("--half", type=str, default="1,2,0",
                   help="要抓的 season，逗號分隔：1=上半季, 2=下半季, 0=全年度")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    out = run(season=args.season, halfs=args.half, dry_run=args.dry_run)
    print("\n=== 結果 ===")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    sys.exit(0 if not out.get("errors") else 1)
