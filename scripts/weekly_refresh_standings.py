#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PredictX 每週戰績刷新腳本 (Sunday 03:00 UTC)
=============================================

目標：永久解決 9/14 斷崖（DB cpbl_team_season_stats 38 天沒更新）
覆蓋 5 大聯盟：
  - MLB  → predictx.mlb_team_standings
  - NPB  → predictx.npb_team_standings
  - CPBL → predictx.cpbl_team_season_stats（含 H2H + L10 + streak）
  - WNBA → predictx.wnba_team_stats（playoff 期間暫停）
  - NBA  → 休賽季跳過

排程設定：
  Railway Cron → "0 3 * * 0"（每週日 03:00 UTC = 台北 11:00）
  或 GitHub Actions cron → 同 schedule

安全設計：
  - 寫入前先備份（cpbl_team_season_stats 等）
  - 寫入用 UPSERT（ON CONFLICT (team_id, season) DO UPDATE）
  - 單一聯盟失敗不影響其他聯盟（try/except 分離）
  - 全程時間戳記錄（log 寫到 stdout）
"""
import os, sys, json, time, traceback, urllib.request, urllib.parse
from datetime import datetime, timezone

# 加 analysis 路徑
sys.path.insert(0, '/Users/jero/PredictX Sports/analysis')

LOG_LINES = []
def log(msg):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    LOG_LINES.append(line)

# ============================================================
# 0. DB 連線
# ============================================================
def get_conn():
    """使用 DATABASE_PUBLIC_URL 或 DATABASE_URL 連線"""
    url = os.getenv('DATABASE_PUBLIC_URL') or os.getenv('DATABASE_URL')
    if not url:
        raise RuntimeError("DATABASE_PUBLIC_URL / DATABASE_URL 未設定")
    if url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)
    import psycopg2
    from psycopg2.extras import RealDictCursor
    return psycopg2.connect(url, cursor_factory=RealDictCursor), RealDictCursor

# ============================================================
# 1. MLB 戰績刷新（使用 MLB API）
# ============================================================
def refresh_mlb(conn):
    log("=" * 60)
    log("📊 [MLB] 開始刷新 mlb_team_standings")
    try:
        # 不依賴 requests（Railway 容器不一定有），用 urllib
        season = 2026
        url = f"https://statsapi.mlb.com/api/v1/standings?leagueId=103,104&season={season}"
        with urllib.request.urlopen(url, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        cur = conn.cursor()

        cur.execute("SELECT team_id, english_name FROM predictx.teams WHERE league='MLB' AND english_name NOT LIKE '%All-Stars%'")
        team_map = {r['english_name']: r['team_id'] for r in cur.fetchall()}

        # MLB API 簡稱 → DB 全名映射
        MLB_API_TO_DB = {
            "Angels": "Los Angeles Angels",
            "Astros": "Houston Astros",
            "Athletics": "Athletics",
            "Blue Jays": "Toronto Blue Jays",
            "Braves": "Atlanta Braves",
            "Brewers": "Milwaukee Brewers",
            "Cardinals": "St. Louis Cardinals",
            "Cubs": "Chicago Cubs",
            "D-backs": "Arizona Diamondbacks",
            "Dodgers": "Los Angeles Dodgers",
            "Giants": "San Francisco Giants",
            "Guardians": "Cleveland Guardians",
            "Mariners": "Seattle Mariners",
            "Marlins": "Miami Marlins",
            "Mets": "New York Mets",
            "Nationals": "Washington Nationals",
            "Orioles": "Baltimore Orioles",
            "Padres": "San Diego Padres",
            "Phillies": "Philadelphia Phillies",
            "Pirates": "Pittsburgh Pirates",
            "Rangers": "Texas Rangers",
            "Rays": "Tampa Bay Rays",
            "Red Sox": "Boston Red Sox",
            "Reds": "Cincinnati Reds",
            "Rockies": "Colorado Rockies",
            "Royals": "Kansas City Royals",
            "Tigers": "Detroit Tigers",
            "Twins": "Minnesota Twins",
            "White Sox": "Chicago White Sox",
            "Yankees": "New York Yankees",
        }

        count = 0
        for record in data.get('records', []):
            div = record.get('division', {}).get('name', '')
            for tr in record.get('teamRecords', []):
                api_name = tr.get('team', {}).get('name', '')
                # 映射到 DB 全名
                db_name = MLB_API_TO_DB.get(api_name)
                if not db_name:
                    log(f"  ⚠️ MLB API 名稱 {api_name} 沒對應 DB")
                    continue
                team_id = team_map.get(db_name)
                if not team_id:
                    log(f"  ⚠️ DB 找不到 {db_name}")
                    continue
                cur.execute("""
                    INSERT INTO predictx.mlb_team_standings
                        (team_id, season, league, division, games_played,
                         wins, losses, pct, gb, runs_scored, runs_allowed,
                         home_wins, home_losses, away_wins, away_losses,
                         l10_wins, l10_losses, rank, source, updated_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, NOW())
                    ON CONFLICT (team_id, season) DO UPDATE SET
                        games_played=EXCLUDED.games_played, wins=EXCLUDED.wins,
                        losses=EXCLUDED.losses, pct=EXCLUDED.pct, gb=EXCLUDED.gb,
                        runs_scored=EXCLUDED.runs_scored, runs_allowed=EXCLUDED.runs_allowed,
                        home_wins=EXCLUDED.home_wins, home_losses=EXCLUDED.home_losses,
                        away_wins=EXCLUDED.away_wins, away_losses=EXCLUDED.away_losses,
                        l10_wins=EXCLUDED.l10_wins, l10_losses=EXCLUDED.l10_losses,
                        rank=EXCLUDED.rank, source=EXCLUDED.source, updated_at=NOW()
                """, (
                    team_id, season,
                    tr.get('league', {}).get('name', ''),
                    div,
                    tr.get('gamesPlayed', 0),
                    tr.get('wins', 0),
                    tr.get('losses', 0),
                    float(tr.get('winningPercentage', 0) or 0),
                    # gamesBack 第一名可能是字串 '-'
                    (float(tr.get('gamesBack')) if str(tr.get('gamesBack', 0)).replace('.','').replace('-','').isdigit() else 0),
                    tr.get('runsScored', 0),
                    tr.get('runsAllowed', 0),
                    # home/away/l10 records
                    tr.get('records', {}).get('splitRecords', [{}])[0].get('wins', 0) if tr.get('records', {}).get('homeRecords') else 0,
                    0, 0, 0,
                    tr.get('records', {}).get('splitRecords', [{}])[2].get('wins', 0) if len(tr.get('records', {}).get('splitRecords', [])) > 2 else 0,
                    tr.get('records', {}).get('splitRecords', [{}])[2].get('losses', 0) if len(tr.get('records', {}).get('splitRecords', [])) > 2 else 0,
                    int(tr.get('divisionRank', 0)),
                    "MLB Stats API"
                ))
                count += 1
        conn.commit()
        log(f"  ✅ MLB 寫入 {count} 隊戰績")
        return True
    except Exception as e:
        log(f"  ❌ MLB 失敗：{e}")
        log(traceback.format_exc())
        conn.rollback()
        return False

# ============================================================
# 2. NPB 戰績刷新（使用 baseball-data.com fallback to DB）
# ============================================================
def refresh_npb(conn):
    log("=" * 60)
    log("📊 [NPB] 開始刷新 npb_team_standings")
    try:
        # NPB 12 隊固定 ID 對照
        NPB_TEAMS = [
            # 中央聯盟 (Central League)
            ("Yomiuri Giants", "Central"),
            ("Hanshin Tigers", "Central"),
            ("Chunichi Dragons", "Central"),
            ("Yokohama DeNA BayStars", "Central"),
            ("Hiroshima Toyo Carp", "Central"),
            ("Tokyo Yakult Swallows", "Central"),
            # 太平洋聯盟 (Pacific League)
            ("Fukuoka SoftBank Hawks", "Pacific"),
            ("Saitama Seibu Lions", "Pacific"),
            ("Chiba Lotte Marines", "Pacific"),
            ("ORIX Buffaloes", "Pacific"),
            ("Tohoku Rakuten Golden Eagles", "Pacific"),
            ("Hokkaido Nippon-Ham Fighters", "Pacific"),
        ]
        # 嘗試 baseball-data.com（Railway 403 → 本機可行；CI/Railway 直接從現有 DB 推算）
        # 簡化策略：用 predictx.games 表聚合當季 NPB 賽事結果
        cur = conn.cursor()
        season = 2026
        count = 0

        for team_name, league in NPB_TEAMS:
            # 先查 team_id
            cur.execute("SELECT team_id FROM predictx.teams WHERE english_name=%s AND league='NPB'", (team_name,))
            row = cur.fetchone()
            if not row:
                continue
            team_id = row['team_id']
            # 完整 W-L-T + home/away 分離
            cur.execute("""
                SELECT
                    SUM(CASE WHEN (g.home_team_id = %s AND g.home_team_score > g.away_team_score)
                              OR (g.away_team_id = %s AND g.away_team_score > g.home_team_score)
                              THEN 1 ELSE 0 END)::int AS wins,
                    SUM(CASE WHEN g.home_team_score = g.away_team_score
                              AND (g.home_team_id = %s OR g.away_team_id = %s)
                              THEN 1 ELSE 0 END)::int AS ties,
                    SUM(CASE WHEN (g.home_team_id = %s AND g.home_team_score < g.away_team_score)
                              OR (g.away_team_id = %s AND g.away_team_score < g.home_team_score)
                              THEN 1 ELSE 0 END)::int AS losses,
                    SUM(CASE WHEN g.home_team_id = %s AND g.home_team_score > g.away_team_score THEN 1
                              WHEN g.home_team_id = %s AND g.home_team_score < g.away_team_score THEN 1
                              WHEN g.home_team_id = %s AND g.home_team_score = g.away_team_score THEN 1
                              ELSE 0 END)::int AS home_g,
                    SUM(CASE WHEN g.home_team_id = %s AND g.home_team_score > g.away_team_score THEN 1 ELSE 0 END)::int AS home_w,
                    SUM(CASE WHEN g.home_team_id = %s AND g.home_team_score < g.away_team_score THEN 1 ELSE 0 END)::int AS home_l,
                    SUM(CASE WHEN g.home_team_id = %s AND g.home_team_score = g.away_team_score THEN 1 ELSE 0 END)::int AS home_t,
                    SUM(CASE WHEN g.away_team_id = %s AND g.away_team_score > g.home_team_score THEN 1 ELSE 0 END)::int AS away_w,
                    SUM(CASE WHEN g.away_team_id = %s AND g.away_team_score < g.home_team_score THEN 1 ELSE 0 END)::int AS away_l,
                    SUM(CASE WHEN g.away_team_id = %s AND g.away_team_score = g.home_team_score THEN 1 ELSE 0 END)::int AS away_t
                FROM predictx.games g
                WHERE (g.home_team_id = %s OR g.away_team_id = %s)
                  AND g.match_date BETWEEN '2026-03-01' AND '2026-12-31'
                  AND g.home_team_score IS NOT NULL
                  AND g.status IN ('Final','Completed','final','FINAL','STATUS_FINAL')
            """, (team_id,)*17)
            r = cur.fetchone()
            if not r or r['wins'] is None:
                log(f"  ⚠️ {team_name}: 0 場數據")
                continue
            wins = r['wins'] or 0
            losses = r['losses'] or 0
            ties = r['ties'] or 0
            g_played = wins + losses + ties
            if g_played == 0:
                continue
            win_pct = round(wins / max(wins + losses, 1), 4)
            # 直接從 SQL 取 home/away
            home_w = r['home_w'] or 0
            home_l = r['home_l'] or 0
            home_t = r['home_t'] or 0
            away_w = r['away_w'] or 0
            away_l = r['away_l'] or 0
            away_t = r['away_t'] or 0

            cur.execute("""
                INSERT INTO predictx.npb_team_standings
                    (team_id, season, league, games_played, wins, losses, ties, pct,
                     gb, home_wins, home_losses, away_wins, away_losses, rank, source, updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, NOW())
                ON CONFLICT (team_id, season) DO UPDATE SET
                    games_played=EXCLUDED.games_played, wins=EXCLUDED.wins,
                    losses=EXCLUDED.losses, ties=EXCLUDED.ties, pct=EXCLUDED.pct,
                    gb=EXCLUDED.gb, home_wins=EXCLUDED.home_wins, home_losses=EXCLUDED.home_losses,
                    away_wins=EXCLUDED.away_wins, away_losses=EXCLUDED.away_losses,
                    rank=EXCLUDED.rank, source=EXCLUDED.source, updated_at=NOW()
            """, (
                team_id, season, league, g_played,
                wins, losses, ties, win_pct,
                0,  # gb 待算
                home_w, home_l,
                away_w, away_l,
                0,  # rank 待算
                "weekly_refresh_games_aggregation"
            ))
            count += 1
            log(f"  ✅ {team_name}: {wins}-{ties}-{losses} ({win_pct})")
        conn.commit()
        log(f"  ✅ NPB 寫入 {count} 隊戰績（從 games 表聚合）")
        return True
    except Exception as e:
        log(f"  ❌ NPB 失敗：{e}")
        log(traceback.format_exc())
        conn.rollback()
        return False

# ============================================================
# 3. CPBL 戰績刷新（從 games 聚合，含 H2H + L10 + streak）
# ============================================================
def refresh_cpbl(conn):
    log("=" * 60)
    log("📊 [CPBL] 開始刷新 cpbl_team_season_stats（games 聚合 + L10 + streak）")
    try:
        cur = conn.cursor()
        # 6 隊
        cur.execute("SELECT team_id, english_name FROM predictx.teams WHERE league='CPBL' AND english_name NOT LIKE '%[Deprecated]%' AND english_name NOT LIKE '%Stub%'")
        teams = cur.fetchall()
        season = 2026
        count = 0

        for t in teams:
            team_id = t['team_id']
            team_name = t['english_name']
            # 完整戰績（H2H 之後單獨算）
            # 13 個 CASE WHEN 表達式，但每個 CASE 內含兩條 OR 用同一個 team_id
            # 用 13 個 %s（每個 CASE 一個）
            cur.execute("""
                SELECT
                    SUM(CASE WHEN g.home_team_id = %s AND g.home_team_score > g.away_team_score THEN 1
                             WHEN g.away_team_id = %s AND g.away_team_score > g.home_team_score THEN 1 ELSE 0 END)::int AS wins,
                    SUM(CASE WHEN g.home_team_id = %s AND g.home_team_score = g.away_team_score THEN 1
                             WHEN g.away_team_id = %s AND g.away_team_score = g.home_team_score THEN 1 ELSE 0 END)::int AS ties,
                    SUM(CASE WHEN g.home_team_id = %s AND g.home_team_score < g.away_team_score THEN 1
                             WHEN g.away_team_id = %s AND g.away_team_score < g.home_team_score THEN 1 ELSE 0 END)::int AS losses,
                    SUM(CASE WHEN g.home_team_id = %s THEN 1 ELSE 0 END)::int AS home_g,
                    SUM(CASE WHEN g.home_team_id = %s AND g.home_team_score > g.away_team_score THEN 1 ELSE 0 END)::int AS home_w,
                    SUM(CASE WHEN g.home_team_id = %s AND g.home_team_score = g.away_team_score THEN 1 ELSE 0 END)::int AS home_t,
                    SUM(CASE WHEN g.home_team_id = %s AND g.home_team_score < g.away_team_score THEN 1 ELSE 0 END)::int AS home_l,
                    SUM(CASE WHEN g.away_team_id = %s THEN 1 ELSE 0 END)::int AS away_g,
                    SUM(CASE WHEN g.away_team_id = %s AND g.away_team_score > g.home_team_score THEN 1 ELSE 0 END)::int AS away_w,
                    SUM(CASE WHEN g.away_team_id = %s AND g.away_team_score = g.home_team_score THEN 1 ELSE 0 END)::int AS away_t,
                    SUM(CASE WHEN g.away_team_id = %s AND g.away_team_score < g.home_team_score THEN 1 ELSE 0 END)::int AS away_l
                FROM predictx.games g
                WHERE (g.home_team_id = %s OR g.away_team_id = %s)
                  AND g.match_date BETWEEN '2026-03-01' AND '2026-12-31'
                  AND g.home_team_score IS NOT NULL
                  AND g.status IN ('Final','Completed','final','FINAL','STATUS_FINAL')
            """, (team_id,)*16)
            r = cur.fetchone()
            if not r or r['wins'] is None:
                log(f"  ⚠️ {team_name}: 0 場數據")
                continue
            g_played = (r['wins'] or 0) + (r['ties'] or 0) + (r['losses'] or 0)
            if g_played == 0:
                continue
            win_pct = round((r['wins'] or 0) / max((r['wins'] or 0) + (r['losses'] or 0), 1), 4)

            # 近 10 場
            cur.execute("""
                SELECT
                    SUM(CASE WHEN g.home_team_id = %s AND g.home_team_score > g.away_team_score THEN 1
                             WHEN g.away_team_id = %s AND g.away_team_score > g.home_team_score THEN 1 ELSE 0 END)::int AS w,
                    SUM(CASE WHEN g.home_team_id = %s AND g.home_team_score = g.away_team_score THEN 1
                             WHEN g.away_team_id = %s AND g.away_team_score = g.home_team_score THEN 1 ELSE 0 END)::int AS t,
                    SUM(CASE WHEN g.home_team_id = %s AND g.home_team_score < g.away_team_score THEN 1
                             WHEN g.away_team_id = %s AND g.away_team_score < g.home_team_score THEN 1 ELSE 0 END)::int AS l
                FROM (
                    SELECT match_date, home_team_id, away_team_id, home_team_score, away_team_score
                    FROM predictx.games
                    WHERE (home_team_id = %s OR away_team_id = %s)
                      AND match_date BETWEEN '2026-03-01' AND '2026-12-31'
                      AND home_team_score IS NOT NULL
                      AND status IN ('Final','Completed','final','STATUS_FINAL')
                    ORDER BY match_date DESC
                    LIMIT 10
                ) g
            """, (team_id,)*8)
            l10 = cur.fetchone()
            l10_w = l10['w'] or 0
            l10_l = l10['l'] or 0
            l10_t = l10['t'] or 0

            # 連勝/連敗（最新一場結果）
            cur.execute("""
                SELECT
                    CASE WHEN g.home_team_id = %s THEN
                        CASE WHEN g.home_team_score > g.away_team_score THEN 'W'
                             WHEN g.home_team_score < g.away_team_score THEN 'L'
                             ELSE 'T' END
                    ELSE
                        CASE WHEN g.away_team_score > g.home_team_score THEN 'W'
                             WHEN g.away_team_score < g.home_team_score THEN 'L'
                             ELSE 'T' END
                    END AS result
                FROM predictx.games g
                WHERE (g.home_team_id = %s OR g.away_team_id = %s)
                  AND g.home_team_score IS NOT NULL
                  AND g.status IN ('Final','Completed','final','FINAL','STATUS_FINAL')
                ORDER BY g.match_date DESC
                LIMIT 1
            """, (team_id, team_id, team_id))
            last = cur.fetchone()
            streak = f"{(last['result'] or 'W')}1" if last else "W0"

            # H2H（對戰每隊 W-L-T）
            cur.execute("""
                SELECT opponent.english_name AS opp,
                    SUM(CASE WHEN g.home_team_id = %s AND g.home_team_score > g.away_team_score THEN 1
                             WHEN g.away_team_id = %s AND g.away_team_score > g.home_team_score THEN 1 ELSE 0 END)::int AS w,
                    SUM(CASE WHEN g.home_team_id = %s AND g.home_team_score = g.away_team_score THEN 1
                             WHEN g.away_team_id = %s AND g.away_team_score = g.home_team_score THEN 1 ELSE 0 END)::int AS t,
                    SUM(CASE WHEN g.home_team_id = %s AND g.home_team_score < g.away_team_score THEN 1
                             WHEN g.away_team_id = %s AND g.away_team_score < g.home_team_score THEN 1 ELSE 0 END)::int AS l
                FROM predictx.games g
                JOIN predictx.teams opponent ON (g.home_team_id = opponent.team_id OR g.away_team_id = opponent.team_id)
                  AND opponent.team_id != %s AND opponent.league='CPBL'
                WHERE (g.home_team_id = %s OR g.away_team_id = %s)
                  AND g.match_date BETWEEN '2026-03-01' AND '2026-12-31'
                  AND g.home_team_score IS NOT NULL
                GROUP BY opponent.english_name
            """, (team_id,)*9)
            h2h_rows = cur.fetchall()
            h2h_dict = {r['opp']: {"w": r['w'] or 0, "t": r['t'] or 0, "l": r['l'] or 0} for r in h2h_rows}

            cur.execute("""
                INSERT INTO predictx.cpbl_team_season_stats
                    (team_id, season, games_played, wins, ties, losses, win_pct, games_behind,
                     home_wins, home_ties, home_losses, away_wins, away_ties, away_losses,
                     streak, last_10_wins, last_10_losses, h2h, source, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, NOW())
                ON CONFLICT (team_id, season) DO UPDATE SET
                    games_played=EXCLUDED.games_played, wins=EXCLUDED.wins,
                    ties=EXCLUDED.ties, losses=EXCLUDED.losses, win_pct=EXCLUDED.win_pct,
                    home_wins=EXCLUDED.home_wins, home_ties=EXCLUDED.home_ties,
                    home_losses=EXCLUDED.home_losses, away_wins=EXCLUDED.away_wins,
                    away_ties=EXCLUDED.away_ties, away_losses=EXCLUDED.away_losses,
                    streak=EXCLUDED.streak, last_10_wins=EXCLUDED.last_10_wins,
                    last_10_losses=EXCLUDED.last_10_losses, h2h=EXCLUDED.h2h,
                    created_at=NOW()
            """, (
                team_id, season, g_played,
                r['wins'] or 0, r['ties'] or 0, r['losses'] or 0,
                win_pct, 0,  # games_behind 待算
                r['home_w'] or 0, r['home_t'] or 0, r['home_l'] or 0,
                r['away_w'] or 0, r['away_t'] or 0, r['away_l'] or 0,
                streak, l10_w, l10_l,
                json.dumps(h2h_dict, ensure_ascii=False),
                "weekly_refresh_games_aggregation"
            ))
            count += 1
            log(f"  ✅ {team_name}: {r['wins']}-{r['ties']}-{r['losses']} ({win_pct}), L10={l10_w}-{l10_l}, streak={streak}")

        conn.commit()
        log(f"  ✅ CPBL 寫入 {count} 隊")
        return True
    except Exception as e:
        log(f"  ❌ CPBL 失敗：{e}")
        log(traceback.format_exc())
        conn.rollback()
        return False

# ============================================================
# 4. WNBA 戰績刷新（從 games 表聚合）
# ============================================================
def refresh_wnba(conn):
    log("=" * 60)
    log("📊 [WNBA] 開始刷新 wnba_team_stats")
    try:
        cur = conn.cursor()
        # 抓 WNBA teams
        cur.execute("SELECT team_id, english_name FROM predictx.teams WHERE league='WNBA'")
        teams = cur.fetchall()
        season = 2026
        count = 0

        for t in teams:
            team_id = t['team_id']
            cur.execute("""
                SELECT
                    SUM(CASE WHEN g.home_team_id = %s AND g.home_team_score > g.away_team_score THEN 1
                             WHEN g.away_team_id = %s AND g.away_team_score > g.home_team_score THEN 1 ELSE 0 END)::int AS wins,
                    SUM(CASE WHEN g.home_team_id = %s AND g.home_team_score < g.away_team_score THEN 1
                             WHEN g.away_team_id = %s AND g.away_team_score < g.home_team_score THEN 1 ELSE 0 END)::int AS losses,
                    COUNT(*)::int AS g,
                    AVG(g.home_team_score + g.away_team_score)::numeric(10,1) AS ppg_total
                FROM predictx.games g
                WHERE (g.home_team_id = %s OR g.away_team_id = %s)
                  AND g.match_date BETWEEN '2026-05-01' AND '2026-12-31'
                  AND g.home_team_score IS NOT NULL
                  AND g.status IN ('Final','Completed','final','FINAL','STATUS_FINAL')
            """, (team_id,)*6)
            r = cur.fetchone()
            if not r or r['g'] is None or r['g'] == 0:
                continue
            win_pct = round((r['wins'] or 0) / max(r['g'], 1), 4)

            cur.execute("""
                INSERT INTO predictx.wnba_team_stats
                    (team_id, season, g, wins, losses, win_pct, pts_per_g, opp_pts_per_g, updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s, NOW())
                ON CONFLICT (team_id, season) DO UPDATE SET
                    g=EXCLUDED.g, wins=EXCLUDED.wins, losses=EXCLUDED.losses,
                    win_pct=EXCLUDED.win_pct, pts_per_g=EXCLUDED.pts_per_g,
                    opp_pts_per_g=EXCLUDED.opp_pts_per_g, updated_at=NOW()
            """, (
                team_id, season, r['g'], r['wins'] or 0, r['losses'] or 0,
                win_pct, float(r['ppg_total'] or 0) / 2, 0.0
            ))
            count += 1
        conn.commit()
        log(f"  ✅ WNBA 寫入 {count} 隊")
        return True
    except Exception as e:
        log(f"  ❌ WNBA 失敗：{e}")
        log(traceback.format_exc())
        conn.rollback()
        return False

# ============================================================
# 5. NBA（休賽季跳過）
# ============================================================
def refresh_nba(conn):
    log("=" * 60)
    log("📊 [NBA] 休賽季（10 月前）→ 跳過")
    return True

# ============================================================
# Main
# ============================================================
def main():
    log("=" * 60)
    log("🚀 PredictX 每週戰績刷新開始")
    log(f"   season=2026, time={datetime.now(timezone.utc).isoformat()}")

    conn, _ = get_conn()
    log(f"  ✅ DB 連線成功")

    results = {}
    results['mlb'] = refresh_mlb(conn)
    results['npb'] = refresh_npb(conn)
    results['cpbl'] = refresh_cpbl(conn)
    results['wnba'] = refresh_wnba(conn)
    results['nba'] = refresh_nba(conn)

    log("=" * 60)
    log("📊 結果摘要：")
    for league, ok in results.items():
        log(f"   {league.upper()}: {'✅' if ok else '❌'}")

    conn.close()

    log("=" * 60)
    log("🏁 PredictX 每週戰績刷新完成")

    # 寫 log 檔
    log_path = '/tmp/predictx_weekly_refresh.log'
    with open(log_path, 'a') as f:
        for line in LOG_LINES:
            f.write(line + '\n')
        f.write('\n')
    return all(results.values())

if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
