#!/usr/bin/env python3
import os, sys, json, psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone

sys.path.insert(0, '/Users/jero/PredictX Sports/analysis')

with open('/tmp/railway_pg.json') as f:
    pg = json.load(f)
DB_URL = f"postgresql://postgres:{pg['PGPASSWORD']}@thomas.proxy.rlwy.net:49887/railway"

os.environ['CLOUD_LLM_PROVIDER'] = 'nvidia'
os.environ['CLOUD_LLM_MODEL'] = 'minimaxai/minimax-m3'
os.environ['CLOUD_LLM_URL'] = 'https://integrate.api.nvidia.com/v1/chat/completions'

GAME_ID = 'dea296e4-75a3-4e7e-b6b8-c78e45c11d97'

def main():
    conn = psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    from analysis_engine import AnalysisEngine
    engine = AnalysisEngine(conn=conn)

    print(f"🔍 重新分析 {GAME_ID} (Mariners vs Reds)...")
    try:
        result = engine.analyze_game(GAME_ID)
        if not result:
            print("❌ 分析失敗")
            return

        # 讀取現有 analysis_data，保留其他欄位，覆寫本次分析結果
        cur.execute("SELECT analysis_data FROM predictx.game_analysis WHERE game_id=%s::uuid", (GAME_ID,))
        row = cur.fetchone()
        existing = row['analysis_data'] if row and row['analysis_data'] else {}

        # 標準化結果（確保數值型態正確）
        merged = dict(existing)
        merged.update({
            'home_win_probability': float(result.get('home_win_probability', 0)),
            'away_win_probability': float(result.get('away_win_probability', 0)),
            'confidence': int(result.get('confidence', 0)),
            'predicted_score': result.get('predicted_score', ''),
            'summary': result.get('summary', ''),
            'key_factors': result.get('key_factors', []),
            'radar_chart': result.get('radar_chart', {}),
            'model_used': 'minimax-m3 (fallback computed)',
            'reanalyzed_at': datetime.now(timezone.utc).isoformat(),
        })

        # 若原先已有 actual_result（結算資料），保留
        if isinstance(existing, dict) and existing.get('actual_result'):
            merged['actual_result'] = existing['actual_result']

        cur.execute("""
            INSERT INTO predictx.game_analysis (game_id, analysis_data, updated_at)
            VALUES (%s::uuid, %s::jsonb, CURRENT_TIMESTAMP)
            ON CONFLICT (game_id)
            DO UPDATE SET analysis_data = EXCLUDED.analysis_data,
                          updated_at = CURRENT_TIMESTAMP
        """, (GAME_ID, json.dumps(merged, ensure_ascii=False)))

        conn.commit()
        print("✅ 已寫回 DB (UPSERT game_analysis)")
        print(f"   主隊勝率: {merged['home_win_probability']:.1%} | 客隊: {merged['away_win_probability']:.1%} | 信心: {merged['confidence']}/10")
        print(f"   預測比分: {merged['predicted_score']}")
        print(f"   model_used: {merged['model_used']}")
    except Exception as e:
        conn.rollback()
        print(f"❌ 寫入失敗: {e}")
        import traceback; traceback.print_exc()
    finally:
        engine.close(); cur.close(); conn.close()

if __name__ == '__main__':
    main()
