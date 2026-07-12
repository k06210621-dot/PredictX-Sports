#!/usr/bin/env python3
"""對 2026-06-14 NPB 6 場結算（原始預測 vs 實際比分），不影響其他場次"""
import os, sys, psycopg2, json
from psycopg2.extras import RealDictCursor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from settlement_engine import SettlementEngine

TARGET_DATE = '2026-06-14'
LEAGUE = 'NPB'

def main():
    url = os.getenv('DATABASE_URL', '')
    if 'postgres.railway.internal' in url:
        os.environ['DATABASE_URL'] = url.replace('postgres.railway.internal:5432', 'thomas.proxy.rlwy.net:49887')

    settler = SettlementEngine()
    cur = settler.conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('''
        SELECT g.game_id::text, g.home_team_score, g.away_team_score, ga.analysis_data
        FROM predictx.games g
        JOIN predictx.game_analysis ga ON g.game_id = ga.game_id
        JOIN predictx.teams th ON g.home_team_id = th.team_id
        WHERE th.league = %s AND g.match_date = %s
          AND g.home_team_score IS NOT NULL AND g.away_team_score IS NOT NULL
    ''', (LEAGUE, TARGET_DATE))
    rows = cur.fetchall()
    cur.close()

    print(f"準備結算 {len(rows)} 場")
    for r in rows:
        settler._settle_win_loss(
            r['game_id'], float(r['home_team_score']),
            float(r['away_team_score']), r['analysis_data']
        )
    settler.conn.commit()
    settler.close()
    print("結算完成")

if __name__ == '__main__':
    main()
