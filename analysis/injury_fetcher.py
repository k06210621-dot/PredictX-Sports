#!/usr/bin/env python3
"""
傷兵名單抓取器（MLB + NBA + WNBA）

資料源：
  MLB  — statsapi.mlb.com（roster 40-man，status code 直接標示 IL）
  NBA  — site.api.espn.com（injuries endpoint）
  WNBA — site.api.espn.com（injuries endpoint）

回傳格式：
  {
    "home": [{"name": "Mark Vientos", "status": "IL10", "desc": "Injured 10-Day", "date": "2026-07-10"}],
    "away": [...]
  }

如果無傷兵或抓取失敗，回傳 {"home": [], "away": []}
"""
import requests
import logging

_logger = logging.getLogger(__name__)

MLB_API_BASE = "https://statsapi.mlb.com/api/v1"
ESPN_INJURY_URLS = {
    "NBA":  "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries",
    "WNBA": "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/injuries",
}

# MLB status code → 人類可讀描述
_MLB_STATUS_MAP = {
    "D10": "IL 10-Day",
    "D15": "IL 15-Day",
    "D60": "IL 60-Day",
    "DAA": "Bereavement List",
    "RM":  "Reassigned to Minors",
    "A":   "Active",
}


def _normalize_team_name(name):
    """去除多餘空白、統一小寫以利比對。"""
    return (name or "").strip().lower()


def fetch_mlb_injuries(home_team_name, away_team_name):
    """
    從 MLB statsapi 抓 40-man roster，篩出 IL 球員。
    回傳 {"home": [...], "away": [...]}
    """
    result = {"home": [], "away": []}
    try:
        # 先拿全部 MLB teams，用名字比對出 teamId
        resp = requests.get(f"{MLB_API_BASE}/teams?sportId=1&season=2026", timeout=15)
        resp.raise_for_status()
        all_teams = resp.json().get("teams", [])
    except Exception as e:
        _logger.warning(f"MLB injuries: failed to fetch team list: {e}")
        return result

    # 為 home/away 分別找出 teamId
    targets = {}
    for side, name in [("home", home_team_name), ("away", away_team_name)]:
        norm = _normalize_team_name(name)
        for t in all_teams:
            full = _normalize_team_name(t.get("name", ""))
            short = _normalize_team_name(t.get("teamName", ""))
            loc = _normalize_team_name(t.get("locationName", ""))
            if norm and (norm in full or norm in short or norm in loc or full in norm or short in norm):
                targets[side] = t.get("id")
                break

    if not targets.get("home") and not targets.get("away"):
        _logger.warning(f"MLB injuries: could not match teams: {home_team_name} / {away_team_name}")
        return result

    for side, team_id in targets.items():
        if not team_id:
            continue
        try:
            resp = requests.get(
                f"{MLB_API_BASE}/teams/{team_id}/roster?rosterType=40Man&season=2026",
                timeout=15,
            )
            resp.raise_for_status()
            roster = resp.json().get("roster", [])
            for r in roster:
                person = r.get("person", {})
                status = r.get("status", {})
                code = status.get("code", "")
                # 只收 IL 相關
                if code and code.startswith("D") and code != "DAA":
                    desc = _MLB_STATUS_MAP.get(code, status.get("description", code))
                    result[side].append({
                        "name": person.get("fullName", "?"),
                        "status": code,
                        "desc": desc,
                        "position": r.get("position", {}).get("abbreviation", ""),
                        "date": "",
                    })
        except Exception as e:
            _logger.warning(f"MLB injuries: roster fetch failed for team {team_id}: {e}")

    return result


def fetch_espn_injuries(league, home_team_name, away_team_name):
    """
    從 ESPN 抓 NBA/WNBA 傷兵名單。
    回傳 {"home": [...], "away": [...]}
    """
    result = {"home": [], "away": []}
    url = ESPN_INJURY_URLS.get(league.upper())
    if not url:
        return result

    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        _logger.warning(f"ESPN injuries ({league}): fetch failed: {e}")
        return result

    teams = data.get("injuries", [])
    for side, target_name in [("home", home_team_name), ("away", away_team_name)]:
        norm = _normalize_team_name(target_name)
        for team_entry in teams:
            team_display = _normalize_team_name(team_entry.get("displayName", ""))
            if norm and (norm in team_display or team_display in norm):
                for inj in team_entry.get("injuries", []):
                    athlete = inj.get("athlete", {})
                    status = inj.get("status", "Unknown")
                    # 只收 Out / IL / Day-To-Day，不收 "Return to Action" 這種
                    if status and status.upper() in ("OUT", "IL", "IL10", "IL15", "IL60",
                                                      "DAY-TO-DAY", "INJURED LIST",
                                                      "QUESTIONABLE", "DOUBTFUL"):
                        result[side].append({
                            "name": athlete.get("displayName", "?"),
                            "status": status,
                            "desc": inj.get("shortComment", ""),
                            "date": inj.get("date", ""),
                        })
                break

    return result


def _cpbl_latest_moves():
    """抓 CPBL 官網球員異動，回傳 {(球員, 中文隊名): (日期, 原因)}（取最新一筆）。

    官網表格為「新→舊」排序，因此每位球員第一次出現即為最新異動。
    """
    import re
    from bs4 import BeautifulSoup

    HDR = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 Chrome/120 Safari/537.36",
        "Accept-Language": "zh-TW",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://www.cpbl.com.tw/player/trans",
    }
    s = requests.Session()
    r = s.get("https://www.cpbl.com.tw/player/trans", headers=HDR, timeout=25)
    soup = BeautifulSoup(r.text, "lxml")
    form = soup.find("form", id="MainForm") or soup.find("form")
    if not form:
        return {}
    fields = {el.get("name"): el.get("value", "")
              for el in form.find_all(["input", "select"]) if el.get("name")}
    resp = s.post("https://www.cpbl.com.tw/player/trans", data=fields, headers=HDR, timeout=30)
    sp = BeautifulSoup(resp.text, "lxml")
    table = sp.find("table")
    if not table:
        return {}

    latest = {}
    cur_date = None
    for tr in table.find_all("tr")[1:]:
        cells = [c.get_text(strip=True) for c in tr.find_all(["td", "th"])]
        if len(cells) >= 4:
            cur_date = cells[0]
            name, team, reason = cells[1], cells[2], cells[3]
        elif len(cells) == 3 and cur_date:
            name, team, reason = cells[0], cells[1], cells[2]
        else:
            continue
        name = name.lstrip('#').strip()
        key = (name, team)
        if key not in latest:          # 新→舊，第一次即最新
            latest[key] = (cur_date, reason)
    return latest


def _cpbl_unavailable_from_db(home_en, away_en):
    """從 predictx.cpbl_unavailable 讀取缺陣名單（生產環境主要來源）。

    Railway egress 對 CPBL 官網常被阻擋（實測解析 0 筆），
    故改由本機排程抓取後寫入 DB，引擎端只讀 DB。
    """
    import os
    try:
        import psycopg2
    except Exception:
        return None
    db_url = (os.getenv("DATABASE_PUBLIC_URL") or os.getenv("DATABASE_URL")
              or os.getenv("POSTGRES_URL") or "")
    if not db_url:
        return None
    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        cur.execute("""
            SELECT t.english_name, u.player_name, u.reason, u.move_date::text
            FROM predictx.cpbl_unavailable u
            JOIN predictx.teams t ON u.team_id = t.team_id
        """)
        rows = cur.fetchall()
        cur.close(); conn.close()
    except Exception as e:
        print(f"  ⚠ CPBL unavailable DB read failed: {type(e).__name__}: {str(e)[:80]}", flush=True)
        return None

    result = {"home": [], "away": []}
    for team_en, name, reason, move_date in rows:
        item = {
            "name": name,
            "status": reason,
            "desc": f"CPBL 官網球員異動：{reason}（{move_date}），已不在現行名單",
            "date": move_date,
        }
        if team_en == home_en:
            result["home"].append(item)
        elif team_en == away_en:
            result["away"].append(item)
    for side in ("home", "away"):
        result[side].sort(key=lambda x: x.get("date") or "", reverse=True)
    return result


def fetch_cpbl_unavailable(home_team_name, away_team_name):
    """CPBL 缺陣名單（保守版）。

    資料源：CPBL 官網「球員異動」。
    ⚠️ CPBL 無官方醫療傷兵名單；此處僅採**確定離開名單**的異動：
       「註銷 / 註冊註銷 / 除役」。
       「降二軍」不納入（僅為輪替，且官網資料可能落後於實際先發）。
    """
    CN2EN = {
        "中信兄弟": "CTBC Brothers",
        "樂天桃猿": "Rakuten Monkeys",
        "味全龍": "Wei Chuan Dragons",
        "富邦悍將": "Fubon Guardians",
        "台鋼雄鷹": "TSG Hawks",
        "統一7-ELEVEn獅": "Uni-President 7-ELEVEn Lions",
    }
    OUT_REASONS = ("註銷", "註冊註銷", "除役")
    home_en = (home_team_name or "").strip()
    away_en = (away_team_name or "").strip()

    # 1) 優先讀 DB 快取（生產環境可靠來源）
    db_res = _cpbl_unavailable_from_db(home_en, away_en)
    if db_res is not None:
        print(f"  [CPBL 缺陣] DB 快取：home={len(db_res['home'])} away={len(db_res['away'])}", flush=True)
        return db_res

    # 2) 備援：直接爬官網（僅在本機等可存取環境有效）
    result = {"home": [], "away": []}
    try:
        latest = _cpbl_latest_moves()
    except Exception as e:
        print(f"  ⚠ CPBL moves fetch failed: {type(e).__name__}: {str(e)[:120]}", flush=True)
        return result
    print(f"  [CPBL trans] 解析 {len(latest)} 名球員異動紀錄", flush=True)

    home_en = (home_team_name or "").strip()
    away_en = (away_team_name or "").strip()
    for (name, cn_team), (date_s, reason) in latest.items():
        if reason not in OUT_REASONS:
            continue
        en = CN2EN.get(cn_team)
        if not en:
            continue
        item = {
            "name": name,
            "status": reason,
            "desc": f"CPBL 官網球員異動：{reason}（{date_s}），已不在現行名單",
            "date": date_s.replace("/", "-"),
        }
        if en == home_en:
            result["home"].append(item)
        elif en == away_en:
            result["away"].append(item)

    for side in ("home", "away"):
        result[side].sort(key=lambda x: x.get("date") or "", reverse=True)
    return result


def fetch_injuries(league, home_team_name, away_team_name):
    """
    統一入口：依聯盟自動選擇資料源。
    回傳 {"home": [...], "away": [...]}
    """
    league = (league or "").upper()
    if league == "MLB":
        return fetch_mlb_injuries(home_team_name, away_team_name)
    elif league in ("NBA", "WNBA"):
        return fetch_espn_injuries(league, home_team_name, away_team_name)
    elif league == "CPBL":
        return fetch_cpbl_unavailable(home_team_name, away_team_name)
    else:
        # NPB 暫不支援
        return {"home": [], "away": []}
