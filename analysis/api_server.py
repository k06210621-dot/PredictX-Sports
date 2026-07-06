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


# 🆕 [2026-06-27] 推播通知相關 endpoint
@app.route('/api/register_device', methods=['POST'])
def register_device():
    """註冊或更新 APNs device token（包含 tier 與 push_enabled 偏好）"""
    try:
        data = request.get_json()
        token = data.get('token')
        tier = data.get('tier', 'free')
        push_enabled = data.get('push_enabled', False)

        if not token or not isinstance(token, str):
            return jsonify({"error": "Missing or invalid token"}), 400

        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO predictx.device_tokens (device_token, tier, push_enabled, updated_at)
            VALUES (%s, %s, %s, NOW())
            ON CONFLICT (device_token) DO UPDATE
            SET tier = EXCLUDED.tier,
                push_enabled = EXCLUDED.push_enabled,
                updated_at = NOW()
        """, (token, tier, bool(push_enabled)))
        conn.commit()
        cur.close()
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logger.error(f"register_device error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/update_push_preference', methods=['POST'])
def update_push_preference():
    """更新推播偏好設定（不變動 token）"""
    try:
        data = request.get_json()
        token = data.get('token')
        push_enabled = data.get('push_enabled', False)

        if not token or not isinstance(token, str):
            return jsonify({"error": "Missing or invalid token"}), 400

        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            UPDATE predictx.device_tokens
            SET push_enabled = %s, updated_at = NOW()
            WHERE device_token = %s
        """, (bool(push_enabled), token))
        conn.commit()
        cur.close()
        return jsonify({"status": "ok", "rows_updated": cur.rowcount}), 200
    except Exception as e:
        logger.error(f"update_push_preference error: {e}")
        return jsonify({"error": str(e)}), 500


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
                    WHEN UPPER(%s) IN ('MLB', 'NBA', 'WNBA') THEN g.match_date + 1
                    ELSE g.match_date
                END AS match_date,
                COALESCE(g.status, gs.status) AS status,
                g.home_team_score,
                g.away_team_score,
                COALESCE(th.english_name, th.chinese_name) AS home_team,
                COALESCE(ta.english_name, ta.chinese_name) AS away_team,
                g.home_pitcher_name,
                g.away_pitcher_name,
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
            # 🆕 投手欄位（MLB ingester 從 statsapi.mlb.com hydrate=probablePitcher 抓）
            # base.py 傳入的 home_pitcher 是 dict {"name": ..., "id": ...}，要取 name 欄位
            home_pitcher_raw = g.get('home_pitcher')
            away_pitcher_raw = g.get('away_pitcher')
            home_pitcher_name = (
                home_pitcher_raw.get('name') if isinstance(home_pitcher_raw, dict)
                else home_pitcher_raw  # 若已是 string 直接用
            ) if home_pitcher_raw else None
            away_pitcher_name = (
                away_pitcher_raw.get('name') if isinstance(away_pitcher_raw, dict)
                else away_pitcher_raw
            ) if away_pitcher_raw else None
            # 過濾 TBD/空字串
            if home_pitcher_name in ('', 'TBD', 'tbd'):
                home_pitcher_name = None
            if away_pitcher_name in ('', 'TBD', 'tbd'):
                away_pitcher_name = None

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
                        """INSERT INTO predictx.games (season, match_date, status, home_team_id, away_team_id, home_team_score, away_team_score, home_pitcher_name, away_pitcher_name, pitcher_updated_at)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, CASE WHEN %s IS NOT NULL OR %s IS NOT NULL THEN CURRENT_TIMESTAMP ELSE NULL END)""",
                        (season, match_date, status, home_id, away_id, home_score, away_score, home_pitcher_name, away_pitcher_name, home_pitcher_name, away_pitcher_name)
                    )
                    inserted += 1
                else:
                    # 更新現有賽事的 status / score / pitcher
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
                    # 🆕 投手欄位：只在有值時更新（避免 MLB 開打前 TBD 蓋掉已設定的投手）
                    # 投手有變化時同步更新 pitcher_updated_at
                    if home_pitcher_name is not None:
                        update_fields.append("home_pitcher_name = %s")
                        update_vals.append(home_pitcher_name)
                        update_fields.append("pitcher_updated_at = CURRENT_TIMESTAMP")
                    if away_pitcher_name is not None:
                        update_fields.append("away_pitcher_name = %s")
                        update_vals.append(away_pitcher_name)
                        # 只在 home 沒更新時設一次（避免重複）
                        if not any("pitcher_updated_at" in f for f in update_fields[:-1]):
                            update_fields.append("pitcher_updated_at = CURRENT_TIMESTAMP")
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


@app.route('/api/admin/import_npb_players', methods=['POST'])
def import_npb_players():
    """一次性端點：匯入 npb_players.json 到 predictx.players"""
    body = request.get_json(silent=True) or {}
    if body.get('secret') != os.getenv('ADMIN_SECRET', 'predictx-admin-2026'):
        return jsonify({"error": "unauthorized"}), 403
    try:
        import json as _json
        import uuid as _uuid
        import os as _os

        # team_code → DB team_id
        TEAM_CODE_TO_DB = {
            'G': 'Yomiuri Giants', 'T': 'Hanshin Tigers', 'D': 'Chunichi Dragons',
            'YB': 'Yokohama DeNA BayStars', 'C': 'Hiroshima Toyo Carp', 'S': 'Tokyo Yakult Swallows',
            'H': 'Fukuoka SoftBank Hawks', 'L': 'Saitama Seibu Lions', 'M': 'Chiba Lotte Marines',
            'E': 'Tohoku Rakuten Golden Eagles', 'B': 'ORIX Buffaloes', 'F': 'Hokkaido Nippon-Ham Fighters',
        }

        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # 取得 NPB team UUIDs
        cur.execute("""
            SELECT english_name, team_id FROM predictx.teams
            WHERE league = 'NPB' AND english_name NOT LIKE '%Deprecated%'
        """)
        rows = cur.fetchall()
        # RealDictCursor 用 column name 取值（backward-compat with tuple fallback）
        team_name_to_id = {}
        for row in rows:
            try:
                name = row['english_name'] if isinstance(row, dict) else row[0]
                tid = row['team_id'] if isinstance(row, dict) else row[1]
            except (KeyError, IndexError, TypeError):
                # fallback: try positional
                name = row[0]
                tid = row[1]
            team_name_to_id[name] = tid

        # 檢查是否已匯入
        cur.execute("""
            SELECT COUNT(*) FROM predictx.players p
            JOIN predictx.player_teams pt ON p.player_id = pt.player_id
            JOIN predictx.teams t ON pt.team_id = t.team_id
            WHERE t.league = 'NPB' AND pt.is_active = true
        """)
        existing_row = cur.fetchone()
        # RealDictCursor: 用 column name 取值；tuple cursor: 用 positional index
        existing = 0
        if existing_row:
            if isinstance(existing_row, dict):
                existing = int(list(existing_row.values())[0])  # 任取 first value
            else:
                existing = existing_row[0]
        if existing > 0:
            cur.close()
            return jsonify({"status": "skipped", "reason": f"Already {existing} NPB players in DB"}), 200

        # 讀取 npb_players.json
        script_dir = _os.path.dirname(_os.path.abspath(__file__))
        json_path = _os.path.join(script_dir, 'npb_players.json')
        with open(json_path) as f:
            players = _json.load(f)

        inserted = 0
        skipped = 0
        for p in players:
            team_code = p.get('team_code')
            if not team_code:
                skipped += 1
                continue
            team_name = TEAM_CODE_TO_DB.get(team_code)
            if not team_name:
                skipped += 1
                continue
            team_id = team_name_to_id.get(team_name)
            if not team_id:
                skipped += 1
                continue

            name_en = p.get('name_en', 'Unknown')
            kind = p.get('kind', 'batter')
            position = 'P' if kind == 'pitcher' else 'IF/OF'
            player_id = str(_uuid.uuid4())

            try:
                cur.execute("""
                    INSERT INTO predictx.players (player_id, player_name, position)
                    VALUES (%s, %s, %s)
                """, (player_id, name_en, position))
                cur.execute("""
                    INSERT INTO predictx.player_teams (id, player_id, team_id, is_active)
                    VALUES (%s, %s, %s, true)
                """, (str(_uuid.uuid4()), player_id, team_id))
                inserted += 1
            except Exception:
                conn.rollback()
                skipped += 1

        conn.commit()
        cur.close()
        return jsonify({"status": "ok", "inserted": inserted, "skipped": skipped, "total_json": len(players)}), 200
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500


@app.route('/api/admin/db_player_stats', methods=['POST'])
def db_player_stats():
    """一次性端點：列出 DB 內各聯盟球員數量（診斷用）"""
    body = request.get_json(silent=True) or {}
    if body.get('secret') != os.getenv('ADMIN_SECRET', 'predictx-admin-2026'):
        return jsonify({"error": "unauthorized"}), 403
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT t.league, COUNT(p.player_id) AS cnt
            FROM predictx.teams t
            JOIN predictx.player_teams pt ON t.team_id = pt.team_id
            JOIN predictx.players p ON pt.player_id = p.player_id
            WHERE pt.is_active = true
            GROUP BY t.league
            ORDER BY t.league
        """)
        by_league = cur.fetchall()

        # Sample 球員 (NBA, WNBA)
        samples = {}
        for lg in ('NBA', 'WNBA', 'MLB', 'CPBL', 'NPB'):
            cur.execute("""
                SELECT p.player_id, p.player_name, p.position, t.english_name
                FROM predictx.players p
                JOIN predictx.player_teams pt ON p.player_id = pt.player_id
                JOIN predictx.teams t ON pt.team_id = t.team_id
                WHERE t.league = %s AND pt.is_active = true
                LIMIT 3
            """, (lg,))
            samples[lg] = [dict(r) for r in cur.fetchall()]

        cur.close()
        return jsonify({
            "by_league": [dict(r) for r in by_league],
            "samples": samples,
        }), 200
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500


@app.route('/api/admin/migrate_pitcher_tracking', methods=['POST'])
def migrate_pitcher_tracking():
    """一次性 migration：加 pitcher_updated_at 與 last_analyzed_pitcher_update 欄位"""
    body = request.get_json(silent=True) or {}
    if body.get('secret') != os.getenv('ADMIN_SECRET', 'predictx-admin-2026'):
        return jsonify({"error": "unauthorized"}), 403
    try:
        conn = get_db()
        cur = conn.cursor()
        results = []
        # 加欄位（IF NOT EXISTS — PostgreSQL 9.6+）
        for sql, desc in [
            ("ALTER TABLE predictx.games ADD COLUMN IF NOT EXISTS pitcher_updated_at TIMESTAMPTZ",
             "games.pitcher_updated_at"),
            ("ALTER TABLE predictx.game_analysis ADD COLUMN IF NOT EXISTS last_analyzed_pitcher_update TIMESTAMPTZ",
             "game_analysis.last_analyzed_pitcher_update"),
        ]:
            try:
                cur.execute(sql)
                results.append({"step": desc, "status": "ok"})
            except Exception as e:
                conn.rollback()
                cur = conn.cursor()
                results.append({"step": desc, "status": "error", "error": str(e)[:200]})

        # 建立 index 加速 get_pending_games
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_games_pitcher_updated_at ON predictx.games (pitcher_updated_at)")
            results.append({"step": "idx_games_pitcher_updated_at", "status": "ok"})
        except Exception as e:
            conn.rollback()
            cur = conn.cursor()
            results.append({"step": "idx_games_pitcher_updated_at", "status": "skipped", "error": str(e)[:200]})

        conn.commit()
        cur.close()
        return jsonify({"status": "migration_applied", "results": results}), 200
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500


@app.route('/api/admin/check_settlement', methods=['POST'])
def check_settlement():
    """診斷 endpoint：檢查指定 game 的 analysis_data->actual_result 內容"""
    body = request.get_json(silent=True) or {}
    if body.get('secret') != os.getenv('ADMIN_SECRET', 'predictx-admin-2026'):
        return jsonify({"error": "unauthorized"}), 403
    try:
        game_ids = body.get('game_ids', [])
        if not game_ids:
            return jsonify({"error": "need game_ids"}), 400

        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT g.game_id::text, g.match_date, g.status, g.home_team_score, g.away_team_score,
                   ga.analysis_data,
                   ga.analysis_data->'actual_result' as actual_result,
                   ht.english_name as home_team, at.english_name as away_team
            FROM predictx.games g
            LEFT JOIN predictx.game_analysis ga ON g.game_id = ga.game_id
            JOIN predictx.teams ht ON g.home_team_id = ht.team_id
            JOIN predictx.teams at ON g.away_team_id = at.team_id
            WHERE g.game_id = ANY(%s::uuid[])
        """, (game_ids,))
        rows = cur.fetchall()
        cur.close()
        return jsonify({
            "count": len(rows),
            "games": [dict(r) for r in rows]
        }), 200
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500


if __name__ == "__main__":
    port = int(os.getenv('PORT', 8081))
    app.run(host="0.0.0.0", port=port, debug=False)


# 已於 2026-06-17 移除 FIFA 端點 — 不再提供 FIFA 相關 API 行為