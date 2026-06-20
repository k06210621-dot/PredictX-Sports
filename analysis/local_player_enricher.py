"""
local_player_enricher.py
========================
從本地爬蟲輸出的 JSON 載入 CPBL / NPB 球員資料，並提供
對應 AI prompt 用的格式化段落。

資料來源：
- CPBL: stats.cpbl.com.tw  爬蟲 → cpbl_players.json
- NPB:  npb.jp/bis/eng/2026/stats/ 爬蟲 → npb_players.json

JSON 檔案路徑透過環境變數 PLAYER_DATA_DIR 覆寫，預設為本檔同目錄。
"""

import json
import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

LOGGER = logging.getLogger("local-player-enricher")

_THIS_DIR = Path(__file__).parent
_DATA_DIR = Path(os.getenv("PLAYER_DATA_DIR", _THIS_DIR))
CPBL_FILE = _DATA_DIR / "cpbl_players.json"
NPB_FILE = _DATA_DIR / "npb_players.json"

# CPBL 球隊中文名 → TheSportsDB team name（與 analysis_engine 對齊）
# 確保我們建立的提示段落使用 PredictX 內部一致的球隊名稱
# key: CPBL 一軍球隊代碼（011 為一軍，022 為二軍），value: 中文全名
CPBL_TEAM_KEYS = {
    "ACN011": "中信兄弟",
    "ADD011": "統一7-ELEVEn獅",
    "AEO011": "富邦悍將",
    "AJL011": "樂天桃猿",
    "AAA011": "味全龍",
    "AKP011": "台鋼雄鷹",
    # 二軍代碼（對應中文全名，給 fallback）
    "ACN022": "中信兄弟二軍",
    "ADD022": "統一7-ELEVEn獅二軍",
    "AEO022": "富邦悍將二軍",
    "AJL022": "樂天桃猿二軍",
    "AAA022": "味全龍二軍",
    "AKP022": "台鋼雄鷹二軍",
}

# CPBL 球隊中英別名 → 一軍代碼（用於從 game.home_team 名稱反查）
CPBL_NAME_TO_CODE = {
    "中信兄弟": "ACN011",
    "兄弟": "ACN011",
    "CTBC Brothers": "ACN011",
    "CTBC": "ACN011",
    "統一7-ELEVEn獅": "ADD011",
    "統一獅": "ADD011",
    "統一": "ADD011",
    "Uni-President 7-ELEVEn Lions": "ADD011",
    "Lions": "ADD011",
    "富邦悍將": "AEO011",
    "富邦": "AEO011",
    "Fubon Guardians": "AEO011",
    "Fubon": "AEO011",
    "Guardians": "AEO011",
    "樂天桃猿": "AJL011",
    "樂天": "AJL011",
    "Rakuten Monkeys": "AJL011",
    "Monkeys": "AJL011",
    "味全龍": "AAA011",
    "味全": "AAA011",
    "Wei Chuan Dragons": "AAA011",
    "Dragons": "AAA011",
    "台鋼雄鷹": "AKP011",
    "台鋼": "AKP011",
    "TSG Hawks": "AKP011",
    "Hawks": "AKP011",
}

# NPB 球隊代碼（pit_c.html 用單字母代碼）→ 全名（含官方簡稱）
NPB_TEAM_KEYS = {
    "T": ("Hanshin Tigers", "Tigers"),
    "D": ("Chunichi Dragons", "Dragons"),
    "G": ("Yomiuri Giants", "Giants"),
    "DB": ("YOKOHAMA DeNA BAYSTARS", "DeNA"),
    "C": ("Hiroshima Toyo Carp", "Carp"),
    "S": ("Tokyo Yakult Swallows", "Swallows"),
    "H": ("Fukuoka SoftBank Hawks", "Hawks"),
    "F": ("Hokkaido Nippon-Ham Fighters", "Fighters"),
    "B": ("ORIX Buffaloes", "Buffaloes"),
    "E": ("Tohoku Rakuten Golden Eagles", "Eagles"),
    "L": ("Saitama Seibu Lions", "Lions"),
    "M": ("Chiba Lotte Marines", "Marines"),
}

# NPB 球隊官方簡稱 → (league, code)
NPB_TEAM_TO_LEAGUE_CODE = {
    # 完整英文名
    "Hanshin Tigers": ("central", "T"),
    "Chunichi Dragons": ("central", "D"),
    "Yomiuri Giants": ("central", "G"),
    "YOKOHAMA DeNA BAYSTARS": ("central", "DB"),
    "Yokohama DeNA BayStars": ("central", "DB"),
    "Hiroshima Toyo Carp": ("central", "C"),
    "Tokyo Yakult Swallows": ("central", "S"),
    "Fukuoka SoftBank Hawks": ("pacific", "H"),
    "Hokkaido Nippon-Ham Fighters": ("pacific", "F"),
    "ORIX Buffaloes": ("pacific", "B"),
    "Tohoku Rakuten Golden Eagles": ("pacific", "E"),
    "Saitama Seibu Lions": ("pacific", "L"),
    "Chiba Lotte Marines": ("pacific", "M"),
    # 簡稱（與爬蟲資料內 "Pitcher" / "Batter" 欄位的 team 縮寫對齊）
    "Tigers": ("central", "T"),
    "Dragons": ("central", "D"),
    "Giants": ("central", "G"),
    "DeNA": ("central", "DB"),
    "Carp": ("central", "C"),
    "Swallows": ("central", "S"),
    "Hawks": ("pacific", "H"),
    "Fighters": ("pacific", "F"),
    "Buffaloes": ("pacific", "B"),
    "Eagles": ("pacific", "E"),
    "Lions": ("pacific", "L"),
    "Marines": ("pacific", "M"),
}


@lru_cache(maxsize=1)
def _load_cpbl() -> List[Dict]:
    if not CPBL_FILE.exists():
        LOGGER.warning(f"CPBL data file not found: {CPBL_FILE}")
        return []
    try:
        with open(CPBL_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        LOGGER.warning(f"Failed to load CPBL data: {e}")
        return []


@lru_cache(maxsize=1)
def _load_npb() -> List[Dict]:
    if not NPB_FILE.exists():
        LOGGER.warning(f"NPB data file not found: {NPB_FILE}")
        return []
    try:
        with open(NPB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        LOGGER.warning(f"Failed to load NPB data: {e}")
        return []


def get_cpbl_roster(team_code: str) -> List[Dict]:
    """回傳指定 CPBL 球隊（限定一軍）所有球員。"""
    if not team_code:
        return []
    return [
        p for p in _load_cpbl()
        if p.get("team_code") == team_code and p.get("is_active")
    ]


def get_npb_qualified_players(league: str, kind: str) -> List[Dict]:
    """回傳指定 NPB 聯盟 + 投手/打者的合格球員（已過規定局/打席）。"""
    if not league or not kind:
        return []
    return [
        p for p in _load_npb()
        if p.get("league") == league and p.get("kind") == kind
    ]


def build_cpbl_roster_section(team_code: str, side: str = "home") -> str:
    """建立「CPBL 球隊陣容」段落，包含一軍所有球員基本資料。"""
    if not team_code:
        return ""

    players = get_cpbl_roster(team_code)
    if not players:
        return ""

    team_name_zh = CPBL_TEAM_KEYS.get(team_code, team_code)
    is_first = side == "home"
    title = "主隊" if is_first else "客隊"

    # 投手（位置代碼 1 = 投手）
    pitchers = [p for p in players if p.get("position_code") == "1"]
    batters = [p for p in players if p.get("position_code") != "1"]

    lines = [
        f"\n===== {title} CPBL 球隊陣容（{team_name_zh}）=====",
        f"資料來源：stats.cpbl.com.tw 官方",
        f"球員總數: {len(players)} 位（投手 {len(pitchers)} 位、野手 {len(batters)} 位）",
        "",
        "【投手名單】（背號 - 中文姓名 - 身高）",
    ]
    # 排序：背號（字串內含補零）
    pitchers_sorted = sorted(
        pitchers, key=lambda x: str(x.get("uniform") or "999").zfill(4)
    )
    for p in pitchers_sorted[:30]:
        u = p.get("uniform") or "-"
        n = p.get("name_zh") or "?"
        h = p.get("height_cm")
        h_str = f"{h}cm" if h else "?"
        lines.append(f"  • #{u:>4} {n} ({h_str})")
    if len(pitchers_sorted) > 30:
        lines.append(f"  ... 及其他 {len(pitchers_sorted) - 30} 位投手")

    lines.append("")
    lines.append("【野手名單】")
    batters_sorted = sorted(
        batters, key=lambda x: str(x.get("uniform") or "999").zfill(4)
    )
    for p in batters_sorted[:30]:
        u = p.get("uniform") or "-"
        n = p.get("name_zh") or "?"
        h = p.get("height_cm")
        h_str = f"{h}cm" if h else "?"
        lines.append(f"  • #{u:>4} {n} ({h_str})")
    if len(batters_sorted) > 30:
        lines.append(f"  ... 及其他 {len(batters_sorted) - 30} 位野手")

    return "\n".join(lines) + "\n"


def build_npb_qualified_section(league: str) -> str:
    """建立「NPB 聯盟合格球員統計」段落，含投手 ERA 排名與打者打擊率排名。"""
    if league not in ("central", "pacific"):
        return ""

    league_name = "中央聯盟" if league == "central" else "太平洋聯盟"
    pitchers = get_npb_qualified_players(league, "pitcher")
    batters = get_npb_qualified_players(league, "batter")

    if not pitchers and not batters:
        return ""

    lines = [f"\n===== NPB {league_name} 合格球員統計（官方）=====",
             f"資料來源：npb.jp/bis/eng/2026/stats/ 官方",
             f"規定投手: {len(pitchers)} 位 / 規定打者: {len(batters)} 位",
             ""]

    if pitchers:
        lines.append("【投手 ERA 排行（取前 10 名）】")
        lines.append("排名 球員(球隊)       ERA    G   W  L  SV    IP    SO")
        for p in pitchers[:10]:
            rank = p.get("rank")
            name = p.get("name_en", "?")
            team_info = NPB_TEAM_KEYS.get(p.get("team_code"), (None, ""))
            short_team = team_info[1] if team_info else ""
            lines.append(
                f" {rank:>3}  {name:<22}({short_team:<4}) "
                f"{p.get('era'):>5} {p.get('g'):>3} {p.get('w'):>2} {p.get('l'):>2} "
                f"{p.get('sv'):>2} {p.get('ip'):>6} {p.get('so'):>4}"
            )
        lines.append("")

    if batters:
        lines.append("【打者打擊率排行（取前 10 名）】")
        lines.append("排名 球員(球隊)        AVG    G    H  HR  RBI    BB    SO")
        for p in batters[:10]:
            rank = p.get("rank")
            name = p.get("name_en", "?")
            team_info = NPB_TEAM_KEYS.get(p.get("team_code"), (None, ""))
            short_team = team_info[1] if team_info else ""
            lines.append(
                f" {rank:>3}  {name:<22}({short_team:<4}) "
                f"{p.get('avg'):>5} {p.get('g'):>3} {p.get('h'):>4} "
                f"{p.get('hr'):>2} {p.get('rbi'):>4} {p.get('bb'):>4} {p.get('so'):>4}"
            )
        lines.append("")

    return "\n".join(lines) + "\n"


def cpbl_team_to_code(team_name_zh: str) -> Optional[str]:
    """由球隊中文名（如「中信兄弟」）反查 CPBL 球隊代碼。

    支援多種格式：
      - 中文全名：「中信兄弟」
      - 中文簡稱：「兄弟」「統一」「富邦」
      - 英文全名：「CTBC Brothers」
      - 英文簡稱：「CTBC」「Dragons」
    """
    if not team_name_zh:
        return None
    return CPBL_NAME_TO_CODE.get(team_name_zh.strip())


def npb_team_name_to_league_and_code(team_name_en: str) -> Optional[tuple]:
    """由 NPB 球隊英文名反查 (league, code)。"""
    return NPB_TEAM_TO_LEAGUE_CODE.get(team_name_en)


def get_data_health_report() -> Dict[str, Dict]:
    """回報兩個資料源的當前健康狀態。"""
    cpbl = _load_cpbl()
    npb = _load_npb()
    return {
        "cpbl": {
            "file": str(CPBL_FILE),
            "exists": CPBL_FILE.exists(),
            "player_count": len(cpbl),
            "active_count": sum(1 for p in cpbl if p.get("is_active")),
        },
        "npb": {
            "file": str(NPB_FILE),
            "exists": NPB_FILE.exists(),
            "row_count": len(npb),
            "pitchers": sum(1 for p in npb if p.get("kind") == "pitcher"),
            "batters": sum(1 for p in npb if p.get("kind") == "batter"),
        },
    }


if __name__ == "__main__":
    import sys

    report = get_data_health_report()
    print("=== 本地球員資料健康報告 ===")
    for league, info in report.items():
        print(f"\n[{league}]")
        for k, v in info.items():
            print(f"  {k}: {v}")

    # 顯示樣本段落
    print("\n=== CPBL 範例段落 ===")
    sample = build_cpbl_roster_section("AEO011", "home")
    print(sample)

    print("\n=== NPB 中央聯盟範例段落 ===")
    sample = build_npb_qualified_section("central")
    print(sample)