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

GAME_IDS = [
    '77902e9f-12d4-425d-9ea2-4b4497660d60',  # Angels vs Cardinals (Taiwan 7/22)
    '62c79203-5046-4b7f-be70-2952f662850c',  # Diamondbacks vs Athletics (Taiwan 7/22)
]

def main():
    conn = psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    from analysis_engine import AnalysisEngine
    engine = AnalysisEngine(conn=conn)

    for gid in GAME_IDS:
        print("\n" + "#"*70)
        print(f"🎯 重新分析: {gid}")
        print(f"⏰ {datetime.now().isoformat()}")
        print("#"*70)

        # 顯示球隊資訊
        cur.execute("""
            SELECT ht.english_name home, ta.english_name away,
                   g.home_pitcher_name, g.away_pitcher_name, g.match_date
            FROM predictx.games g
            JOIN predictx.teams ht ON g.home_team_id = ht.team_id
            JOIN predictx.teams ta ON g.away_team_id = ta.team_id
            WHERE g.game_id = %s::uuid
        """, (gid,))
        info = cur.fetchone()
        if info:
            print(f"📋 {info['home']} vs {info['away']} ({info['match_date']})")
            print(f"   先發: {info['home_pitcher_name']} / {info['away_pitcher_name']}")

        print("🤖 模型: minimax-m3 (NVIDIA) | Recipe 8 傷兵 + Recipe 6 投手\n")
        try:
            result = engine.analyze_game(gid)
            if not result:
                print("❌ 分析失敗 (LLM fallback 規則)")
                continue

            hp = result.get('home_win_probability', 0)
            ap = result.get('away_win_probability', 0)
            conf = result.get('confidence', 0)
            print(f"主隊勝率: {hp:.1%} | 客隊勝率: {ap:.1%}")
            print(f"信心度:   {conf}/10")
            print(f"預測比分: {result.get('predicted_score','N/A')}")

            summary = result.get('summary', '')
            if summary:
                print(f"\n📝 摘要:\n{(summary[:600]+'...') if len(summary)>600 else summary}")

            kf = result.get('key_factors', [])
            if kf:
                print(f"\n🔑 關鍵因素:")
                for i, x in enumerate((kf if isinstance(kf, list) else [kf])[:6], 1):
                    print(f"  {i}. {x}")

            radar = result.get('radar_chart', {})
            if radar:
                print(f"\n📈 六維雷達:")
                for k, v in radar.items():
                    if isinstance(v, (int, float)):
                        print(f"  {k}: {v:.2f}")
                    else:
                        print(f"  {k}: {v}")

            tags = []
            if '[傷兵校正]' in summary: tags.append('Recipe 8 傷兵')
            if '[投手參數校正]' in summary or '[投手近況校正]' in summary: tags.append('Recipe 6 投手')
            if tags:
                print(f"\n✅ 已套用: {', '.join(tags)}")
            else:
                print(f"\nℹ️  本場未觸發傷兵/投手後處理 (差距 < 閾值)")

        except Exception as e:
            print(f"❌ 例外: {e}")
            import traceback; traceback.print_exc()

    engine.close(); cur.close(); conn.close()
    print("\n" + "#"*70)
    print("✅ 兩場重新分析完成")

if __name__ == '__main__':
    main()
