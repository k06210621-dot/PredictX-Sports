#!/usr/bin/env python3
"""更新 Tigers vs Astros 6/17 詳細 AI 分析"""
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
    "summary": "比賽傾向：老虎微幅優勢。主要原因：太空人客場12勝26敗，是本場最大弱點；老虎近10場攻擊提升，平均5.6分；老虎牛棚近期壓制力明顯較佳。Hunter Brown雖然數據漂亮，但MLB樣本僅10.2局，存在回歸風險。",
    "key_factors": [
        "太空人客場12勝26敗，勝率31.6%，是本場最大弱點",
        "老虎近10場攻擊大幅提升，平均得分5.6分",
        "老虎近10場防守出色，平均失分僅3.2分", 
        "Hunter Brown ERA 0.84但僅投10.2局，樣本過小存在回歸風險",
        "Framber Valdez ERA 4.40但投球局數穩定(77.2局)",
        "老虎牛棚近期壓制力明顯優於太空人",
        "老虎面對左投7勝14敗明顯弱項，此戰由Valdez（左投）登板對此有利",
        "太空人長期得分能力較佳但近期略下降",
        "兩隊平均失分偏高支持大分7.5"
    ],
    "home_win_probability": 54,
    "away_win_probability": 46,
    "confidence": 68,
    "predicted_score": "老虎 5-4 太空人",
    "radar_chart": {
        "home": {
            "進攻能力": 80,
            "投手能力": 78,
            "近期狀態": 90,
            "陣容完整度": 80,
            "主客場": 85
        },
        "away": {
            "進攻能力": 82,
            "投手能力": 86,
            "近期狀態": 72,
            "陣容完整度": 82,
            "主客場": 70
        }
    },
    "win_model": {
        "weights": {
            "先發投手": 40,
            "打線": 25,
            "近期狀態": 20,
            "主客場": 15
        },
        "home_win_rate": 54,
        "away_win_rate": 46
    },
    "score_prediction": {
        "most_likely": "老虎 5 : 4 太空人",
        "other_possibilities": [
            "老虎 4 : 3 太空人",
            "太空人 5 : 4 老虎"
        ]
    },
    "total_prediction": {
        "line": "7.5",
        "choice": "大分",
        "confidence": 56,
        "analysis": {
            "support_over": [
                "兩隊平均失分偏高",
                "太空人客場防守差",
                "老虎近期火力提升"
            ],
            "support_under": [
                "Hunter Brown近期壓制力強",
                "Valdez若恢復王牌狀態"
            ]
        }
    },
    "pitcher_analysis": {
        "home_pitcher": {
            "name": "Framber Valdez",
            "hand": "左投",
            "season_record": "3-5",
            "era": 4.40,
            "whip": 1.34,
            "batting_average_against": ".249",
            "innings_pitched": 77.2,
            "strikeouts": 61,
            "recent_performance": [
                {
                    "date": "6/11",
                    "opponent": "雙城",
                    "innings": 5,
                    "runs_allowed": 4,
                    "result": "負敗"
                },
                {
                    "date": "6/6", 
                    "opponent": "水手",
                    "innings": 5,
                    "runs_allowed": 1,
                    "result": "勝"
                }
            ],
            "strengths": [
                "左投先發",
                "投球局數穩定",
                "三振能力仍存在"
            ],
            "weaknesses": [
                "ERA 4.40偏高",
                "WHIP 1.34代表容易讓跑者上壘",
                "最近表現不穩"
            ],
            "score": 78
        },
        "away_pitcher": {
            "name": "Hunter Brown",
            "hand": "右投",
            "season_record": "1-0",
            "era": 0.84,
            "whip": 1.03,
            "batting_average_against": ".135",
            "innings_pitched": 10.2,
            "strikeouts": 17,
            "recent_performance": [
                {
                    "date": "4/1",
                    "innings": 6,
                    "runs_allowed": 1,
                    "strikeouts": 8,
                    "note": "6局失1分8K"
                },
                {
                    "date": "3/27",
                    "innings": 4.2,
                    "runs_allowed": 0,
                    "strikeouts": 9,
                    "note": "4.2局無失分9K"
                }
            ],
            "strengths": [
                "ERA 0.84極低",
                "被擊打率 .135極優",
                "三振率極高"
            ],
            "weaknesses": [
                "樣本太小僅10.2局",
                "MLB AI模型會降低可信度",
                "長局數能力未知"
            ],
            "score": 86
        },
        "duel_analysis": {
            "raw_comparison": "Hunter Brown > Valdez",
            "adjusted_for_sample_size": "差距縮小",
            "advantages": {
                "short_term_dominance": "太空人",
                "stability": "老虎",
                "long_inning_ability": "老虎略優"
            }
        }
    },
    "team_comparison": {
        "home": {
            "name": "底特律老虎",
            "record": "30勝42敗",
            "home_record": "主場16-20",
            "away_record": "客場14-22",
            "recent_10": "6勝4敗",
            "recent_trend": "🔥1連勝",
            "avg_runs_scored": 4.1,
            "avg_runs_allowed": 4.2,
            "recent_10_avg_runs": 5.6,
            "recent_10_avg_allowed": 3.2,
            "batting_average": ".234",
            "on_base_percentage": ".313",
            "ai_offense_score": 80,
            "ai_pitching_score": 78,
            "ai_recent_form": 90,
            "ai_roster_complete": 80
        },
        "away": {
            "name": "休士頓太空人",
            "record": "33勝41敗",
            "home_record": "主場21-15",
            "away_record": "客場12-26",
            "recent_10": "5勝5敗",
            "recent_trend": "❌2連敗",
            "avg_runs_scored": 4.5,
            "avg_runs_allowed": 5.1,
            "recent_10_avg_runs": 4.7,
            "recent_10_avg_allowed": 5.3,
            "batting_average": ".231",
            "on_base_percentage": ".309",
            "ai_offense_score": 82,
            "ai_pitching_score": 86,
            "ai_recent_form": 72,
            "ai_roster_complete": 82
        }
    },
    "bullpen_analysis": {
        "home": {
            "recent_10_avg_runs_allowed": 3.2,
            "condition": "🔥 牛棚狀態佳",
            "advantage": "老虎優勢"
        },
        "away": {
            "recent_10_avg_runs_allowed": 5.3,
            "condition": "❌ 後援壓力大",
            "advantage": "處於劣勢"
        }
    },
    "left_right_split": {
        "home_vs_lefty": {
            "record": "7勝14敗",
            "assessment": "❌ 明顯弱項",
            "note": "這對 Valdez 有利"
        },
        "away_vs_lefty": {
            "record": "9勝12敗", 
            "assessment": "略優"
        }
    },
    "home_field_advantage": {
        "home_record": "老虎主場 16勝20敗",
        "away_record": "太空人客場 12勝26敗",
        "away_win_percentage": "31.6%",
        "impact": "巨大扣分",
        "home_advantage_points": "老虎 +7分"
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
print("✅ Tigers vs Astros 詳細 AI 分析已更新")