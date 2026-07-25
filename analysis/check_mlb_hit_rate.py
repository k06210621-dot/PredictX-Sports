#!/usr/bin/env python3
"""檢查 MLB 近期命中率與信心度分佈"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 設定 Railway DB 連線
url = os.environ.get('DATABASE_URL', '')
if 'postgres.railway.internal' in url:
    os.environ['DATABASE_URL'] = url.replace('postgres.railway.internal:5432', 'thomas.proxy.rlwy.net:49887')

import psycopg2
from psycopg2.extras import RealDictCursor

def main():
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    print("=== MLB 命中率分析 ===\n")
    
    # 近 14 天整體統計
    cur.execute('''
    SELECT 
        COUNT(*) as total,
        COUNT(*) FILTER (WHERE ai_is_hit = true) as hits,
        COUNT(*) FILTER (WHERE ai_is_hit = false) as misses,
        ROUND(COUNT(*) FILTER (WHERE ai_is_hit = true) * 100.0 / NULLIF(COUNT(*),0), 2) as hit_rate
    FROM predictx.games g
    JOIN predictx.game_analysis ga ON g.game_id = ga.game_id
    JOIN predictx.teams t ON g.home_team_id = t.team_id
    WHERE t.league = 'MLB'
      AND g.home_team_score IS NOT NULL
      AND g.away_team_score IS NOT NULL
      AND g.match_date >= CURRENT_DATE - INTERVAL '14 days'
    ''')
    r = cur.fetchone()
    print(f"[近 14 天] 總計：{r['total']}場 | 命中：{r['hits']} | 未命中：{r['misses']} | 命中率：{r['hit_rate']}%")
    
    # 近 30 天整體統計
    cur.execute('''
    SELECT 
        COUNT(*) as total,
        COUNT(*) FILTER (WHERE ai_is_hit = true) as hits,
        ROUND(COUNT(*) FILTER (WHERE ai_is_hit = true) * 100.0 / NULLIF(COUNT(*),0), 2) as hit_rate
    FROM predictx.games g
    JOIN predictx.game_analysis ga ON g.game_id = ga.game_id
    JOIN predictx.teams t ON g.home_team_id = t.team_id
    WHERE t.league = 'MLB'
      AND g.home_team_score IS NOT NULL
      AND g.away_team_score IS NOT NULL
      AND g.match_date >= CURRENT_DATE - INTERVAL '30 days'
    ''')
    r = cur.fetchone()
    print(f"[近 30 天] 總計：{r['total']}場 | 命中：{r['hits']} | 命中率：{r['hit_rate']}%")
    
    # 信心度區間分析（近 30 天）
    print("\n=== 信心度區間命中率 (近 30 天) ===")
    cur.execute('''
    SELECT 
        CASE 
            WHEN ai_confidence >= 9 THEN '9-10 (極高)'
            WHEN ai_confidence >= 7 THEN '7-8 (高)'
            WHEN ai_confidence >= 5 THEN '5-6 (中)'
            ELSE '1-4 (低)'
        END as conf_range,
        COUNT(*) as total,
        COUNT(*) FILTER (WHERE ai_is_hit = true) as hits,
        ROUND(COUNT(*) FILTER (WHERE ai_is_hit = true) * 100.0 / NULLIF(COUNT(*),0), 2) as hit_rate,
        AVG(ai_confidence) as avg_conf
    FROM predictx.games g
    JOIN predictx.game_analysis ga ON g.game_id = ga.game_id
    JOIN predictx.teams t ON g.home_team_id = t.team_id
    WHERE t.league = 'MLB'
      AND g.home_team_score IS NOT NULL
      AND g.away_team_score IS NOT NULL
      AND g.match_date >= CURRENT_DATE - INTERVAL '30 days'
      AND ai_confidence IS NOT NULL
    GROUP BY conf_range
    ORDER BY 
        CASE 
            WHEN ai_confidence >= 9 THEN 1
            WHEN ai_confidence >= 7 THEN 2
            WHEN ai_confidence >= 5 THEN 3
            ELSE 4
        END
    ''')
    
    for row in cur.fetchall():
        bar = '█' * int(row['hit_rate'] / 10)
        print(f"{row['conf_range']:12} | {row['total']:2}場 | 命中{row['hits']:2} | {row['hit_rate']:5.1f}% {bar}")
    
    # 檢查高信心度（>=8）的命中率
    print("\n=== 高信心度 (>=8) 分析 ===")
    cur.execute('''
    SELECT 
        COUNT(*) as total,
        COUNT(*) FILTER (WHERE ai_is_hit = true) as hits,
        ROUND(COUNT(*) FILTER (WHERE ai_is_hit = true) * 100.0 / NULLIF(COUNT(*),0), 2) as hit_rate
    FROM predictx.games g
    JOIN predictx.game_analysis ga ON g.game_id = ga.game_id
    JOIN predictx.teams t ON g.home_team_id = t.team_id
    WHERE t.league = 'MLB'
      AND g.home_team_score IS NOT NULL
      AND g.away_team_score IS NOT NULL
      AND g.match_date >= CURRENT_DATE - INTERVAL '30 days'
      AND ai_confidence >= 8
    ''')
    r = cur.fetchone()
    print(f"信心度 >=8: {r['total']}場 | 命中{r['hits']} | 命中率：{r['hit_rate']}%")
    
    # 檢查未命中場次的信心度分佈
    print("\n=== 未命中場次的信心度分佈 ===")
    cur.execute('''
    SELECT 
        CASE 
            WHEN ai_confidence >= 9 THEN '9-10'
            WHEN ai_confidence >= 7 THEN '7-8'
            WHEN ai_confidence >= 5 THEN '5-6'
            ELSE '1-4'
        END as conf_range,
        COUNT(*) as count
    FROM predictx.games g
    JOIN predictx.game_analysis ga ON g.game_id = ga.game_id
    JOIN predictx.teams t ON g.home_team_id = t.team_id
    WHERE t.league = 'MLB'
      AND g.home_team_score IS NOT NULL
      AND g.away_team_score IS NOT NULL
      AND g.match_date >= CURRENT_DATE - INTERVAL '30 days'
      AND ai_is_hit = false
      AND ai_confidence IS NOT NULL
    GROUP BY conf_range
    ORDER BY 
        CASE 
            WHEN ai_confidence >= 9 THEN 1
            WHEN ai_confidence >= 7 THEN 2
            WHEN ai_confidence >= 5 THEN 3
            ELSE 4
        END
    ''')
    
    total_miss_high_conf = 0
    for row in cur.fetchall():
        if row['conf_range'] in ['9-10', '7-8']:
            total_miss_high_conf += row['count']
        print(f"{row['conf_range']:6} | {row['count']}場未命中")
    
    print(f"\n⚠️  高信心度未命中 (>=7): {total_miss_high_conf}場")
    
    cur.close()
    conn.close()
    print("\n=== 分析完成 ===")

if __name__ == '__main__':
    main()