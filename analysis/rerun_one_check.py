#!/usr/bin/env python3
"""單場重跑分析（用當前部署預設模型），看模型獨立推演結果"""
import os, sys, json, psycopg2
from psycopg2.extras import RealDictCursor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from analysis_engine import AnalysisEngine

GAME_PREFIX = os.getenv('GAME_PREFIX')
LEAGUE = os.getenv('LEAGUE', 'MLB')
TARGET_DATE = os.getenv('TARGET_DATE', '2026-07-10')

def _norm_url():
    url = os.getenv('DATABASE_URL', '')
    if 'postgres.railway.internal' in url:
        os.environ['DATABASE_URL'] = url.replace('postgres.railway.internal:5432', 'thomas.proxy.rlwy.net:49887')

def main():
    _norm_url()
    engine = AnalysisEngine()
    cur = engine.conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('''
        SELECT g.game_id::text
        FROM predictx.games g
        JOIN predictx.teams th ON g.home_team_id = th.team_id
        WHERE th.league = %s AND g.match_date = %s
          AND g.game_id::text LIKE %s
    ''', (LEAGUE, TARGET_DATE, GAME_PREFIX + '%'))
    gid = cur.fetchone()
    cur.close()
    if not gid:
        print(f"找不到 {GAME_PREFIX}")
        engine.close()
        return
    full_id = gid['game_id']
    print(f"重跑單場: {full_id[:8]} (模型={os.getenv('CLOUD_LLM_PROVIDER')}/{os.getenv('CLOUD_LLM_MODEL')})")

    res = engine.analyze_game(full_id)
    if res:
        print(f"  conf={res.get('confidence')}")
        print(f"  home_win_probability={res.get('home_win_probability')}")
        print(f"  away_win_probability={res.get('away_win_probability')}")
        print(f"  predicted_score={res.get('predicted_score')}")
        print(f"  summary={(res.get('summary') or '')[:200]}")
    else:
        print("  ✗ 無結果 (fallback)")
    engine.close()

if __name__ == '__main__':
    main()
