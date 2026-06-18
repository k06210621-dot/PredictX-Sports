#!/usr/bin/env python3
"""寫入 Tigers vs Astros 6/17 AI 分析"""
import os, sys, json, psycopg2
from psycopg2.extras import RealDictCursor

database_url = os.getenv('DATABASE_URL')
if database_url:
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    conn = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
else:
    conn = psycopg2.connect(
        dbname='sports_db', user='jero', password='',
        host='localhost', port=5432, cursor_factory=RealDictCursor
    )

game_id = '61b6b115-be70-4743-a8de-2be2a7d2a2bd'

analysis = {
    "summary": "老虎微幅優勢。太空人客場12勝26敗是本場最大弱點，老虎近10場攻擊提升至平均5.6分，牛棚壓制力明顯較佳。Hunter Brown雖然數據漂亮但MLB樣本僅10.2局，存在回歸風險。",
    "key_factors": [
        "太空人客場12勝26敗，勝率31.6%，是本場最大劣勢",
        "老虎近10場攻擊大幅提升，平均得分5.6分",
        "老虎近10場防守出色，平均失分僅3.2分",
        "Hunter Brown ERA 0.84但僅投10.2局，樣本過小",
        "Framber Valdez ERA 4.40但投球局數穩定(77.2局)",
        "老虎牛棚近期壓制力明顯優於太空人"
    ],
    "home_win_probability": 54,
    "away_win_probability": 46,
    "confidence": 68,
    "predicted_score": "老虎 5-4 太空人",
    "radar_chart": {
        "home": {"進攻能力": 80, "投手能力": 78, "近期狀態": 90, "陣容完整度": 80, "主客場": 85},
        "away": {"進攻能力": 82, "投手能力": 86, "近期狀態": 72, "陣容完整度": 82, "主客場": 70}
    },
    "over_under_2_5": True,
    "total_prediction": {
        "line": "7.5",
        "choice": "大分",
        "confidence": 56
    },
    "pitcher_analysis": {
        "home_pitcher": {
            "name": "Framber Valdez",
            "era": 4.40,
            "whip": 1.34,
            "k9": 7.1,
            "record": "3-5",
            "score": 78
        },
        "away_pitcher": {
            "name": "Hunter Brown",
            "era": 0.84,
            "whip": 1.03,
            "k9": 14.3,
            "record": "1-0",
            "score": 86,
            "note": "樣本僅10.2局，可信度降低"
        }
    },
    "team_comparison": {
        "home": {
            "name": "底特律老虎",
            "record": "30勝42敗",
            "home_record": "主場16-20",
            "recent_10": "6勝4敗",
            "avg_score": 4.1,
            "avg_against": 4.2,
            "recent_10_avg_score": 5.6,
            "recent_10_avg_against": 3.2,
            "batting_avg": ".234",
            "obp": ".313",
            "ai_score": 82
        },
        "away": {
            "name": "休士頓太空人",
            "record": "33勝41敗",
            "away_record": "客場12-26",
            "recent_10": "5勝5敗",
            "avg_score": 4.5,
            "avg_against": 5.1,
            "recent_10_avg_score": 4.7,
            "recent_10_avg_against": 5.3,
            "batting_avg": ".231",
            "obp": ".309",
            "ai_score": 78
        }
    },
    "actual_result": None
}

cur = conn.cursor()
cur.execute(
    """INSERT INTO predictx.game_analysis (game_id, analysis_data, updated_at)
       VALUES (%s, %s, CURRENT_TIMESTAMP)
       ON CONFLICT (game_id)
       DO UPDATE SET analysis_data = EXCLUDED.analysis_data, updated_at = CURRENT_TIMESTAMP""",
    (game_id, json.dumps(analysis, ensure_ascii=False))
)
conn.commit()
cur.close()
conn.close()
print("✅ Tigers vs Astros AI 分析已寫入")
