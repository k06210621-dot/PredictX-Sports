#!/usr/bin/env python3
"""
手動抓取 NPB 所有投手數據並寫入 player_season_stats
此腳本執行後會抓取 12 隊所有 ip >= 5 的投手，寫入 DB。
"""
import sys
sys.path.insert(0, '/Users/jero/PredictX-Sports-backend')

from analysis.npb_data_fetcher import NPBDataFetcher
import psycopg2
from psycopg2.extras import RealDictCursor
import os, json

TEAM_NAMES = [
    'Yomiuri Giants', 'Hanshin Tigers', 'Chunichi Dragons',
    'Yokohama DeNA BayStars', 'Hiroshima Toyo Carp', 'Tokyo Yakult Swallows',
    'Fukuoka SoftBank Hawks', 'Saitama Seibu Lions', 'Chiba Lotte Marines',
    'ORIX Buffaloes', 'Tohoku Rakuten Golden Eagles', 'Hokkaido Nippon-Ham Fighters'
]

def main():
    print("=== 開始抓取 NPB 所有投手數據 ===")
    fetcher = NPBDataFetcher()
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        print("❌ DATABASE_URL 未設定")
        sys.exit(1)
    conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor)
    cur = conn.cursor()
    
    total_fetched = 0
    for team in TEAM_NAMES:
        print(f"\n抓取 {team}...")
        pitchers = fetcher.get_top_starters(team, top_n=30)  # 抓取前 30 名（應足夠）
        if not pitchers:
            print(f"  ⚠️  {team} 抓取失敗或無數據")
            continue
        
        print(f"  ✓ 抓取到 {len(pitchers)} 名投手")
        total_fetched += len(pitchers)
        
        for p in pitchers:
            # 先查 player_id
            cur.execute("""
                SELECT p.player_id FROM predictx.players p
                JOIN predictx.player_teams pt ON p.player_id = pt.player_id
                JOIN predictx.teams t ON pt.team_id = t.team_id
                WHERE t.english_name = %s AND p.player_name = %s AND t.league = 'NPB'
            """, (team, p['name']))
            row = cur.fetchone()
            if not row:
                # 找不到球員，嘗試模糊匹配或跳過
                print(f"    - 未找到球員 ID: {p['name']}，跳過")
                continue
            
            player_id = row['player_id']
            
            # 寫入 player_season_stats
            cur.execute("""
                INSERT INTO predictx.player_season_stats 
                (player_id, league, season, kind, era, w, l, ip, p_so, p_bb, source, fetched_at)
                VALUES (%s, 'NPB', 2026, 'pitcher', %s, %s, %s, %s, %s, %s, 'baseball-data-scraper', NOW())
                ON CONFLICT (player_id, season, source) DO UPDATE SET
                    era = EXCLUDED.era, w = EXCLUDED.w, l = EXCLUDED.l,
                    ip = EXCLUDED.ip, p_so = EXCLUDED.p_so, p_bb = EXCLUDED.p_bb
            """, (
                player_id,
                p['era'], p['wins'], p['losses'], p['ip'], p['k'], p['bb']
            ))
    
    conn.commit()
    
    # 統計結果
    cur.execute("SELECT count(*) FROM predictx.player_season_stats WHERE league = 'NPB' AND season = 2026 AND source = 'baseball-data-scraper'")
    new_count = cur.fetchone()[0]
    print(f"\n=== 完成：本次抓取 {total_fetched} 筆, 新增/更新 {new_count} 筆 ===")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()