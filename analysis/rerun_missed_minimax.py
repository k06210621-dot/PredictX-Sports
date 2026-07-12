#!/usr/bin/env python3
"""對指定日期+聯盟 is_hit=False 的場次，用 MINIMAX-M3 重新分析+結算"""
import os, sys, json, gzip, psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ['CLOUD_LLM_PROVIDER'] = 'nvidia'
os.environ['CLOUD_LLM_MODEL'] = 'minimaxai/minimax-m3'

from analysis_engine import AnalysisEngine
from settlement_engine import SettlementEngine

TARGET_DATE = os.getenv('TARGET_DATE', '2026-06-20')
LEAGUE = os.getenv('LEAGUE', 'NPB')

def _norm_url():
    url = os.getenv('DATABASE_URL', '')
    if 'postgres.railway.internal' in url:
        os.environ['DATABASE_URL'] = url.replace('postgres.railway.internal:5432', 'thomas.proxy.rlwy.net:49887')

def backup(conn, ids):
    if not ids:
        return
    cur = conn.cursor(cursor_factory=RealDictCursor)
    placeholders = ','.join(['%s'] * len(ids))
    cur.execute(f'''
        SELECT g.game_id::text, g.match_date::text, th.english_name as home, ta.english_name as away,
               g.home_team_score, g.away_team_score, ga.analysis_data
        FROM predictx.games g
        JOIN predictx.game_analysis ga ON g.game_id = ga.game_id
        JOIN predictx.teams th ON g.home_team_id = th.team_id
        JOIN predictx.teams ta ON g.away_team_id = ta.team_id
        WHERE g.game_id::text IN ({placeholders})
    ''', ids)
    rows = cur.fetchall()
    cur.close()
    data = [{'game_id': r['game_id'], 'match_date': str(r['match_date']), 'home_team': r['home'],
             'away_team': r['away'], 'home_team_score': r['home_team_score'],
             'away_team_score': r['away_team_score'], 'analysis_data': r['analysis_data']} for r in rows]
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    fn = f'backup/{LEAGUE}_{TARGET_DATE.replace("-","")}_missed_orig_{ts}.json.gz'
    with gzip.open(fn, 'wt', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    print(f'備份 {len(data)} 場 -> {fn}')

def save_no_push(conn, game_id, result):
    if not result:
        return False
    cur = conn.cursor()
    try:
        cur.execute("SELECT pitcher_updated_at FROM predictx.games WHERE game_id = %s::uuid", (game_id,))
        p = cur.fetchone()
        cur.execute(
            """INSERT INTO predictx.game_analysis (game_id, analysis_data, updated_at, last_analyzed_pitcher_update)
               VALUES (%s, %s, CURRENT_TIMESTAMP, %s)
               ON CONFLICT (game_id)
               DO UPDATE SET analysis_data = EXCLUDED.analysis_data,
                             updated_at = CURRENT_TIMESTAMP,
                             last_analyzed_pitcher_update = EXCLUDED.last_analyzed_pitcher_update""",
            (game_id, json.dumps(result), p['pitcher_updated_at'] if p else None)
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"  ❌ save error {game_id[:8]}: {e}")
        conn.rollback()
        return False
    finally:
        cur.close()

def main():
    _norm_url()
    engine = AnalysisEngine()
    cur = engine.conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('''
        SELECT g.game_id::text, ga.analysis_data->'actual_result'->>'is_hit' as is_hit
        FROM predictx.games g
        JOIN predictx.game_analysis ga ON g.game_id = ga.game_id
        JOIN predictx.teams th ON g.home_team_id = th.team_id
        WHERE th.league = %s AND g.match_date = %s
          AND g.home_team_score IS NOT NULL AND g.away_team_score IS NOT NULL
    ''', (LEAGUE, TARGET_DATE))
    missed = [r['game_id'] for r in cur.fetchall() if str(r['is_hit']).lower() == 'false']
    cur.close()
    print(f"{LEAGUE} {TARGET_DATE} 命中失敗場次: {len(missed)} -> {[i[:8] for i in missed]}")

    if not missed:
        engine.close()
        return

    backup(engine.conn, missed)

    ids_full = missed
    for idx, gid in enumerate(ids_full):
        try:
            res = engine.analyze_game(gid)
            if res:
                ok = save_no_push(engine.conn, gid, res)
                print(f"  [{idx+1}/{len(ids_full)}] {'✓' if ok else '✗'} {gid[:8]}... conf={res.get('confidence')}")
            else:
                print(f"  [{idx+1}/{len(ids_full)}] ✗ {gid[:8]}... no result")
        except Exception as e:
            print(f"  [{idx+1}/{len(ids_full)}] ✗ {gid[:8]}... error: {e}")
    engine.close()

    settler = SettlementEngine()
    cur = settler.conn.cursor(cursor_factory=RealDictCursor)
    placeholders = ','.join(['%s'] * len(ids_full))
    cur.execute(f'''
        SELECT g.game_id::text, g.home_team_score, g.away_team_score, ga.analysis_data
        FROM predictx.games g
        JOIN predictx.game_analysis ga ON g.game_id = ga.game_id
        WHERE g.game_id::text IN ({placeholders})
    ''', ids_full)
    rows = cur.fetchall()
    cur.close()
    for r in rows:
        settler._settle_win_loss(r['game_id'], float(r['home_team_score']), float(r['away_team_score']), r['analysis_data'])
    settler.conn.commit()
    settler.close()
    print("MINIMAX-M3 重跑+結算完成")

if __name__ == '__main__':
    main()
