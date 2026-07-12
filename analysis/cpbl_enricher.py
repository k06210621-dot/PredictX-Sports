"""
cpbl_enricher.py
===============
CPBL 資料擴充模組 — 從 TheSportsDB 獲取 CPBL 賽事資料，
計算球隊近期表現、對戰紀錄等，豐富 AI prompt 的資料量。

使用 eventsseason.php 單次呼叫（快速），僅對最近 7 天用 eventsday.php 補充。
"""

import json
import logging
import os
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import requests

LOGGER = logging.getLogger("cpbl-enricher")

THESPORTSDB_KEY = os.getenv("THESPORTSDB_API_KEY", "123")
CPBL_LEAGUE_ID = "5111"
API_BASE = "https://www.thesportsdb.com/api/v1/json"

CPBL_TEAMS = [
    "CTBC Brothers", "Fubon Guardians", "Rakuten Monkeys",
    "Uni-President 7-ELEVEn Lions", "Wei Chuan Dragons", "TSG Hawks",
]

TEAM_NAME_ZH = {
    "CTBC Brothers": "中信兄弟", "Fubon Guardians": "富邦悍將",
    "Rakuten Monkeys": "樂天桃猿", "Uni-President 7-ELEVEn Lions": "統一7-ELEVEn獅",
    "Wei Chuan Dragons": "味全龍", "TSG Hawks": "台鋼雄鷹",
}


class CPBLEnricher:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "application/json",
        })
        self._all_events: Optional[List[Dict]] = None

    def _fetch_season(self) -> List[Dict]:
        """單次呼叫 eventsseason.php 取得整季賽事"""
        url = f"{API_BASE}/{THESPORTSDB_KEY}/eventsseason.php"
        try:
            resp = self.session.get(url, params={"id": CPBL_LEAGUE_ID, "s": "2026"}, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("events", []) or []
        except Exception as e:
            LOGGER.warning(f"CPBL season fetch failed: {e}")
        return []

    def _fetch_recent_days(self, days: int = 7) -> List[Dict]:
        """補充最近 N 天的賽事（eventsseason.php 可能漏掉）"""
        events = []
        for i in range(days):
            d = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            url = f"{API_BASE}/{THESPORTSDB_KEY}/eventsday.php"
            try:
                resp = self.session.get(url, params={"d": d, "l": CPBL_LEAGUE_ID}, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    day_events = data.get("events", []) or []
                    events.extend(day_events)
            except Exception:
                pass
            time.sleep(0.2)
        return events

    def get_all_events(self) -> List[Dict]:
        """取得所有 CPBL 賽事（含快取）"""
        if self._all_events is not None:
            return self._all_events

        season = self._fetch_season()
        recent = self._fetch_recent_days(7)

        # 合併去重（以 idEvent 為 key）
        seen = set()
        merged = []
        for e in recent + season:
            eid = e.get("idEvent", "")
            if eid and eid not in seen:
                seen.add(eid)
                merged.append(e)

        self._all_events = merged
        return merged

    def get_team_recent_form(self, team_name: str, games: int = 10) -> Dict:
        events = self.get_all_events()
        team_games = []
        for e in events:
            home = e.get("strHomeTeam", "")
            away = e.get("strAwayTeam", "")
            if home != team_name and away != team_name:
                continue
            hs = e.get("intHomeScore")
            aws = e.get("intAwayScore")
            if hs is None or aws is None:
                continue
            team_games.append(e)

        team_games.sort(key=lambda x: x.get("dateEvent", ""), reverse=True)
        recent_n = team_games[:games]

        wins = losses = runs_for = runs_against = 0
        last_5 = []

        for g in recent_n:
            home = g.get("strHomeTeam", "")
            hs = int(g.get("intHomeScore", 0))
            aws = int(g.get("intAwayScore", 0))
            if home == team_name:
                if hs > aws:
                    wins += 1; last_5.append("W")
                else:
                    losses += 1; last_5.append("L")
                runs_for += hs; runs_against += aws
            else:
                if aws > hs:
                    wins += 1; last_5.append("W")
                else:
                    losses += 1; last_5.append("L")
                runs_for += aws; runs_against += hs

        total = wins + losses
        return {
            "team": team_name, "team_zh": TEAM_NAME_ZH.get(team_name, team_name),
            "games": total, "wins": wins, "losses": losses,
            "win_pct": round(wins / total, 3) if total > 0 else 0.0,
            "runs_for": runs_for, "runs_against": runs_against,
            "run_diff": runs_for - runs_against,
            "last_5": "".join(last_5[:5]) if last_5 else "",
            "avg_runs_scored": round(runs_for / total, 1) if total > 0 else 0,
            "avg_runs_allowed": round(runs_against / total, 1) if total > 0 else 0,
        }

    def get_head_to_head(self, team1: str, team2: str, games: int = 5) -> Dict:
        events = self.get_all_events()
        h2h = []
        for e in events:
            home = e.get("strHomeTeam", "")
            away = e.get("strAwayTeam", "")
            if {home, away} != {team1, team2}:
                continue
            hs = e.get("intHomeScore")
            aws = e.get("intAwayScore")
            if hs is None or aws is None:
                continue
            h2h.append(e)

        h2h.sort(key=lambda x: x.get("dateEvent", ""), reverse=True)
        recent = h2h[:games]

        t1_wins = t2_wins = 0
        results = []
        for g in recent:
            home = g.get("strHomeTeam", "")
            hs = int(g.get("intHomeScore", 0))
            aws = int(g.get("intAwayScore", 0))
            winner = home if hs > aws else g.get("strAwayTeam", "")
            if winner == team1:
                t1_wins += 1; results.append(f"{g.get('dateEvent','')}: {team1} 勝")
            else:
                t2_wins += 1; results.append(f"{g.get('dateEvent','')}: {team2} 勝")

        return {
            "team1": team1, "team2": team2, "games": len(recent),
            "team1_wins": t1_wins, "team2_wins": t2_wins, "recent_results": results,
        }

    def build_prompt_section(self, home_team: str, away_team: str) -> str:
        home_form = self.get_team_recent_form(home_team)
        away_form = self.get_team_recent_form(away_team)
        h2h = self.get_head_to_head(home_team, away_team)

        lines = [
            "===== CPBL 擴充資料（TheSportsDB）=====", "",
            f"【{TEAM_NAME_ZH.get(home_team, home_team)} 近 {home_form['games']} 場】",
            f"  戰績: {home_form['wins']}-{home_form['losses']}  勝率: {home_form['win_pct']:.3f}",
            f"  近 5 場: {home_form['last_5']}  得失分差: {home_form['run_diff']:+d}",
            f"  場均得分: {home_form['avg_runs_scored']}  場均失分: {home_form['avg_runs_allowed']}",
            "",
            f"【{TEAM_NAME_ZH.get(away_team, away_team)} 近 {away_form['games']} 場】",
            f"  戰績: {away_form['wins']}-{away_form['losses']}  勝率: {away_form['win_pct']:.3f}",
            f"  近 5 場: {away_form['last_5']}  得失分差: {away_form['run_diff']:+d}",
            f"  場均得分: {away_form['avg_runs_scored']}  場均失分: {away_form['avg_runs_allowed']}",
            "",
            f"【近期對戰】{home_team} {h2h['team1_wins']} 勝 - {away_team} {h2h['team2_wins']} 勝",
        ]
        for r in h2h.get("recent_results", []):
            lines.append(f"  {r}")

        return "\n".join(lines)


_enricher: Optional[CPBLEnricher] = None


def get_cpbl_enricher() -> CPBLEnricher:
    global _enricher
    if _enricher is None:
        _enricher = CPBLEnricher()
    return _enricher


def build_cpbl_prompt_section(home_team: str, away_team: str) -> str:
    return get_cpbl_enricher().build_prompt_section(home_team, away_team)


if __name__ == "__main__":
    enricher = CPBLEnricher()
    section = enricher.build_prompt_section("Fubon Guardians", "Rakuten Monkeys")
    print(section)
    print(f"\n總字數: {len(section)}")