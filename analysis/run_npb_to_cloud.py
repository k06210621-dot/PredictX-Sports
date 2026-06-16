#!/usr/bin/env python3
"""
run_npb_to_cloud.py
===================
從 npb.jp 抓取 NPB 當日賽事 → POST 至 Railway 雲端 /api/insert_games

設計目標：
- 任何環境（Railway cron service、本機 cron、Mac 終端手動跑）都可執行
- 只需 CLOUD_API_URL 環境變數，未設 fallback 到正式 production
- 失敗有完整錯誤輸出，不 silent skip
- 支援「只補指定日期」模式（cron 一天跑兩次：06:00 補當日、18:00 補次日）

執行：
    python run_npb_to_cloud.py            # 抓今天 + 明天
    python run_npb_to_cloud.py --days 3   # 抓今天到 +3 天
    CLOUD_API_URL=https://... python run_npb_to_cloud.py
"""

import os
import sys
import asyncio
import argparse
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

import aiohttp
import requests

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
LOGGER = logging.getLogger("npb-to-cloud")

# 正式 production endpoint（未設環境變數時的預設）
DEFAULT_CLOUD_API_URL = "https://predictx-sports-production.up.railway.app"
NPB_DAILY_URL_TEMPLATE = "https://npb.jp/bis/eng/{year}/games/gm{date}.html"

# NPB 球隊解析（同 npb.py，但獨立可單獨 import）
NPB_TEAMS = {
    "Yomiuri":    "Yomiuri Giants",
    "Hanshin":    "Hanshin Tigers",
    "Chunichi":   "Chunichi Dragons",
    "DeNA":       "Yokohama DeNA BayStars",
    "Hiroshima":  "Hiroshima Toyo Carp",
    "Yakult":     "Tokyo Yakult Swallows",
    "Seibu":      "Saitama Seibu Lions",
    "Rakuten":    "Tohoku Rakuten Golden Eagles",
    "SoftBank":   "Fukuoka SoftBank Hawks",
    "Nippon-Ham": "Hokkaido Nippon-Ham Fighters",
    "Lotte":      "Chiba Lotte Marines",
    "ORIX":       "ORIX Buffaloes",
}

import re
from bs4 import BeautifulSoup


def resolve_team(text: str) -> Optional[str]:
    """解析簡寫球隊名為全名"""
    clean = re.sub(r'[0-9]', '', text).strip()
    if clean in NPB_TEAMS:
        return NPB_TEAMS[clean]
    for key, full in NPB_TEAMS.items():
        if key.lower() in clean.lower():
            return full
    return None


async def fetch_npb_games(days_ahead: int = 1) -> List[Dict[str, Any]]:
    """
    從 npb.jp 抓取今天到 +days_ahead 天的 NPB 賽事
    """
    games = []
    today = datetime.now()
    target_dates = [today + timedelta(days=i) for i in range(days_ahead + 1)]

    async with aiohttp.ClientSession() as session:
        for target_date in target_dates:
            date_str = target_date.strftime("%Y%m%d")
            url = NPB_DAILY_URL_TEMPLATE.format(year=target_date.year, date=date_str)
            try:
                async with session.get(url, timeout=20) as resp:
                    if resp.status != 200:
                        LOGGER.warning(f"NPB {date_str} HTTP {resp.status}, 跳過")
                        continue
                    html = await resp.text()
            except Exception as e:
                LOGGER.warning(f"NPB {date_str} 請求失敗: {e}")
                continue

            soup = BeautifulSoup(html, "lxml")
            gr = soup.find("div", class_="game_result")
            if not gr:
                LOGGER.info(f"NPB {date_str} 休兵日（無 game_result）")
                continue

            left_unit = gr.find("div", class_="left_unit")
            if not left_unit:
                continue
            units = left_unit.find_all("div", class_="unit")
            LOGGER.info(f"NPB {date_str} 找到 {len(units)} 場")

            for unit in units:
                team_left = unit.find("div", class_="team_left")
                team_right = unit.find("div", class_="team_right")
                if not team_left or not team_right:
                    continue

                home_name_div = team_left.find("div", class_="team_name")
                away_name_div = team_right.find("div", class_="team_name")
                home_score_div = team_left.find("div", class_="score_text")
                away_score_div = team_right.find("div", class_="score_text")

                if not home_name_div or not away_name_div:
                    continue

                home_full = resolve_team(home_name_div.get_text(strip=True))
                away_full = resolve_team(away_name_div.get_text(strip=True))
                if not home_full or not away_full:
                    LOGGER.warning(f"  無法解析隊名: {home_name_div.get_text(strip=True)} / {away_name_div.get_text(strip=True)}")
                    continue

                home_score_text = home_score_div.get_text(strip=True) if home_score_div else ""
                away_score_text = away_score_div.get_text(strip=True) if away_score_div else ""
                home_score = int(home_score_text) if home_score_text.isdigit() else None
                away_score = int(away_score_text) if away_score_text.isdigit() else None

                # 狀態：有分數就是 final，否則 scheduled
                status = "FINAL" if home_score is not None and away_score is not None else "SCHEDULED"

                games.append({
                    "season": target_date.year,
                    "match_date": target_date.strftime("%Y-%m-%d"),
                    "home_team": home_full,
                    "away_team": away_full,
                    "status": status,
                })

    return games


def upload_to_cloud(games: List[Dict[str, Any]], cloud_url: str) -> bool:
    """POST games 到雲端 /api/insert_games"""
    if not games:
        LOGGER.info("沒有賽事需上傳")
        return True

    endpoint = f"{cloud_url.rstrip('/')}/api/insert_games"
    LOGGER.info(f"上傳 {len(games)} 場到 {endpoint}")

    try:
        resp = requests.post(endpoint, json={"games": games}, timeout=30)
        if resp.status_code != 200:
            LOGGER.error(f"❌ HTTP {resp.status_code}: {resp.text[:200]}")
            return False
        result = resp.json()
        LOGGER.info(f"✅ 雲端回應: inserted={result.get('inserted')}, skipped={result.get('skipped')}")
        return True
    except Exception as e:
        LOGGER.error(f"❌ 上傳失敗: {e}")
        return False


async def main():
    parser = argparse.ArgumentParser(description='NPB 賽事抓取並上傳到雲端')
    parser.add_argument('--days', type=int, default=1, help='抓取今天到 +N 天（預設 1）')
    args = parser.parse_args()

    cloud_url = os.getenv('CLOUD_API_URL', DEFAULT_CLOUD_API_URL)
    LOGGER.info(f"=== NPB → Cloud Pipeline START ===")
    LOGGER.info(f"Target: {args.days + 1} 天 | Cloud: {cloud_url}")

    games = await fetch_npb_games(days_ahead=args.days)
    LOGGER.info(f"共抓到 {len(games)} 場 NPB 賽事")

    if not games:
        LOGGER.info("無資料，提前結束")
        return 0

    success = upload_to_cloud(games, cloud_url)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
