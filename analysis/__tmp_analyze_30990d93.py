#!/usr/bin/env python3
import os, sys, json, psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

sys.path.insert(0, '/Users/jero/PredictX Sports/analysis')

with open('/tmp/railway_pg.json') as f:
    pg = json.load(f)
DB_URL = f"postgresql://postgres:{pg['PGPASSWORD']}@thomas.proxy.rlwy.net:49887/railway"

os.environ['CLOUD_LLM_PROVIDER'] = 'nvidia'
os.environ['CLOUD_LLM_MODEL'] = 'minimaxai/minimax-m3'
os.environ['CLOUD_LLM_URL'] = 'https://integrate.api.nvidia.com/v1/chat/completions'

def main():
    conn = psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    GAME_ID = '30990d93-e7c4-4cf7-a901-538420464e73'
    print(f"🎯 目標場次: Hanshin Tigers vs Yokohama DeNA BayStars (game_id={GAME_ID}...)")
    print(f"📅 日期: 2026-07-22")
    print(f"⏰ 執行時間: {datetime.now().isoformat()}")
    print("="*60)

    from analysis_engine import AnalysisEngine
    engine = AnalysisEngine(conn=conn)

    print("🤖 使用模型: minimax-m3 (NVIDIA)")
    print("🔍 開始分析 (含 Recipe 8 傷兵權重 + Recipe 6 投手 K/BB)...\n")

    try:
        result = engine.analyze_game(GAME_ID)
        if not result:
            print("❌ 分析失敗 (可能 LLM 輸出不完整，已 fallback 規則)")
            return

        print("="*60)
        print("📊 分析結果")
        print("="*60)
        hp = result.get('home_win_probability', 0)
        ap = result.get('away_win_probability', 0)
        conf = result.get('confidence', 0)
        print(f"主隊勝率 (阪神):  {hp:.1%}")
        print(f"客隊勝率 (DeNA):  {ap:.1%}")
        print(f"信心度:           {conf}/10")
        print(f"預測比分:         {result.get('predicted_score', 'N/A')}")

        summary = result.get('summary', '')
        if summary:
            print(f"\n📝 摘要:")
            print(summary if len(summary) <= 500 else summary[:500] + "...")

        kf = result.get('key_factors', [])
        if kf:
            print(f"\n🔑 關鍵因素:")
            items = kf if isinstance(kf, list) else [kf]
            for i, x in enumerate(items[:6], 1):
                print(f"  {i}. {x}")

        radar = result.get('radar_chart', {})
        if radar:
            print(f"\n📈 六維雷達:")
            for k, v in radar.items():
                if isinstance(v, (int, float)):
                    print(f"  {k}: {v:.2f}")
                else:
                    print(f"  {k}: {v}")

        # Recipe 檢查
        if '[傷兵校正]' in summary:
            print(f"\n✅ Recipe 8 傷兵權重調整已套用")
        if '[投手參數校正]' in summary or '[投手近況校正]' in summary:
            print(f"✅ Recipe 6 投手校正已套用")
        if '[投手參數校正]' not in summary and '[傷兵校正]' not in summary:
            print(f"\nℹ️  本場未觸發傷兵/投手後處理調整 (資料對稱或差距 < 閾值)")

        print("\n" + "="*60)
        print("✅ 分析完成")
    except Exception as e:
        print(f"❌ 分析例外: {e}")
        import traceback; traceback.print_exc()
    finally:
        engine.close(); cur.close(); conn.close()

if __name__ == '__main__':
    main()
