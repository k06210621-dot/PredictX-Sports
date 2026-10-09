#!/usr/bin/env python3
"""
NBA 季前賽失敗場次 — 改用替代 AI 模型重新分析
================================================
用途：對 10/03-10/09 預測失敗場次，改用不同的 LLM 模型重跑，
      以對照「換模型是否能提升準確率」。

模型：Nous Portal `deepseek/deepseek-v4-flash`
      （與現行 deepseek-v4.1-flash 不同的模型，JSON 格式已實測穩定）

安全設計：
- 先備份現有分析結果（含預測），供比較用
- save_analysis_multi：寫入 game_analysis + ai_prediction_history
  + analysis_data 內記錄 model_used（供區分不同模型的產出）
- 不觸發 APNs 推播（歷史場次）
"""
import os, sys, json, datetime

sys.path.insert(0, "/Users/jero/PredictX Sports/analysis")
os.chdir("/Users/jero/PredictX Sports/analysis")

url = open('/tmp/dburl.env').read().strip()
os.environ['DATABASE_URL'] = url
os.environ['DATABASE_PUBLIC_URL'] = url
os.environ['PREDICTX_MODEL'] = 'cloud'
# 切換到替代模型
os.environ['CLOUD_LLM_PROVIDER'] = 'nous'
os.environ['CLOUD_LLM_MODEL'] = 'deepseek/deepseek-v4-flash'

import psycopg2
from psycopg2.extras import RealDictCursor
from decimal import Decimal

MODEL_TAG = 'deepseek/deepseek-v4-flash'


def _jd(o):
    if isinstance(o, (datetime.date, datetime.datetime)):
        return o.isoformat()
    if isinstance(o, Decimal):
        return float(o)
    return str(o)


def save_multi(conn, game_id, result, model_tag):
    """寫入分析結果，並在 analysis_data 記錄模型（供多模型對照）"""
    if not result:
        return False
    result = dict(result)
    result['_model'] = model_tag
    cur = conn.cursor()
    try:
        cur.execute("SELECT pitcher_updated_at FROM predictx.games WHERE game_id=%s::uuid", (game_id,))
        p = cur.fetchone()
        cur.execute("""
            INSERT INTO predictx.game_analysis (game_id, analysis_data, updated_at, last_analyzed_pitcher_update)
            VALUES (%s::uuid, %s::jsonb, CURRENT_TIMESTAMP, %s)
            ON CONFLICT (game_id) DO UPDATE SET
                analysis_data = EXCLUDED.analysis_data,
                updated_at = CURRENT_TIMESTAMP,
                last_analyzed_pitcher_update = EXCLUDED.last_analyzed_pitcher_update
        """, (game_id, json.dumps(result, ensure_ascii=False, default=_jd),
              p['pitcher_updated_at'] if p else None))
        cur.execute("""
            SELECT t_h.league AS lg, t_h.english_name AS hn, t_a.english_name AS an
            FROM predictx.games g
            JOIN predictx.teams t_h ON g.home_team_id=t_h.team_id
            JOIN predictx.teams t_a ON g.away_team_id=t_a.team_id
            WHERE g.game_id=%s::uuid
        """, (game_id,))
        gr = cur.fetchone()
        if gr:
            # 用 model 專屬的 prompt_version 區分不同模型的預測快照
            cur.execute("""
                INSERT INTO predictx.ai_prediction_history
                    (game_id, league, prediction_time, home_team, away_team,
                     home_win_probability, away_win_probability, confidence, predicted_score, prompt_version)
                VALUES (%s::uuid, %s, NOW(), %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (game_id, prompt_version) DO UPDATE SET
                    home_win_probability=EXCLUDED.home_win_probability,
                    away_win_probability=EXCLUDED.away_win_probability,
                    confidence=EXCLUDED.confidence,
                    predicted_score=EXCLUDED.predicted_score,
                    prediction_time=NOW()
            """, (game_id, gr['lg'], gr['hn'], gr['an'],
                  result.get('home_win_probability'), result.get('away_win_probability'),
                  result.get('confidence'), str(result.get('predicted_score') or '')[:10],
                  f"v3-{model_tag.replace('/', '-')}"))
        conn.commit()
        return True
    except Exception as e:
        print(f"    ❌ save error: {e}")
        conn.rollback()
        return False
    finally:
        cur.close()


def main():
    conn = psycopg2.connect(url, cursor_factory=RealDictCursor)
    cur = conn.cursor()
    cur.execute("""
        SELECT g.game_id::text, g.match_date::text,
               ht.english_name AS home, at.english_name AS away,
               g.home_team_score AS hs, g.away_team_score AS a_s,
               ga.analysis_data->>'predicted_score' AS old_pred,
               ga.analysis_data->>'home_win_probability' AS old_hp,
               ga.analysis_data->>'confidence' AS old_conf
        FROM predictx.games g
        JOIN predictx.teams ht ON g.home_team_id=ht.team_id
        JOIN predictx.teams at ON g.away_team_id=at.team_id
        JOIN predictx.game_analysis ga ON g.game_id=ga.game_id
        WHERE ht.league='NBA' AND g.match_date BETWEEN '2026-10-03' AND '2026-10-09'
          AND ga.analysis_data->'actual_result'->>'is_hit' = 'false'
        ORDER BY g.match_date, at.english_name
    """)
    games = cur.fetchall()
    cur.close()

    # 備份現況
    bk = f"/Users/jero/自動生成文件/backups/nba_failed_before_{MODEL_TAG.replace('/','-')}_{datetime.datetime.now():%Y%m%d_%H%M%S}.json"
    os.makedirs(os.path.dirname(bk), exist_ok=True)
    with open(bk, 'w') as f:
        json.dump([dict(g) for g in games], f, ensure_ascii=False, indent=1, default=_jd)
    print(f"現況已備份: {bk}\n")

    print(f"=== 改用 {MODEL_TAG} 重跑失敗場次: {len(games)} 場 ===\n")
    from analysis_engine import AnalysisEngine
    engine = AnalysisEngine(conn=conn)

    ok = fail = 0
    for i, g in enumerate(games, 1):
        gid = g['game_id']
        real_winner = '客' if int(g['a_s']) > int(g['hs']) else '主'
        print(f"[{i}/{len(games)}] {g['match_date']} {g['away']} @ {g['home']}")
        print(f"    實際: {int(g['a_s'])}-{int(g['hs'])}（{real_winner}勝）")
        print(f"    舊（v4.1-flash）: {g['old_pred']} hp={float(g['old_hp']):.2f} conf={g['old_conf']}")
        try:
            res = engine.analyze_game(gid)
            if res and save_multi(conn, gid, res, MODEL_TAG):
                ok += 1
                hp = float(res.get('home_win_probability') or 0.5)
                new_winner = '主' if hp > 0.5 else ('客' if hp < 0.5 else '平')
                correct = (new_winner == real_winner)
                print(f"    新（{MODEL_TAG}）: {res.get('predicted_score')} hp={hp:.2f} conf={res.get('confidence')} → {'✓ 命中' if correct else '✗ 未命中'}")
            else:
                fail += 1
                print("    ✗ 失敗（保留舊值）")
        except Exception as e:
            fail += 1
            print(f"    ✗ error: {e}")
            try:
                conn.rollback()
            except Exception:
                pass
        print()
    engine.close()
    print(f"=== 完成: OK={ok} FAIL={fail} ===")
    conn.close()


if __name__ == '__main__':
    main()
