#!/usr/bin/env python3
"""單獨分析指定 NPB 賽事（阪神虎 vs 橫濱 DeNA 海灣之星）- 2026-07-22"""
import os
import sys
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 設定環境（模擬 Railway 環境）
os.environ['CLOUD_LLM_PROVIDER'] = 'nvidia'
os.environ['CLOUD_LLM_MODEL'] = 'minimaxai/minimax-m3'
os.environ['CLOUD_LLM_URL'] = 'https://integrate.api.nvidia.com/v1/chat/completions'

import psycopg2
from psycopg2.extras import RealDictCursor
from analysis_engine import AnalysisEngine


def main():
    # 連線資料庫
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print("❌ 請先設定 DATABASE_URL 環境變數")
        return

    # 如果是 Railway 內部網址，改用 proxy
    if 'postgres.railway.internal' in db_url:
        db_url = db_url.replace('postgres.railway.internal:5432', 'thomas.proxy.rlwy.net:49887')

    conn = psycopg2.connect(db_url)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # 查詢 2026-07-22 阪神虎 vs 橫濱 DeNA 海灣之星的賽事
    print("🔍 查詢 2026-07-22 阪神虎 vs 橫濱 DeNA 海灣之星賽事...")
    cur.execute('''
        SELECT
            g.game_id,
            g.match_date,
            g.home_team_id,
            g.away_team_id,
            th.team_name_zh as home_team,
            ta.team_name_zh as away_team,
            g.home_pitcher_name,
            g.away_pitcher_name,
            g.venue
        FROM predictx.games g
        JOIN predictx.teams th ON g.home_team_id = th.team_id
        JOIN predictx.teams ta ON g.away_team_id = ta.team_id
        WHERE th.league = 'NPB'
          AND ta.league = 'NPB'
          AND g.match_date = '2026-07-22'
          AND (th.team_name_zh LIKE '%虎%' AND ta.team_name_zh LIKE '%海灣%'
               OR th.team_name_zh LIKE '%阪神%' AND ta.team_name_zh LIKE '%DeNA%')
        LIMIT 1
    ''')

    game = cur.fetchone()
    if not game:
        print("❌ 找不到該場賽事，請確認日期或球隊名稱")
        print("嘗試查詢所有 2026-07-22 NPB 賽事：")
        cur.execute('''
            SELECT
                g.game_id,
                th.team_name_zh as home_team,
                ta.team_name_zh as away_team,
                g.match_date
            FROM predictx.games g
            JOIN predictx.teams th ON g.home_team_id = th.team_id
            JOIN predictx.teams ta ON g.away_team_id = ta.team_id
            WHERE th.league = 'NPB'
              AND g.match_date = '2026-07-22'
            LIMIT 5
        ''')
        for r in cur.fetchall():
            print(f"  - {r['match_date']} | {r['home_team']} vs {r['away_team']} (id: {r['game_id']})")
        cur.close()
        conn.close()
        return

    print(f"\n✅ 找到賽事：")
    print(f"   日期：{game['match_date']}")
    print(f"   主隊：{game['home_team']} (ID: {game['home_team_id']})")
    print(f"   客隊：{game['away_team']} (ID: {game['away_team_id']})")
    print(f"   場地：{game.get('venue', '未設定')}")
    print(f"   Game ID：{game['game_id']}")
    print(f"   先發投手：主={game['home_pitcher_name']}, 客={game['away_pitcher_name']}")

    # 執行分析（不觸發推播）
    print("\n🤖 開始 AI 分析（使用 minimax-m3）...")
    engine = AnalysisEngine()

    try:
        result = engine.analyze_game(game['game_id'])

        if result:
            print("\n" + "="*60)
            print(f"📊 分析結果：{game['home_team']} vs {game['away_team']}")
            print("="*60)

            # 基本資訊
            print(f"\n預測主隊勝率：{result.get('home_win_probability', 'N/A')}")
            print(f"預測客隊勝率：{result.get('away_win_probability', 'N/A')}")
            print(f"信心度：{result.get('confidence', 'N/A')}/10")

            # 預測比分
            predicted_score = result.get('predicted_score', 'N/A')
            print(f"\n預測比分：{predicted_score}")

            # 摘要
            summary = result.get('summary', '')
            if summary:
                print(f"\n📝 賽事分析摘要：")
                print(f"{summary}")

            # 關鍵因素
            key_factors = result.get('key_factors', [])
            if key_factors:
                print(f"\n🔑 關鍵因素：")
                if isinstance(key_factors, list):
                    for i, factor in enumerate(key_factors, 1):
                        print(f"  {i}. {factor}")
                else:
                    print(f"  {key_factors}")

            # 雷達圖數據
            radar = result.get('radar_chart', {})
            if radar:
                print(f"\n📈 六維雷達圖數據：")
                for key, value in radar.items():
                    if isinstance(value, (int, float)):
                        print(f"  {key}: {value:.2f}")
                    else:
                        print(f"  {key}: {value}")

            # 風險因素
            risk = result.get('risk_factors', '')
            if risk:
                print(f"\n⚠️  風險因素：{risk}")

            # 注入資料來源
            sources = result.get('sources', [])
            if sources:
                print(f"\n📡 資料來源：{', '.join(sources)}")

            print("\n" + "="*60)
            print("✅ 分析完成")
        else:
            print("\n❌ 分析失敗：AI 模型未返回結果")

    except Exception as e:
        print(f"\n❌ 分析過程出錯：{e}")
        import traceback
        traceback.print_exc()
    finally:
        engine.close()
        cur.close()
        conn.close()


if __name__ == '__main__':
    main()