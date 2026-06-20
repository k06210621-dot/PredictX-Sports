"""
thesportsdb_enricher.py
=======================
從 TheSportsDB API 抓取增強資料，提升 AI 預測準確度。

主要功能：
- get_match_result_details(event_id): 取得單場比賽逐局比分
- get_season_matchups(league_id, season): 取得聯盟整季賽事
- get_team_recent_form(team_id, limit): 取得球隊最近賽事
- build_innings_analysis_section(home, away): 建立 AI prompt 的逐局分析段落

免費版限制：
- eventslast/eventsnext 只回 1 場
- searchteams 限 "Arsenal"
- lookup_all_players 限 10 位
- Rate limit: 30 req/min
"""

import os
import re
import logging
from typing import Dict, Any, Optional, List
import requests
from functools import lru_cache

LOGGER = logging.getLogger("thesportsdb-enricher")

# TheSportsDB 設定
_TDB_DEFAULT = "123"  # 免費版 default (overridden by env THESPORTSDB_API_KEY)
BASE = f"https://www.thesportsdb.com/api/v1/json/{123}"  # 預設 free key

# 各聯盟 ID
LEAGUE_IDS = {
    "MLB": "4424",
    "NBA": "4387",
    "NPB": "4839",  # Nippon Professional Baseball
    "CPBL": "5111",  # Chinese Professional Baseball League
    "KBO": "4170",  # Korean KBO League（未來用）
}


# Hard-coded TheSportsDB team IDs（因 free tier searchteams 限 Arsenal）
TEAM_ID_MAP = {
    # MLB
    "Tampa Bay Rays": "135261",
    "New York Yankees": "135260",
    "Los Angeles Dodgers": "135269",
    "Boston Red Sox": "135271",
    "Houston Astros": "135272",
    "Atlanta Braves": "135263",
    "Philadelphia Phillies": "135275",
    "Chicago Cubs": "135264",
    "Seattle Mariners": "135267",
    "San Diego Padres": "135273",
    # CPBL
    "Uni-President 7-ELEVEn Lions": "144301",
    "CTBC Brothers": "144298",
    "Fubon Guardians": "144299",
    "Rakuten Monkeys": "144300",
    "Wei Chuan Dragons": "144302",
    "TSG Hawks": "147333",
    # NPB (部分)
    "Yomiuri Giants": "140299",
    "Hanshin Tigers": "140300",
    "Chunichi Dragons": "140301",
}


class TheSportsDBEnricher:
    """TheSportsDB 增強資料服務"""

    def __init__(self, _key: Optional[str] = None):
        _env_key = __import__("os").environ.get("THESPORTSDB_API_KEY")
        self.api_key = _key or _env_key or _TDB_DEFAULT
        self.base = f"https://www.thesportsdb.com/api/v1/json/{self.api_key}"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "PredictX-Sports/1.0",
            "Accept": "application/json",
        })

    def _get(self, endpoint: str, params: Optional[Dict] = None, timeout: int = 10) -> Optional[Dict]:
        """GET 請求（含錯誤處理）"""
        url = f"{self.base}/{endpoint}"
        try:
            r = self.session.get(url, params=params, timeout=timeout)
            if r.status_code == 200:
                return r.json()
            elif r.status_code == 429:
                LOGGER.warning("TheSportsDB rate limit hit (429). Sleep 60s...")
                import time
                time.sleep(60)
                r = self.session.get(url, params=params, timeout=timeout)
                if r.status_code == 200:
                    return r.json()
            LOGGER.error(f"TheSportsDB {endpoint} HTTP {r.status_code}")
            return None
        except Exception as e:
            LOGGER.error(f"TheSportsDB {endpoint} failed: {e}")
            return None

    # ========================================================
    # 核心 API
    # ========================================================

    def get_match_result_details(self, event_id: str) -> Optional[Dict[str, Any]]:
        """
        取得單場比賽詳細資料（逐局比分、球場、輪次）

        Args:
            event_id: TheSportsDB event ID

        Returns:
            dict with: venue, round, result_detail, spectators, video, timestamp
        """
        data = self._get(f"lookupevent.php", {"id": event_id})
        if not data:
            return None
        events = data.get("events", [])
        if not events:
            return None
        e = events[0]
        return {
            "venue": e.get("strVenue"),
            "venue_id": e.get("idVenue"),
            "round": e.get("intRound"),
            "result_detail": e.get("strResult"),  # 逐局比分（含 HTML）
            "spectators": e.get("intSpectators"),
            "video": e.get("strVideo"),
            "timestamp": e.get("strTimestamp"),
            "status": e.get("strStatus"),
            "postponed": e.get("strPostponed", "no"),
        }

    @lru_cache(maxsize=64)
    def get_season_matchups(self, league_id: str, season: str = "2026") -> List[Dict]:
        """
        取得聯盟整季所有賽事

        Args:
            league_id: TheSportsDB league ID (如 "5111" for CPBL)
            season: 賽季字串（預設 "2026"）

        Returns:
            List of event dicts
        """
        data = self._get("eventsseason.php", {"id": league_id, "s": season}, timeout=20)
        if not data:
            return []
        return data.get("events", []) or []

    def get_team_recent_form(self, team_id: str) -> List[Dict]:
        """
        取得球隊最近賽事（免費版限 1 場）
        """
        data = self._get("eventslast.php", {"id": team_id})
        if not data:
            return []
        return data.get("results", []) or []

    def get_team_next_game(self, team_id: str) -> Optional[Dict]:
        """
        取得球隊下一場賽事（免費版限 1 場）
        """
        data = self._get("eventsnext.php", {"id": team_id})
        if not data:
            return None
        events = data.get("events", []) or []
        return events[0] if events else None

    def get_team_info(self, team_id: str) -> Optional[Dict[str, Any]]:
        """取得球隊完整資訊（含球場、歷史）"""
        data = self._get("lookupteam.php", {"id": team_id})
        if not data:
            return None
        teams = data.get("teams", [])
        return teams[0] if teams else None

    # ========================================================
    # AI Prompt 整合
    # ========================================================


    # ========================================================
    # 球員資料 (TheSportsDB 球員基本資料)
    # ========================================================

    def get_team_roster(self, team_id: str) -> List[Dict[str, Any]]:
        """
        取得球隊完整球員名單（最多 10 位，free tier 限制）

        回傳每個球員的 dict：
          - idPlayer: 球員 ID
          - strPlayer: 球員姓名
          - strPosition: 位置（如 "Pitcher", "Center"）
          - strNationality: 國籍
          - dateBorn: 生日
          - strHeight, strWeight: 身高體重
          - strThumb: 球員照片 URL
          - strCutout: 去背頭像 URL（iOS UI 推薦用）
        """
        data = self._get("lookup_all_players.php", {"id": team_id})
        if not data:
            return []
        return data.get("player", []) or []

    def get_player_info(self, player_id: str) -> Optional[Dict[str, Any]]:
        """取得單一球員完整基本資料"""
        data = self._get("lookupplayer.php", {"id": player_id})
        if not data:
            return None
        players = data.get("players", [])
        return players[0] if players else None

    def get_player_contracts(self, player_id: str) -> List[Dict[str, Any]]:
        """
        取得球員合約紀錄（NBA 完整，MLB/CPBL/NPB 可能為空）

        回傳每筆合約：
          - strTeam: 球隊
          - strYearStart, strYearEnd: 合約起訖年
          - strBadge: 球隊 logo URL
        """
        data = self._get("lookupcontracts.php", {"id": player_id})
        if not data:
            return []
        contracts = data.get("contracts")
        return contracts if isinstance(contracts, list) else []

    def get_player_honours(self, player_id: str) -> List[Dict[str, Any]]:
        """
        取得球員榮譽（獎項、明星賽、入選等）

        回傳每筆榮譽：
          - strHonour: 獎項名稱
          - strSeason: 球季
          - strSport: 運動類型
        """
        data = self._get("lookuphonours.php", {"id": player_id})
        if not data:
            return []
        honours = data.get("honours")
        return honours if isinstance(honours, list) else []



    # ========================================================
    # 球員逐場/逐季 stats（補強 CPBL/NPB 投手資料缺口）
    # ========================================================

    def get_player_season_stats(self, player_id: str, season: str = "2026") -> Optional[Dict[str, Any]]:
        """
        取得球員某球季的整體 stats（如 Pitcher 的 ERA / Strikeouts）

        TheSportsDB 對 CPBL/NPB 投手資料極少，
        此方法主要用於 NBA（PPG/RPG/APG）和 MLB 部分球員
        """
        data = self._get("lookupplayerstats.php", {"id": player_id})
        if not data:
            return None
        stats_list = data.get("stats")
        if not stats_list or not isinstance(stats_list, list):
            return None

        # 找指定球季
        for s in stats_list:
            if str(s.get("strSeason")) == season:
                return s

        # 找不到指定球季，回傳最近一筆
        return stats_list[0] if stats_list else None

    def get_team_pitchers(self, team_id: str) -> List[Dict[str, Any]]:
        """
        取得球隊所有投手（TheSportsDB 限 free tier 最多 10 位球員，
        過濾出 position 為 Pitcher 的）

        適用於：
          - NBA：實作上 N/A（無投手概念）
          - MLB：可選用 5-10 位主力投手
          - CPBL：僅 1-2 位（資料稀少）
          - NPB：0 位（TheSportsDB 無資料）
        """
        players = self.get_team_roster(team_id)
        # 過濾投手（NBA 不會有）
        pitchers = [p for p in players if "pitcher" in (p.get("strPosition") or "").lower()]
        return pitchers

    def build_pitcher_quality_section(self, league: str, team_id: str) -> str:
        """
        建立 AI prompt 的「投手品質」段落（基於球員名單 + stats）

        即使 TheSportsDB 沒有逐場 ERA，也能提供：
        - 球員姓名 + 位置
        - 球員國籍 / 經驗
        - 球員基本 stats（如有）
        """
        pitchers = self.get_team_pitchers(team_id)
        if not pitchers:
            return ""

        section = f"\n===== 球隊投手名單（{league}）=====\n"
        section += f"可用資料: {len(pitchers)} 位投手\n"

        for p in pitchers:
            name = p.get("strPlayer", "")
            pos = p.get("strPosition", "")
            nat = p.get("strNationality", "")
            born = p.get("dateBorn", "")

            # 計算年齡
            age_str = ""
            if born:
                from datetime import datetime
                try:
                    bd = datetime.strptime(born, "%Y-%m-%d")
                    age = datetime.now().year - bd.year
                    age_str = f", {age} 歲"
                except Exception:
                    pass

            section += f"  • {name} ({pos}, {nat}{age_str})\n"

            # 加 stats（如果有）
            stats = self.get_player_season_stats(p.get("idPlayer", ""))
            if stats:
                relevant = {}
                for k, v in stats.items():
                    # 只取投手相關 stats
                    if k in ["strERA", "strWins", "strLosses", "strSaves",
                             "intWins", "intLosses", "intSaves",
                             "intEarnedRuns", "intHitsAllowed", "intStrikeouts",
                             "strAverage", "intPoints", "intAssists", "intRebounds"]:
                        if v and v != 'null':
                            relevant[k] = v

                if relevant:
                    stats_str = ", ".join(f"{k.replace('str', '').replace('int', '')}={v}" for k, v in relevant.items())
                    section += f"    2026 球季: {stats_str}\n"

        return section


    def build_innings_analysis_section(
        self,
        home_team: str,
        away_team: str,
        team_id_map: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        建立 AI prompt 的「逐局比分分析」段落

        從整季賽事中過濾兩隊對戰，取最近 3 場對戰的逐局比分

        Args:
            home_team: 主隊英文名
            away_team: 客隊英文名
            team_id_map: 可選，球隊名→team_id 對照表（從 DB 取）

        Returns:
            Markdown 格式的分析段落，空字串表示無資料
        """
        if not home_team or not away_team:
            return ""

        # 如果沒給 team_id_map，從 DB 抓
        if team_id_map is None:
            team_id_map = self._get_team_id_map_from_db()

        home_id = team_id_map.get(home_team)
        away_id = team_id_map.get(away_team)

        if not home_id or not away_id:
            LOGGER.debug(f"Team IDs not found: {home_team}={home_id}, {away_team}={away_id}")
            return ""

        # 從整季賽事找兩隊對戰
        league_id = self._guess_league_id(home_team, away_team)
        if not league_id:
            return ""

        season_events = self.get_season_matchups(league_id)
        if not season_events:
            return ""

        # 過濾兩隊對戰（用 id 對比）
        h2h = []
        for e in season_events:
            h = str(e.get("idHomeTeam", ""))
            a = str(e.get("idAwayTeam", ""))
            if (h == home_id and a == away_id) or (h == away_id and a == home_id):
                h2h.append(e)

        # 🆕 eventsseason 不含 strResult，需逐場用 lookupevent 抓逐局比分
        for game in h2h:
            event_id = str(game.get("idEvent", ""))
            if not event_id:
                continue
            details = self.get_match_result_details(event_id)
            if details and details.get("result_detail"):
                game["strResult"] = details["result_detail"]
                game["strVenue"] = details.get("venue", game.get("strVenue"))

        if not h2h:
            return ""

        # 按日期降序，取最近 3 場
        h2h.sort(key=lambda x: x.get("dateEvent", ""), reverse=True)
        recent = h2h[:3]

        # 組裝分析段落
        section = "\n===== 對戰歷史逐局分析（TheSportsDB）=====\n"
        section += f"兩隊本季對戰: {len(h2h)} 場（取最近 {len(recent)} 場逐局比分）\n"

        for i, game in enumerate(recent, 1):
            date = game.get("dateEvent", "")
            ht = game.get("strHomeTeam", "")
            at = game.get("strAwayTeam", "")
            hs = game.get("intHomeScore", "?")
            a_s = game.get("intAwayScore", "?")
            round_num = game.get("intRound", "?")
            result = game.get("strResult", "")

            section += f"\n📅 對戰 {i}: {date}（第 {round_num} 輪）\n"
            section += f"   {ht} {hs} - {a_s} {at}\n"

            if result:
                # 清理 HTML
                clean_result = self._format_innings(result)
                section += f"   逐局比分:\n{clean_result}\n"

                # AI 自動解讀
                insights = self._analyze_innings_pattern(result, ht if h == home_id else at, at if h == home_id else ht)
                if insights:
                    section += f"\n{insights}\n"

        return section

    def build_venue_section(self, home_team: str, away_team: str) -> str:
        """
        建立「球場特性」段落

        Returns:
            Markdown 格式段落
        """
        # 簡化版：透過球隊查主場球場
        # 實際上需要 lookup_all_teams 或 lookupteam.php
        # 為節省 API 呼叫，先用球隊名稱 map

        venue_map = {
            "Tampa Bay Rays": ("Tropicana Field", "室內球場（固定式屋頂）"),
            "New York Yankees": ("Yankee Stadium", "戶外，較冷天氣可能影響打擊"),
            "Los Angeles Dodgers": ("Dodger Stadium", "戶外，海風可能有影響"),
            "Boston Red Sox": ("Fenway Park", "戶外，左外野全壘打牆較近（綠怪物）"),
            "Chicago Cubs": ("Wrigley Field", "戶外，風向影響大"),
            "Uni-President 7-ELEVEn Lions": ("Tainan Municipal Baseball Stadium", "戶外，台南氣候"),
            "CTBC Brothers": ("Taichung Intercontinental Baseball Stadium", "戶外"),
        }

        venue_name, venue_note = venue_map.get(home_team, (None, None))
        if not venue_name:
            return ""

        return f"\n===== 主場球場特性（{venue_name}）=====\n{venue_note}\n"

    def build_round_context_section(self, current_round: Optional[int], league: str) -> str:
        """
        建立「比賽輪次情境」段落

        Args:
            current_round: 比賽輪次（如 13）
            league: 聯盟（"MLB", "CPBL", "NPB"）

        Returns:
            Markdown 格式段落
        """
        if not current_round:
            return ""

        # 球季總長度（依聯盟）
        season_length = {
            "MLB": 162,
            "CPBL": 120,
            "NPB": 143,
            "NBA": 82,
        }.get(league.upper(), 100)

        progress = current_round / season_length

        if progress < 0.1:
            stage = "賽季初期（資料樣本少，預測難度高）"
            note = "球隊仍在調整陣容，不宜過度解讀早期表現"
        elif progress < 0.4:
            stage = "賽季前期（資料逐漸充足）"
            note = "樣本數足夠判斷球隊基本實力"
        elif progress < 0.7:
            stage = "賽季中期（資料最豐富）"
            note = "預測可信度最高的階段"
        elif progress < 0.9:
            stage = "賽季後段（季後賽排名競爭激烈）"
            note = "球隊動機影響表現（爭排名 vs 已淘汰）"
        else:
            stage = "賽季末段（季後賽或最終排名）"
            note = "球隊戰略可能輪換主力"

        return f"\n===== 比賽輪次情境 =====\n"
        f"本場為第 {current_round} 輪（共 {season_length} 輪賽季）\n"
        f"階段：{stage}\n"
        f"分析指引：{note}\n"

    # ========================================================
    # 內部工具
    # ========================================================

    def _format_innings(self, raw_text: str) -> str:
        """清理 HTML tags，格式化逐局比分"""
        if not raw_text:
            return ""
        # 把 <br> 換成換行
        clean = re.sub(r"<br>", "\n     ", raw_text)
        # 移除其他 HTML tags
        clean = re.sub(r"<[^>]+>", "", clean)
        # 移除多餘空格
        clean = re.sub(r" +", " ", clean)
        # 縮短（避免 prompt 過長）
        if len(clean) > 400:
            clean = clean[:400] + "..."
        return clean

    def _analyze_innings_pattern(self, result_detail: str, our_team: str, opponent: str) -> str:
        """
        自動解讀逐局比分模式（給 AI 的提示）

        Returns:
            Markdown 格式的解讀
        """
        insights = []

        # 解析逐局數字
        # 格式範例: " Team A Innings:<br>0 0 0 0 1 2 0 0 0 <br>Hits: 4 - Errors: 1<br><br>Team B Innings:<br>..."
        innings_matches = re.findall(r"Innings:<br>([\d\s]+)<br>", result_detail)
        if len(innings_matches) >= 2:
            try:
                our_innings = [int(x) for x in innings_matches[0].strip().split() if x.isdigit() or (x.startswith('-') and x[1:].isdigit())]
                opp_innings = [int(x) for x in innings_matches[1].strip().split() if x.isdigit() or (x.startswith('-') and x[1:].isdigit())]
            except Exception:
                return ""

            # 偵測「爆發局」（單局 3+ 分）
            for i, score in enumerate(our_innings, 1):
                if score >= 3:
                    insights.append(f"   📈 第 {i} 局 {our_team} 爆發 {score} 分（進攻火力集中）")
                    break

            # 偵測「後段失分」（7-9 局失 3+ 分）
            late_inning_runs = sum(our_innings[6:9]) if len(our_innings) >= 9 else 0
            if late_inning_runs >= 3:
                insights.append(f"   ⚠️ 7-9 局失 {late_inning_runs} 分（牛棚/後段不穩）")

            # 偵測「投手完封」
            if sum(our_innings) == 0 and len(our_innings) >= 9:
                insights.append(f"   🔥 投手完封 {our_team}（牛棚表現優異）")
            elif sum(our_innings) <= 2 and len(our_innings) >= 9:
                insights.append(f"   📉 {our_team} 只得 {sum(our_innings)} 分（打線低迷）")

            # 偵測「完投完封」（投手投滿 9 局）
            if len(our_innings) == 9 and sum(our_innings) == 0 and sum(opp_innings) > 0:
                insights.append(f"   ⚾ 投手完投完封（先發 + 牛棚極佳）")

        return "\n".join(insights) if insights else ""

    def _guess_league_id(self, home_team: str, away_team: str) -> Optional[str]:
        """依球隊名猜測聯盟 ID"""
        mlb_teams = {
            "Tampa Bay Rays", "New York Yankees", "Los Angeles Dodgers",
            "Boston Red Sox", "Chicago Cubs", "Houston Astros",
            "Atlanta Braves", "Philadelphia Phillies", "San Diego Padres",
        }
        cpbl_teams = {
            "Uni-President 7-ELEVEn Lions", "CTBC Brothers",
            "Fubon Guardians", "Rakuten Monkeys",
            "Wei Chuan Dragons", "TSG Hawks",
        }
        npb_teams = {
            "Yomiuri Giants", "Hanshin Tigers", "Chunichi Dragons",
            "Orix Buffaloes", "SoftBank Hawks", "Rakuten Eagles",
        }

        teams = {home_team, away_team}
        if teams & mlb_teams:
            return LEAGUE_IDS["MLB"]
        if teams & cpbl_teams:
            return LEAGUE_IDS["CPBL"]
        if teams & npb_teams:
            return LEAGUE_IDS["NPB"]
        return None

    def _get_team_id_map_from_db(self) -> Dict[str, str]:
        """回傳球隊英文名 → TheSportsDB ID 對照表
        優先用 DB，fallback 用 hard-coded map
        """
        result = dict(TEAM_ID_MAP)  # 從 hard-coded 開始
        # 嘗試從 DB 補充（未來 DB 加上 team_external_id 欄位時會自動覆蓋）
        try:
            import psycopg2
            import os

            database_url = os.getenv("DATABASE_URL")
            if not database_url:
                return result

            conn = psycopg2.connect(database_url)
            cur = conn.cursor()
            cur.execute("""
                SELECT english_name, team_id::text
                FROM predictx.teams
                WHERE english_name IS NOT NULL
            """)
            for row in cur.fetchall():
                result[row[0]] = row[1]
            cur.close()
            conn.close()
            return result
        except Exception as e:
            LOGGER.debug(f"DB team_id_map unavailable, using hard-coded: {e}")
            return result


# 便利函式
_default_enricher: Optional[TheSportsDBEnricher] = None


def get_enricher() -> TheSportsDBEnricher:
    """取得預設 enricher 單例"""
    global _default_enricher
    if _default_enricher is None:
        _default_enricher = TheSportsDBEnricher()
    return _default_enricher
