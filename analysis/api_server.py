from flask import Flask, jsonify, request
from flask_cors import CORS
import sys
import os
import logging
from decimal import Decimal
from datetime import date, datetime
import psycopg2
from psycopg2.extras import RealDictCursor
import json
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

        # 執行進階分析表格 migration
        advanced_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'db', 'migration_advanced.sql')
        results['advanced_errors'] = []
        if os.path.exists(advanced_path):
            with open(advanced_path, 'r') as f:
                raw_advanced = f.read()
            for stmt in _split_pgdump_sql(raw_advanced):
                try:
                    cur.execute(stmt)
                except Exception as e:
                    results['advanced_errors'].append(str(e)[:200])
            results['advanced_executed'] = True

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
        results = json.dumps([convert_decimals(dict(row)) for row in data], ensure_ascii=False)
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
        results = json.dumps([convert_decimals(dict(row)) for row in data], ensure_ascii=False)
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
        # days 參數：APP 預設 7/14/30 會帶，可調範圍避免一次性回傳太多歷史資料
        days = request.args.get('days', default=14, type=int)
        days = max(1, min(days, 60))  # 限制 1~60 天，避免誤傳超大值
        sql = """
            SELECT
                g.game_id,
                CASE
                    WHEN UPPER(%s) IN ('MLB', 'NBA') THEN g.match_date + 1
                    ELSE g.match_date
                END AS match_date,
                COALESCE(gs.status, g.status) AS status,
                g.home_team_score,
                g.away_team_score,
                COALESCE(th_a.alias_name, th.english_name) AS home_team,
                COALESCE(ta_a.alias_name, ta.english_name) AS away_team,
                (ga.analysis_data->>'confidence')::numeric AS ai_confidence,
                (ga.analysis_data->>'home_win_probability')::numeric AS ai_home_prob,
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
            AND g.match_date >= CURRENT_DATE - (%s || ' days')::interval
            ORDER BY g.match_date DESC, g.game_id
        """
        cur.execute(sql, (league, league, league, str(days)))
        games = cur.fetchall()
        cur.close()
        conn.close()
        results = [convert_decimals(dict(row)) for row in games]
        return jsonify(results)
    except Exception as e:
        import traceback
        logger.error(f"Error in /api/games: {e}\n{traceback.format_exc()}")
        return jsonify({"error": str(e), "type": type(e).__name__}), 500


@app.route('/api/run_analysis', methods=['POST'])
def run_analysis():
    """執行 AI 分析 + 結算（同步執行）"""
    try:
        from run_analysis import get_pending_games, save_analysis
        from analysis_engine import AnalysisEngine
        from settlement_engine import SettlementEngine
        from datetime import datetime, timedelta

        conn = get_db()
        results = {}
        results['env'] = {
            'model': os.getenv('PREDICTX_MODEL', 'not set'),
            'nvidia_key': bool(os.getenv('NVIDIA_API_KEY'))
        }

        taipei_tz = datetime.now().astimezone().tzinfo
        today = datetime.now(taipei_tz).strftime('%Y-%m-%d')
        tomorrow = (datetime.now(taipei_tz) + timedelta(days=1)).strftime('%Y-%m-%d')

        pending = get_pending_games(conn, [today, tomorrow])
        results['pending'] = len(pending)

        if pending:
            engine = AnalysisEngine(conn=conn)
            success = 0
            for idx, game in enumerate(pending[:5]):
                game_id = game['game_id']
                try:
                    result = engine.analyze_game(game_id)
                    if result and save_analysis(conn, game_id, result):
                        success += 1
                except Exception as e:
                    results[f'e{idx}'] = str(e)[:100]
            engine.close()
            results['analyzed'] = success
        else:
            results['analyzed'] = 0

        try:
            settler = SettlementEngine()
            results['settled'] = settler.settle_games()
        except Exception as e:
            results['settle_error'] = str(e)[:200]

        conn.close()
        return jsonify({"status": "success", "details": results}), 200
    except Exception as e:
        import traceback
        logger.error(f"run_analysis: {e}\n{traceback.format_exc()}")
        return jsonify({"error": str(e), "type": type(e).__name__}), 500


@app.route('/api/insert_games', methods=['POST'])
def insert_games():
    """接受外部傳入的賽程資料並寫入資料庫"""
    try:
        data = request.get_json()
        if not data or 'games' not in data:
            return jsonify({"error": "Missing games array"}), 400

        conn = get_db()
        conn.autocommit = True
        cur = conn.cursor()
        inserted = 0
        skipped = 0
        updated = 0

        for g in data['games']:
            match_date = g.get('match_date', '2026-06-15')
            home_name = g.get('home_team')
            away_name = g.get('away_team')
            season = g.get('season', 2026)
            status = g.get('status', 'SCHEDULED')
            home_score = g.get('home_team_score')
            away_score = g.get('away_team_score')

            if not home_name or not away_name:
                skipped += 1
                continue

            cur.execute("SELECT team_id FROM predictx.teams WHERE english_name = %s", (home_name,))
            home_row = cur.fetchone()
            cur.execute("SELECT team_id FROM predictx.teams WHERE english_name = %s", (away_name,))
            away_row = cur.fetchone()

            if home_row and away_row:
                home_id = home_row['team_id']
                away_id = away_row['team_id']
                cur.execute(
                    "SELECT game_id FROM predictx.games WHERE match_date = %s AND home_team_id = %s AND away_team_id = %s",
                    (match_date, home_id, away_id)
                )
                existing = cur.fetchone()
                if not existing:
                    cur.execute(
                        """INSERT INTO predictx.games (season, match_date, status, home_team_id, away_team_id, home_team_score, away_team_score)
                           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                        (season, match_date, status, home_id, away_id, home_score, away_score)
                    )
                    inserted += 1
                else:
                    # 更新現有賽事的 status 和 score
                    update_fields = []
                    update_vals = []
                    if status:
                        update_fields.append("status = %s")
                        update_vals.append(status)
                    if home_score is not None:
                        update_fields.append("home_team_score = %s")
                        update_vals.append(home_score)
                    if away_score is not None:
                        update_fields.append("away_team_score = %s")
                        update_vals.append(away_score)
                    if update_fields:
                        update_vals.append(existing['game_id'])
                        cur.execute(
                            f"UPDATE predictx.games SET {', '.join(update_fields)} WHERE game_id = %s",
                            tuple(update_vals)
                        )
                    updated += 1
            else:
                skipped += 1

        cur.close()
        conn.close()
        return jsonify({"status": "success", "inserted": inserted, "updated": updated, "skipped": skipped}), 200
    except Exception as e:
        import traceback
        logger.error(f"insert_games failed: {e}\n{traceback.format_exc()}")
        return jsonify({"error": str(e), "type": type(e).__name__}), 500


@app.route('/api/update_score', methods=['POST'])
def update_score():
    """手動更新指定賽事的比分與狀態，供資料維護用"""
    try:
        data = request.get_json(force=True)
        game_id = data.get('game_id')
        home_score = data.get('home_score')
        away_score = data.get('away_score')
        status = data.get('status', 'FINAL')

        if not game_id:
            return jsonify({"error": "Missing game_id"}), 400

        conn = get_db()
        conn.autocommit = True
        cur = conn.cursor()

        update_fields = []
        update_vals = []
        if home_score is not None:
            update_fields.append("home_team_score = %s")
            update_vals.append(home_score)
        if away_score is not None:
            update_fields.append("away_team_score = %s")
            update_vals.append(away_score)
        if status:
            update_fields.append("status = %s")
            update_vals.append(status)
        update_vals.append(game_id)

        if update_fields:
            cur.execute(
                f"UPDATE predictx.games SET {', '.join(update_fields)} WHERE game_id = %s::uuid",
                tuple(update_vals)
            )
            logger.info(f"update_score: game_id={game_id}, rows={cur.rowcount}")
        else:
            return jsonify({"error": "No fields to update"}), 400

        cur.close()
        conn.close()
        return jsonify({"status": "success", "updated": cur.rowcount}), 200
    except Exception as e:
        import traceback
        logger.error(f"update_score failed: {e}\n{traceback.format_exc()}")
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


@app.route('/api/update_analysis', methods=['POST'])
def update_analysis():
    """手動寫入 AI 分析資料到指定賽事"""
    try:
        data = request.get_json(force=True)
        game_id = data.get('game_id')
        analysis_data = data.get('analysis_data')
        if not game_id or not analysis_data:
            return jsonify({"error": "Missing game_id or analysis_data"}), 400
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO predictx.game_analysis (game_id, analysis_data, updated_at)
               VALUES (%s::uuid, %s::jsonb, CURRENT_TIMESTAMP)
               ON CONFLICT (game_id)
               DO UPDATE SET analysis_data = EXCLUDED.analysis_data, updated_at = CURRENT_TIMESTAMP""",
            (game_id, json.dumps(analysis_data, ensure_ascii=False))
        )
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"status": "success", "game_id": game_id}), 200
    except Exception as e:
        import traceback
        logger.error(f"update_analysis: {e}\n{traceback.format_exc()}")
        return jsonify({"error": str(e), "type": type(e).__name__}), 500


if __name__ == "__main__":
    port = int(os.getenv('PORT', 8081))
    app.run(host="0.0.0.0", port=port, debug=False)


# 已於 2026-06-17 移除 FIFA 端點 — 不再提供 FIFA 相關 API 行為

