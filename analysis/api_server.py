from flask import Flask, jsonify, request, g
from flask_cors import CORS
import sys
import os
import logging
from decimal import Decimal
from datetime import date, datetime
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
import json
from dotenv import load_dotenv
import urllib.parse as urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PredictX-API")

# Sentry 錯誤監控（production）
# 如果未設 SENTRY_DSN，自動跳過（不影響運作）
SENTRY_DSN = os.getenv("SENTRY_DSN")
if SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.flask import FlaskIntegration
        sentry_sdk.init(
            dsn=SENTRY_DSN,
            integrations=[FlaskIntegration()],
            traces_sample_rate=0.1,  # 10% performance traces
            environment=os.getenv("RAILWAY_ENVIRONMENT", "production"),
            release="predictx-api@1.0.0",
        )
        logger.info("Sentry 初始化成功")
    except Exception as e:
        logger.warning(f"Sentry 初始化失敗（不影響服務）: {e}")
else:
    logger.info("未設定 SENTRY_DSN，跳過 Sentry 初始化")

# === 資料庫連線池初始化（模組載入時只建立一次） ===
_database_url = os.getenv('DATABASE_URL')
if not _database_url:
    raise RuntimeError('DATABASE_URL 未設定，無法啟動應用')

_parsed = urlparse.urlparse(_database_url)

_db_minconn = int(os.getenv('DB_POOL_MIN', '2'))
_db_maxconn = int(os.getenv('DB_POOL_MAX', '20'))
logger.info(f"DB connection pool: minconn={_db_minconn}, maxconn={_db_maxconn}")

DB_POOL = pool.ThreadedConnectionPool(
    minconn=_db_minconn,
    maxconn=_db_maxconn,  # 可透過 Railway 環境變數 DB_POOL_MAX 調整
    host=_parsed.hostname,
    port=_parsed.port,
    dbname=_parsed.path.lstrip('/'),
    user=_parsed.username,
    password=_parsed.password,
    cursor_factory=RealDictCursor,
)

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
    """從連線池取得一條連線，存入 g 供請求期間複用"""
    if 'db' not in g:
        g.db = DB_POOL.getconn()
    return g.db


@app.teardown_appcontext
def close_db(exc):
    """請求結束時將連線歸還連線池（而非關閉）"""
    conn = g.pop('db', None)
    if conn is not None:
        DB_POOL.putconn(conn)


@app.route('/health', methods=['GET'])
def health():
    """完整健康檢查：DB 連線 + 必要環境變數"""
    checks = {
        "service": "PredictX Analysis API",
        "timestamp": datetime.now().isoformat(),
        "checks": {}
    }
    overall_healthy = True

    # 1. DB 連線檢查
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
        cur.close()
        # 注意：這裡不呼叫 conn.close()，因為連線要歸還池中
        checks["checks"]["database"] = "ok"
    except Exception as e:
        checks["checks"]["database"] = f"error: {type(e).__name__}"
        overall_healthy = False

    # 2. 必要環境變數檢查
    required_env = ["DATABASE_URL", "NVIDIA_API_KEY", "PREDICTX_MODEL"]
    missing = [k for k in required_env if not os.getenv(k)]
    if missing:
        checks["checks"]["env_vars"] = f"missing: {missing}"
        overall_healthy = False
    else:
        checks["checks"]["env_vars"] = "ok"

    # 3. TheSportsDB key（CPBL 用，可選）
    checks["checks"]["thesportsdb_key"] = "configured" if os.getenv("THESPORTSDB_API_KEY", "123") else "missing"

    checks["status"] = "healthy" if overall_healthy else "unhealthy"
    return jsonify(checks), 200 if overall_healthy else 503


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
        seed_path = os.path.join(os.path.dirname(os.path.abspath(__file__file__)), 'db', 'seed_core.sql')

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
        # 注意：這裡不呼叫 conn.close()，連線會在 teardown 時歸還池中
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


# 🆕 [2026-06-24] Rolling Accuracy API — 提供給 prompt 動態注入用
# 路徑：GET /analytics/accuracy_rolling?league=MLB&window=30
# 回傳：{ league, window, total, hits, hit_rate, oldest, newest }
@app.route('/analytics/accuracy_rolling', methods=['GET'])
def get_accuracy_rolling():
    """取得最近 N 場已結算 AI 預測的命中率（給 prompt 動態注入用）"""
    league = request.args.get('league', type=str)
    window = request.args.get('window', default=30, type=int)
    prompt_version = request.args.get('prompt_version', type=str)  # 可選：只計算特定 prompt 版本
    
    if window < 1 or window > 365:
        return jsonify({"error": "window must be between 1 and 365"}), 400
    
    try:
        conn = get_db()
        cur = conn.cursor()
        
        # 用 ROW_NUMBER 取最近 N 場已結算
        if prompt_version:
            cur.execute(
                """
                WITH ranked AS (
                    SELECT league, is_hit, prediction_time,
                           ROW_NUMBER() OVER (ORDER BY prediction_time DESC) AS rn
                    FROM predictx.ai_prediction_history
                    WHERE league = %s
                      AND is_hit IS NOT NULL
                      AND prompt_version = %s
                )
                SELECT 
                  COUNT(*) AS total,
                  SUM(CASE WHEN is_hit THEN 1 ELSE 0 END) AS hits,
                  ROUND(100.0 * SUM(CASE WHEN is_hit THEN 1 ELSE 0 END)::numeric 
                        / NULLIF(COUNT(*), 0), 1) AS hit_rate,
                  MIN(prediction_time)::date AS oldest,
                  MAX(prediction_time)::date AS newest
                FROM ranked
                WHERE rn <= %s
                """,
                (league.upper() if league else None, prompt_version, window)
            )
        else:
            cur.execute(
                """
                WITH ranked AS (
                    SELECT league, is_hit, prediction_time,
                           ROW_NUMBER() OVER (ORDER BY prediction_time DESC) AS rn
                    FROM predictx.ai_prediction_history
                    WHERE league = %s
                      AND is_hit IS NOT NULL
                )
                SELECT 
                  COUNT(*) AS total,
                  SUM(CASE WHEN is_hit THEN 1 ELSE 0 END) AS hits,
                  ROUND(100.0 * SUM(CASE WHEN is_hit THEN 1 ELSE 0 END)::numeric 
                        / NULLIF(COUNT(*), 0), 1) AS hit_rate,
                  MIN(prediction_time)::date AS oldest,
                  MAX(prediction_time)::date AS newest
                FROM ranked
                WHERE rn <= %s
                """,
                (league.upper() if league else None, window)
            )
        
        row = cur.fetchone()
        cur.close()
        # 不關 conn（會歸還連線池）
        
        if row is None:
            row = {'total': 0, 'hits': 0, 'hit_rate': None, 'oldest': None, 'newest': None}
        else:
            row = dict(row)  # 確保是 dict（RealDictCursor 已 dict，但保險轉換）
        
        total = row.get('total') or 0
        hits = row.get('hits') or 0
        hit_rate_raw = row.get('hit_rate')
        hit_rate = float(hit_rate_raw) if hit_rate_raw is not None else 0.0
        
        oldest = row.get('oldest')
        newest = row.get('newest')
        
        return jsonify({
            "league": league.upper() if league else None,
            "window": window,
            "prompt_version": prompt_version,
            "total": total,
            "hits": hits,
            "hit_rate": hit_rate,
            "oldest": oldest.isoformat() if oldest else None,
            "newest": newest.isoformat() if newest else None,
            "is_sufficient": total >= 10  # 樣本 >= 10 才算有意義
        }), 200
    except Exception as e:
        import traceback
        logger.error(f"accuracy_rolling error: {e}\n{traceback.format_exc()}")
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
                COALESCE(g.status, gs.status) AS status,
                g.home_team_score,
                g.away_team_score,
                COALESCE(th.english_name, th.chinese_name) AS home_team,
                COALESCE(ta.english_name, ta.chinese_name) AS away_team,
                (ga.analysis_data->>'confidence')::numeric AS ai_confidence,
                (ga.analysis_data->>'home_win_probability')::numeric AS ai_home_prob,
                ga.analysis_data->>'predicted_score' AS ai_predicted_score,
                (ga.analysis_data->'actual_result'->>'is_hit')::boolean AS ai_is_hit,
                ga.analysis_data->'actual_result'->>'actual_score' AS ai_actual_score
            FROM predictx.games g
            JOIN predictx.teams th ON g.home_team_id = th.team_id
            JOIN predictx.teams ta ON g.away_team_id = ta.team_id
            LEFT JOIN predictx.game_status gs ON g.game_id = gs.game_id
            LEFT JOIN predictx.game_analysis ga ON g.game_id = ga.game_id
            WHERE UPPER(th.league) = UPPER(%s) AND UPPER(ta.league) = UPPER(%s)
            AND g.match_date >= CURRENT_DATE - (%s || ' days')::interval
            -- 🆕 移除 team_aliases JOIN（之前導致同 game 重複 4 次，例如 NBA Nets 出現 4 個別名）
            -- 直接使用 teams.english_name 作為顯示用名稱
            ORDER BY g.match_date DESC, g.game_id
        """
        cur.execute(sql, (league, league, league, str(days)))
        games = cur.fetchall()
        cur.close()
        # 不呼叫 conn.close()，連線會在 teardown 時歸還池中
        results = [convert_decimals(dict(row)) for row in games]
        return jsonify(results)
    except Exception as e:
        import traceback
        logger.error(f"Error in /api/games: {e}\n{traceback.format_exc()}")
        return jsonify({"error": str(e), "type": type(e).__name__}), 500


@app.route('/api/run_analysis', methods=['POST'])
def run_analysis():
    """執行 AI 分析 + 結算（同步執行）

    可選 body 參數：
      - game_id: 指定單場強制重跑（會覆寫現有 analysis_data）
      - max_count: 限制批次數（預設 5）
    """
    try:
        from run_analysis import get_pending_games, save_analysis
        from analysis_engine import AnalysisEngine
        from settlement_engine import SettlementEngine
        from datetime import datetime, timedelta

        body = request.get_json(silent=True) or {}
        force_game_id = body.get('game_id')
        max_count = int(body.get('max_count', 5))

        conn = get_db()
        results = {}
        results['env'] = {
            'model': os.getenv('PREDICTX_MODEL', 'not set'),
            'nvidia_key': bool(os.getenv('NVIDIA_API_KEY'))
        }

        # 強制重跑單場模式
        if force_game_id:
            results['mode'] = 'force'
            engine = AnalysisEngine(conn=conn)
            try:
                result = engine.analyze_game(force_game_id)
                if result and save_analysis(conn, force_game_id, result):
                    results['analyzed'] = 1
                    results['game_id'] = force_game_id
                else:
                    results['analyzed'] = 0
                    results['error'] = 'no result from engine'
            except Exception as e:
                import traceback
                results['error'] = str(e)[:500]
                results['trace'] = traceback.format_exc()[:500]
            # 不呼叫 conn.close()，連線會在 teardown 時歸還池中
            return jsonify(results), 200

        # 批次模式：跑今日 + 明日 pending
        results['mode'] = 'batch'
        taipei_tz = datetime.now().astimezone().tzinfo
        today = datetime.now(taipei_tz).strftime('%Y-%m-%d')
        tomorrow = (datetime.now(taipei_tz) + timedelta(days=1)).strftime('%Y-%m-%d')

        pending = get_pending_games(conn, [today, tomorrow])
        results['pending'] = len(pending)

        if pending:
            engine = AnalysisEngine(conn=conn)
            success = 0
            for idx, game in enumerate(pending[:max_count]):
                game_id = game['game_id']
                try:
                    result = engine.analyze_game(game_id)
                    if result and save_analysis(conn, game_id, result):
                        success += 1
                except Exception as e:
                    import traceback
                    results[f'e{idx}'] = str(e)[:100]
                    results[f'e{idx}_trace'] = traceback.format_exc()[:500]
            engine.close()
            results['analyzed'] = success
        else:
            results['analyzed'] = 0

        try:
            settler = SettlementEngine()
            results['settled'] = settler.settle_games()
        except Exception as e:
            results['settle_error'] = str(e)[:200]

        # 不呼叫 conn.close()，連線會在 teardown 時歸還池中
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

            # 🆕 三階段 team 解析：english_name → team_aliases → ILIKE 部分匹配
            def find_team_id(name):
                cur.execute("SELECT team_id FROM predictx.teams WHERE english_name = %s", (name,))
                row = cur.fetchone()
                if row:
                    return row['team_id']
                cur.execute("""
                    SELECT t.team_id
                    FROM predictx.team_aliases ta
                    JOIN predictx.teams t ON ta.team_id = t.team_id
                    WHERE ta.alias_name = %s
                """, (name,))
                row = cur.fetchone()
                if row:
                    logger.info(f"[insert_games] team_id resolved via alias: {name} → {row['team_id']}")
                    return row['team_id']
                cur.execute("SELECT team_id FROM predictx.teams WHERE english_name ILIKE %s LIMIT 1", (f'%{name}%',))
                row = cur.fetchone()
                if row:
                    logger.info(f"[insert_games] team_id resolved via ILIKE: {name} → {row['team_id']}")
                    return row['team_id']
                return None

            home_id = find_team_id(home_name)
            away_id = find_team_id(away_name)

            if home_id is not None and away_id is not None:
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
        # 不呼叫 conn.close()，連線會在 teardown 時歸還池中
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
        # 不呼叫 conn.close()，連線會在 teardown 時歸還池中
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
    # 不呼叫 conn.close()，連線會在 teardown 時歸還池中
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
        # 不呼叫 conn.close()，連線會在 teardown 時歸還池中
        return jsonify({"status": "success", "game_id": game_id}), 200
    except Exception as e:
        import traceback
        logger.error(f"update_analysis: {e}\n{traceback.format_exc()}")
        return jsonify({"error": str(e), "type": type(e).__name__}), 500


# ========================================================
# 🆕 球員資料端點（TheSportsDB）
# ========================================================

@app.route('/api/players/roster', methods=['GET'])
def get_team_roster():
    """取得球隊完整球員名單（TheSportsDB）

    Query: ?team_id=135260 (MLB 洋基) 或 ?team=New+York+Yankees
    """
    try:
        from thesportsdb_enricher import get_enricher
        team_id = request.args.get('team_id')
        if not team_id:
            return jsonify({"error": "Missing team_id parameter"}), 400

        enricher = get_enricher()
        players = enricher.get_team_roster(team_id)

        # iOS UI 友善格式
        normalized = []
        for p in players:
            normalized.append({
                "id": p.get("idPlayer"),
                "name": p.get("strPlayer", ""),
                "position": p.get("strPosition", ""),
                "nationality": p.get("strNationality", ""),
                "birth_date": p.get("dateBorn"),
                "height": p.get("strHeight"),
                "weight": p.get("strWeight"),
                "photo_url": p.get("strThumb"),
                "cutout_url": p.get("strCutout"),  # 去背頭像
            })

        return jsonify({
            "team_id": team_id,
            "count": len(normalized),
            "players": normalized,
        }), 200
    except Exception as e:
        logger.error(f"get_team_roster error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/players/<player_id>', methods=['GET'])
def get_player_detail(player_id):
    """取得單一球員完整資料（基本資料 + 合約 + 榮譽）

    Path: /api/players/34164069 (Aaron Judge)
    """
    try:
        from thesportsdb_enricher import get_enricher
        enricher = get_enricher()

        info = enricher.get_player_info(player_id)
        if not info:
            return jsonify({"error": "Player not found"}), 404

        contracts = enricher.get_player_contracts(player_id)
        honours = enricher.get_player_honours(player_id)

        return jsonify({
            "player": {
                "id": info.get("idPlayer"),
                "name": info.get("strPlayer", ""),
                "team": info.get("strTeam", ""),
                "team_id": info.get("idTeam"),
                "nationality": info.get("strNationality", ""),
                "position": info.get("strPosition", ""),
                "birth_date": info.get("dateBorn"),
                "birth_location": info.get("strBirthLocation"),
                "height": info.get("strHeight"),
                "weight": info.get("strWeight"),
                "jersey_number": info.get("strNumber"),
                "photo_url": info.get("strThumb"),
                "cutout_url": info.get("strCutout"),
                "description": info.get("strDescriptionEN"),
            },
            "contracts": contracts,
            "honours": honours,
        }), 200
    except Exception as e:
        logger.error(f"get_player_detail error: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.getenv('PORT', 8081))
    app.run(host="0.0.0.0", port=port, debug=False)


# 已於 2026-06-17 移除 FIFA 端點 — 不再提供 FIFA 相關 API 行為