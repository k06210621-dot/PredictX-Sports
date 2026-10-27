#!/usr/bin/env python3
"""
ingest/npb.py
=============
NPB fetcher — 從 npb.jp 月曆頁面抓全聯盟賽程

設計：
- 主來源：https://www.npb.jp/games/{year}/schedule_{MM}_detail.html
  （月曆總覽頁，含所有 12 隊、跨聯盟交流戰）
- 球隊名稱從 <div class="team1/team2"> 解析（日文簡稱）
- 比分從 <div class="score1/score2"> 解析
- 跨日：依日期 ID（dateMMDD）對應

優點：
- 一次抓整月（league_days_ahead 可達 30 天）
- 同時涵蓋中央聯盟 + 太平洋聯盟 + 跨聯盟交流戰
- 含已結束比賽的最終比分（用於 backfill_yesterday）
"""

import re
import logging
from typing import List, Dict, Any
from datetime import datetime
from bs4 import BeautifulSoup
from .base import BaseIngester

LOGGER = logging.getLogger("ingest.npb")

# NPB 月曆頁面 URL（month 為兩位數，含補零）
NPB_MONTHLY_URL = "https://www.npb.jp/games/{year}/schedule_{month}_detail.html"

# 日文球隊簡稱 → 英文全名 映射（從 <div class="team1"> 解析）
NPB_TEAMS_JP = {
    "巨人":      "Yomiuri Giants",
    "ヤクルト":  "Tokyo Yakult Swallows",
    "DeNA":      "Yokohama DeNA BayStars",
    "中日":      "Chunichi Dragons",
    "阪神":      "Hanshin Tigers",
    "広島":      "Hiroshima Toyo Carp",
    "日本ハム":   "Hokkaido Nippon-Ham Fighters",
    "ソフトバンク": "Fukuoka SoftBank Hawks",
    "ロッテ":     "Chiba Lotte Marines",
    "楽天":      "Tohoku Rakuten Golden Eagles",
    "オリックス":  "ORIX Buffaloes",
    "西武":      "Saitama Seibu Lions",
}


def _resolve_team(jp_short: str):
    """將日文簡稱映射為英文全名"""
    if not jp_short:
        return None
    jp_short = jp_short.strip()
    if jp_short in NPB_TEAMS_JP:
        return NPB_TEAMS_JP[jp_short]
    LOGGER.warning(f"NPB 無法識別球隊簡稱: {jp_short!r}")
    return None


class NPBIngester(BaseIngester):
    league_code = "NPB"
    league_days_ahead = 2  # 抓今天 + 未來 2 天
    source_name = "npb_official_monthly+yahoo_fallback"

    # 快取：避免同一個月重複抓取
    _cached_html: Dict[str, str] = {}
    _cached_soup: Dict[str, BeautifulSoup] = {}

    # 健全性檢查：太平洋聯盟球隊（確保日曆頁含跨聯盟賽事，非只抓中央聯盟）
    PACIFIC_LEAGUE_TEAMS = {
        "Hokkaido Nippon-Ham Fighters",
        "Fukuoka SoftBank Hawks",
        "Chiba Lotte Marines",
        "Tohoku Rakuten Golden Eagles",
        "ORIX Buffaloes",
        "Saitama Seibu Lions",
    }

    def _get_monthly_page(self, year: int, month: int):
        """抓取指定年月的月曆頁（帶快取）"""
        month_str = f"{month:02d}"
        cache_key = f"{year}-{month_str}"

        if cache_key in self._cached_soup:
            return self._cached_soup[cache_key]

        url = NPB_MONTHLY_URL.format(year=year, month=month_str)
        resp = self.session.get(url, timeout=8)
        if resp.status_code != 200:
            raise RuntimeError(f"NPB 月曆頁 HTTP {resp.status_code} ({url})")

        # NPB 月曆頁面使用 SHIFT_JIS 編碼（requests 預設用 ISO-8859-1 解碼會亂碼）
        resp.encoding = "shift_jis"
        html_text = resp.text

        # 嘗試以 UTF-8 解碼（現代 NPB 頁面多為 UTF-8），失敗則降級到 SHIFT_JIS
        try:
            html_text = resp.content.decode("utf-8")
        except UnicodeDecodeError:
            html_text = resp.content.decode("shift_jis", errors="replace")

        soup = BeautifulSoup(html_text, "lxml")
        self._cached_soup[cache_key] = soup
        self._cached_html[cache_key] = html_text
        LOGGER.info(f"NPB 載入月曆頁: {cache_key}")
        return soup

    def fetch_games(self, target_date: str) -> List[Dict[str, Any]]:
        """
        抓取指定日期的 NPB 全部賽事
        主來源：npb.jp 月曆頁（目前常態性連線逾時）
        備援：baseball.yahoo.co.jp 賽程頁（2026-10-27 實測可用）
        """
        try:
            return self._fetch_games_npb(target_date)
        except Exception as e:
            LOGGER.warning(f"NPB 官方月曆失敗（{target_date}）: {e} → 改用 Yahoo 備援")
            return self._fetch_games_yahoo(target_date)

    def _fetch_games_npb(self, target_date: str) -> List[Dict[str, Any]]:
        """
        抓取指定日期的 NPB 全部賽事（12 隊，含跨聯盟）

        來源頁面：https://www.npb.jp/games/{year}/schedule_{MM}_detail.html
        結構：每個 <tr id="dateMMDD"> 包含當天所有比賽
        """
        dt = datetime.strptime(target_date, "%Y-%m-%d")
        soup = self._get_monthly_page(dt.year, dt.month)

        # 找目標日期的 row：id="dateMMDD"
        date_id = f"date{dt.strftime('%m%d')}"
        rows = soup.find_all("tr", id=date_id)

        if not rows:
            LOGGER.info(f"NPB {target_date} 沒有賽事（休兵日）")
            return []

        LOGGER.info(f"NPB {target_date} 找到 {len(rows)} 場")

        games: List[Dict[str, Any]] = []
        for row in rows:
            game = self._parse_game_row(row, dt)
            if game:
                games.append(game)

        # 健全性檢查：若太平洋聯盟球隊都沒在抓取結果裡，可能是抓錯頁面（只抓到中央聯盟）
        team_set = set()
        for g in games:
            team_set.add(g["home_team"])
            team_set.add(g["away_team"])
        pacific_present = team_set & self.PACIFIC_LEAGUE_TEAMS
        if games and len(pacific_present) == 0:
            LOGGER.warning(
                f"NPB {target_date} 抓取結果不含任何太平洋聯盟球隊！"
                f"（共 {len(games)} 場）可能為單一聯盟頁面。請檢查來源 URL。"
            )
        else:
            LOGGER.info(
                f"NPB {target_date} 太平洋聯盟球隊出現: {sorted(pacific_present)}"
            )

        # 🆕 補先發投手（從 lottonavi.com 爬取）
        self._enrich_pitchers(games, target_date)

        return games

    def _fetch_games_yahoo(self, target_date: str) -> List[Dict[str, Any]]:
        """
        🆕 [2026-10-27 P1] Yahoo NPB 賽程備援解析
        URL: https://baseball.yahoo.co.jp/npb/schedule/?date=YYYY-MM-DD
        每個 tr.bb-scheduleTable__row 為一日賽程（含日期表頭），需按日期過濾。
        """
        from datetime import date as _date
        dt = datetime.strptime(target_date, "%Y-%m-%d")
        url = f"https://baseball.yahoo.co.jp/npb/schedule/?date={target_date}"
        resp = self.session.get(url, timeout=20, headers={"Accept-Language": "ja,en"})
        if resp.status_code != 200:
            raise RuntimeError(f"Yahoo NPB HTTP {resp.status_code} ({url})")

        soup = BeautifulSoup(resp.text, "lxml")
        games: List[Dict[str, Any]] = []
        for tr in soup.select("tr.bb-scheduleTable__row"):
            head = tr.select_one(".bb-scheduleTable__head")
            if not head:
                continue
            m = re.search(r"(\d{1,2})月(\d{1,2})日", head.get_text(" ", strip=True))
            if not m or int(m.group(1)) != dt.month or int(m.group(2)) != dt.day:
                continue
            home_el = tr.select_one(".bb-scheduleTable__homeName")
            away_el = tr.select_one(".bb-scheduleTable__awayName")
            if not home_el or not away_el:
                continue
            home = _resolve_team(home_el.get_text(strip=True))
            away = _resolve_team(away_el.get_text(strip=True))
            if not home or not away:
                continue

            def _score(sel: str):
                el = tr.select_one(sel)
                t = el.get_text(strip=True) if el else ""
                return int(t) if t.isdigit() else None

            home_score = _score(".bb-scheduleTable__homeScore")
            away_score = _score(".bb-scheduleTable__awayScore")
            status_el = tr.select_one(".bb-scheduleTable__status")
            status_txt = status_el.get_text(" ", strip=True) if status_el else ""

            if "中止" in status_txt or "ノーゲーム" in status_txt:
                status = "POSTPONED"
                home_score = away_score = None
            elif "試合終了" in status_txt:
                status = "FINAL"
            elif "試合中" in status_txt:
                status = "LIVE"
            else:
                status = "SCHEDULED"

            if dt.date() > _date.today():
                status = "SCHEDULED"
            if status == "SCHEDULED":
                home_score = away_score = None

            game = {
                "season": dt.year,
                "match_date": target_date,
                "home_team": home,
                "away_team": away,
                "status": status,
                "home_team_score": home_score,
                "away_team_score": away_score,
            }
            # 未開打場次可從 (予)投手 取得先發
            for key, sel in (("home_pitcher", ".bb-scheduleTable__homePlayer"),
                             ("away_pitcher", ".bb-scheduleTable__awayPlayer")):
                for li in tr.select(f"{sel} li"):
                    mm = re.search(r"\(予\)\s*(.+)$", li.get_text(strip=True))
                    if mm:
                        game[key] = mm.group(1).strip()
                        break
            games.append(game)

        LOGGER.info(f"NPB Yahoo {target_date} → {len(games)} 場")
        if games and any(g.get("status") == "SCHEDULED" and not g.get("home_pitcher") and not g.get("away_pitcher") for g in games):
            self._enrich_pitchers(games, target_date)
        return games

    def _enrich_pitchers(self, games: List[Dict[str, Any]], target_date: str):
        """從 lottonavi.com 爬取 NPB 當日先發投手並補入 games"""
        try:
            from npb_data_fetcher import NPBDataFetcher
            fetcher = NPBDataFetcher()
            # target_date: "YYYY-MM-DD" → "YYYYMMDD"
            date_str = target_date.replace('-', '')
            starters = fetcher.get_today_starters(date_str)
            if starters:
                enriched = 0
                for g in games:
                    home = g.get('home_team')
                    away = g.get('away_team')
                    # lottonavi 和 npb.jp 主客隊順序可能相反，雙向比對
                    key1 = f"{home}_vs_{away}"
                    key2 = f"{away}_vs_{home}"
                    sp = starters.get(key1)
                    if sp:
                        g['home_pitcher'] = sp.get('home_pitcher')
                        g['away_pitcher'] = sp.get('away_pitcher')
                        enriched += 1
                    elif key2 in starters:
                        sp = starters[key2]
                        # 主客隊相反，投手也要對調
                        g['home_pitcher'] = sp.get('away_pitcher')
                        g['away_pitcher'] = sp.get('home_pitcher')
                        enriched += 1
                LOGGER.info(f"NPB {target_date} 補入先發投手: {enriched} 筆")
            else:
                LOGGER.info(f"NPB {target_date} 無先發投手資料（可能尚未公布）")
        except Exception as e:
            LOGGER.warning(f"NPB pitcher enrichment failed: {e}")

    def _parse_game_row(self, row, dt: datetime):
        """解析單場比賽 <tr> → dict"""
        # 球隊簡稱：<div class="team1"> 與 <div class="team2">
        team1_div = row.find("div", class_="team1")
        team2_div = row.find("div", class_="team2")

        if not team1_div or not team2_div:
            return None

        home_jp = team1_div.get_text(strip=True)
        away_jp = team2_div.get_text(strip=True)
        home_full = _resolve_team(home_jp)
        away_full = _resolve_team(away_jp)

        if not home_full or not away_full:
            LOGGER.debug(f"NPB 無法解析球隊: {home_jp} vs {away_jp}")
            return None

        # 比分：<div class="score1"> / <div class="score2">
        score1_div = row.find("div", class_="score1")
        score2_div = row.find("div", class_="score2")

        def parse_score(div):
            if not div:
                return None
            text = div.get_text(strip=True)
            if not text or text == "&nbsp;":
                return None
            try:
                return int(text)
            except ValueError:
                return None

        home_score = parse_score(score1_div)
        away_score = parse_score(score2_div)

        # 狀態判斷
        # - 兩個比分都有數字 → 已結束
        # - 否則 → 尚未開打（schedule）
        if home_score is not None and away_score is not None:
            status = "FINAL"
        else:
            status = "SCHEDULED"

        # 🆕 [2026-07-28] 未來日期防護：若 dt 是未來日期
        # 一律強制 SCHEDULED 並清空比分
        from datetime import date
        if dt.date() > date.today():
            status = "SCHEDULED"
            home_score = None
            away_score = None

        return {
            "season": dt.year,
            "match_date": dt.strftime("%Y-%m-%d"),
            "home_team": home_full,
            "away_team": away_full,
            "status": status,
            "home_team_score": home_score,
            "away_team_score": away_score,
        }