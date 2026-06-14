from flask import Flask, jsonify, request
from flask_cors import CORS
import sys
import os
import logging
from decimal import Decimal
from datetime import date, datetime
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PredictX-API")

app = Flask(__name__)
CORS(app)

# 延遲載入分析引擎
_stats_engine = None
_settler_engine = None

def _get_stats():
    global _stats_engine
    if _stats_engine is None:
        from stats_engine import StatsEngine
        _stats_engine = StatsEngine()
    return _stats_engine

def _get_settler():
    global _settler_engine
    if _settler_engine is None:
        from settlement_engine import SettlementEngine
        _settler_engine = SettlementEngine()
    return _settler_engine

def convert_decimals(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: convert_decimals(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [convert_decimals(v) for v in obj]
    return obj

def get_db():
    database_url = os.getenv('DATABASE_URL')
    if database_url:
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        return psycopg2.connect(database_url, cursor_factory=RealDictCursor)
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        port=os.getenv('DB_PORT', 5432),
        dbname=os.getenv('DB_NAME', 'sports_db'),
        user=os.getenv('DB_USER', 'jero'),
        password=os.getenv('DB_PASSWORD', ''),
        cursor_factory=RealDictCursor
    )


@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy", "service": "PredictX Analysis API"}), 200


@app.route('/analytics/overall', methods=['GET'])
def get_overall_stats():
    try:
        data = _get_stats().get_overall_hit_rates()
        # 用 json.dumps + default=str fallback 處理所有非原生型別
        import json
        results = json.dumps([dict(row) for row in data], default=str, ensure_ascii=False)
        return app.response_class(results, mimetype='application/json'), 200
    except Exception as e:
        import traceback
        logger.error(f"Error fetching overall stats: {e}\n{traceback.format_exc()}")
        return jsonify({"error": str(e), "type": type(e).__name__}), 500


@app.route('/analytics/trend', methods=['GET'])
def get_trend():
    league = request.args.get('league')
    limit = request.args.get('limit', default=50, type=int)
    try:
        data = _get_stats().get_hit_rate_trend(league=league, limit=limit)
        import json
        results = json.dumps([dict(row) for row in data], default=str, ensure_ascii=False)
        return app.response_class(results, mimetype='application/json'), 200
    except Exception as e:
        import traceback
        logger.error(f"Error updating trend: {e}\n{traceback.format_exc()}")
        return jsonify({"error": str(e), "type": type(e).__name__}), 500


@app.route('/analytics/settle', methods=['POST'])
def trigger_settlement():
    try:
        count = _get_settler().settle_games()
        return jsonify({"status": "success", "settled_count": count}), 200
    except Exception as e:
        logger.error(f"Settlement failed: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/games', methods=['GET'])
def api_games():
    league = request.args.get('league')
    if not league:
        return jsonify({"error": "Missing league parameter"}), 400
    try:
        conn = get_db()
        cur = conn.cursor()
        sql = """
            SELECT DISTINCT ON (g.game_id)
                g.game_id,
                g.match_date,
                COALESCE(gs.status, g.status) as status,
                g.home_team_score,
                g.away_team_score,
                COALESCE(th_a.alias_name, th.english_name) AS home_team,
                COALESCE(ta_a.alias_name, ta.english_name) AS away_team,
                ga.analysis_data->'confidence' AS ai_confidence,
                ga.analysis_data->'home_win_probability' AS ai_home_prob,
                ga.analysis_data->>'predicted_score' AS ai_predicted_score,
                (ga.analysis_data->'actual_result'->>'is_hit')::boolean AS ai_is_hit,
                ga.analysis_data->'actual_result'->>'actual_score' AS ai_actual_score
            FROM predictx.games g
            JOIN predictx.teams th ON g.home_team_id = th.team_id
            LEFT JOIN predictx.team_aliases th_a ON th.team_id = th_a.team_id
            JOIN predictx.teams ta ON g.away_team_id = ta.team_id
            LEFT JOIN predictx.team_aliases ta_a ON ta.team_id = ta_a.team_id
            LEFT JOIN predictx.game_status gs ON g.game_id = gs.game_id
            LEFT JOIN predictx.game_analysis ga ON g.game_id = ga.game_id
            WHERE UPPER(th.league) = UPPER(%s) AND UPPER(ta.league) = UPPER(%s)
            AND g.match_date >= CURRENT_DATE - INTERVAL '30 days'
            ORDER BY g.game_id, g.match_date DESC
        """
        cur.execute(sql, (league, league))
        games = cur.fetchall()
        cur.close()
        conn.close()
        # 用 convert_decimals 處理所有可能的非 JSON 原生型別
        results = [convert_decimals(dict(row)) for row in games]
        return jsonify(results)
    except Exception as e:
        import traceback
        logger.error(f"Error in /api/games: {e}\n{traceback.format_exc()}")
        return jsonify({"error": str(e), "type": type(e).__name__}), 500


@app.route('/api/game_analysis/<game_id>', methods=['GET'])
def get_game_analysis(game_id):
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT analysis_data FROM predictx.game_analysis WHERE game_id = %s::uuid", (game_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row:
        raw = row['analysis_data']
        result = {
            "prediction": {
                "home_win_probability": float(raw.get("home_win_probability", 0.0)),
                "away_win_probability": float(raw.get("away_win_probability", 0.0)),
                "confidence": float(raw.get("confidence", 0.0)),
                "predicted_score": str(raw.get("predicted_score", ""))
            },
            "source_quality": raw.get("source_quality", {"score": 0.0, "sources": []}),
            "radar_chart": {
                "categories": raw.get("radar_chart", {}).get("categories", []),
                "home_team": raw.get("radar_chart", {}).get("home_team", []),
                "away_team": raw.get("radar_chart", {}).get("away_team", [])
            },
            "analysis": {
                "summary": str(raw.get("summary", "")),
                "key_factors": raw.get("key_factors", [])
            }
        }
        return jsonify(result)
    return jsonify({"error": "Analysis not found"}), 404


if __name__ == "__main__":
    port = int(os.getenv('PORT', 8081))
    app.run(host="0.0.0.0", port=port, debug=False)
