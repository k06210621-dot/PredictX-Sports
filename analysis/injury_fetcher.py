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
    else:
        # CPBL/NPB 暫不支援
        return {"home": [], "away": []}
