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
    if isinstance(obj, str):
        # 嘗試轉換數值字串 (e.g. "7", "0.598", "10.0")
        try:
            if '.' in obj or 'e' in obj.lower():
                return float(obj)
            return int(obj)
        except (ValueError, TypeError):
            return obj
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
        port=int(os.getenv('DB_PORT', 5432)),
        dbname=os.getenv('DB_NAME', 'predictx'),
        user=os.getenv('DB_USER', 'jero'),
        password=os.getenv('DB_PASSWORD', ''),
        cursor_factory=RealDictCursor
    )


@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy", "service": "PredictX Analysis API"}), 200


@app.route('/api/init_db', methods=['POST'])
def init_db():
    try:
        results = {}
        conn = get_db()
        conn.autocommit = True
        cur = conn.cursor()

        cur.execute("CREATE SCHEMA IF NOT EXISTS predictx")
        cur.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\"")
        results['schema_created'] = True

        schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'db', 'schema.sql')
        seed_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'db', 'seed_core.sql')

        with open(schema_path, 'r') as f:
            raw = f.read()
        clean = _clean_pgdump(raw)
        results['schema_errors'] = []
        for stmt in _split_pgdump_sql(clean):
            try:
                cur.execute(stmt)
            except Exception as e:
                results['schema_errors'].append(str(e)[:200])
        results['schema_executed'] = True

        results['seed_errors'] = []
        if os.path.exists(seed_path):
            with open(seed_path, 'r') as f:
                raw_seed = f.read()
            clean_seed = _clean_pgdump(raw_seed)
            for stmt in _split_pgdump_sql(clean_seed):
                try:
                    cur.execute(stmt)
                except Exception as e:
                    results['seed_errors'].append(str(e)[:200])
            results['seed_executed'] = True

        try:
            cur.execute("SELECT COUNT(*) as cnt FROM predictx.games")
            cnt = cur.fetchone()[0]
            results['game_count'] = cnt
        except Exception:
            results['game_count'] = 0

        cur.close()
        conn.close()

        return jsonify({"status": "success", "details": results}), 200
    except Exception as e:
        import traceback
        logger.error(f"init_db failed: {e}\n{traceback.format_exc()}")
        return jsonify({"error": str(e), "type": type(e).__name__}), 500


def _clean_pgdump(sql_text):
    lines = []
    for line in sql_text.split('\n'):
        stripped = line.strip()
        if not stripped:
            lines.append(line)
            continue
        if stripped.startswith('--'):
            continue
        upper = stripped.upper()
        if upper.startswith('SET '):
            continue
        if upper.startswith('SELECT PG_CATALOG.'):
            continue
        if 'OWNER TO' in upper:
            continue
        lines.append(line)
    return '\n'.join(lines)


def _split_pgdump_sql(sql_text):
    statements = []
    in_dollar = False
    current = []
    for line in sql_text.split('\n'):
        stripped = line.strip()
        if '$$' in stripped and not in_dollar:
            in_dollar = True
        current.append(line)
        if stripped.endswith(';') and not in_dollar:
            stmt = '\n'.join(current).strip()
            if stmt and stmt != ';':
                statements.append(stmt)
            current = []
        elif stripped == '$$;' and in_dollar:
            in_dollar = False
    if current:
        stmt = '\n'.join(current).strip()
        if stmt:
            statements.append(stmt)
    return statements


@app.route('/analytics/overall', methods=['GET'])
def get_overall_stats():
    try:
        data = _get_stats().get_overall_hit_rates()
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
                ga.analysis_data->>'confidence' AS ai_confidence,
                ga.analysis_data->>'home_win_probability' AS ai_home_prob,
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
    cur.execute("SELECT analysis_data FROM game_analysis WHERE game_id = %s::uuid", (game_id,))
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
