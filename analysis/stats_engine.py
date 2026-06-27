
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
import json


def _get_db_config():
    """優先使用 Railway 注入的 DATABASE_URL，fallback 到本地參數"""
    database_url = os.getenv('DATABASE_URL')
    if database_url:
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        return database_url
    return {
        "dbname": os.getenv('DB_NAME', 'sports_db'),
        "user": os.getenv('DB_USER', 'jero'),
        "password": os.getenv('DB_PASSWORD', ''),
        "host": os.getenv('DB_HOST', 'localhost'),
        "port": os.getenv('DB_PORT', 5432)
    }


class StatsEngine:
    """
    統計分析引擎 — 使用延遲連線設計，避免 import 時崩潰
    第一次呼叫查詢方法時才連線，確保 app 啟動後 healthcheck 可通過
    """

    def __init__(self):
        self.conn = None
        self._db_url = _get_db_config()

    def _ensure_conn(self):
        """延遲連線：第一次使用時才建立連線，並設 autocommit 避免 transaction 中毒"""
        if self.conn is None or self.conn.closed:
            self.conn = psycopg2.connect(self._db_url, cursor_factory=RealDictCursor)
            # 用 autocommit 模式，單筆查詢失敗不會卡住後續查詢
            self.conn.autocommit = True

    def get_overall_hit_rates(self, max_games=800):
        """
        Calculate hit rate per league, limited to the most recent N games.
        Default 800 games to keep the rate responsive to recent performance.
        """
        self._ensure_conn()
        query = """
            WITH ranked AS (
                SELECT
                    t.league,
                    (ga.analysis_data->'actual_result'->>'is_hit')::boolean as is_hit,
                    ROW_NUMBER() OVER (
                        PARTITION BY t.league
                        ORDER BY g.match_date DESC, g.game_id DESC
                    ) as rn
                FROM predictx.game_analysis ga
                JOIN predictx.games g ON ga.game_id = g.game_id
                JOIN predictx.teams t ON g.home_team_id = t.team_id
                WHERE ga.analysis_data->'actual_result' IS NOT NULL
                  AND (ga.analysis_data->'actual_result'->>'is_hit')::boolean IS NOT NULL
                  AND t.league != 'FIFA'
            )
            SELECT
                league,
                COUNT(*) as total_analyzed,
                COUNT(*) FILTER (WHERE is_hit = true) as total_hits,
                ROUND(
                    (COUNT(*) FILTER (WHERE is_hit = true))::numeric /
                    NULLIF(COUNT(*), 0), 3
                ) as hit_rate
            FROM ranked
            WHERE rn <= %s
            GROUP BY league
        """
        cur = self.conn.cursor()
        try:
            cur.execute(query, (max_games,))
            results = cur.fetchall()
        except Exception:
            self.conn.rollback()
            raise
        finally:
            cur.close()
        return results

    def get_hit_rate_trend(self, league=None, limit=50):
        """
        Get hit rate trend by day for the last N games.
        """
        self._ensure_conn()

        league_filter = "AND t.league = %s" if league else ""
        params = [league] if league else []

        query = f"""
            WITH recent_games AS (
                SELECT
                    g.match_date,
                    (ga.analysis_data->'actual_result'->>'is_hit')::boolean as is_hit
                FROM predictx.game_analysis ga
                JOIN predictx.games g ON ga.game_id = g.game_id
                JOIN predictx.teams t ON g.home_team_id = t.team_id
                WHERE ga.analysis_data->'actual_result' IS NOT NULL
                  AND (ga.analysis_data->'actual_result'->>'is_hit')::boolean IS NOT NULL
                {league_filter}
                ORDER BY g.match_date DESC
                LIMIT %s
            )
            SELECT
                match_date as date,
                COUNT(*) as games_count,
                ROUND(
                    (COUNT(*) FILTER (WHERE is_hit = true))::numeric /
                    NULLIF(COUNT(*), 0), 3
                ) as daily_hit_rate
            FROM recent_games
            GROUP BY match_date
            ORDER BY match_date ASC
        """

        cur = self.conn.cursor()
        try:
            cur.execute(query, params + [limit])
            results = cur.fetchall()
        except Exception:
            self.conn.rollback()
            raise
        finally:
            cur.close()

        # Convert date objects to strings for JSON serialization
        for r in results:
            if isinstance(r['date'], (datetime,)):
                r['date'] = r['date'].strftime('%Y-%m-%d')
            elif hasattr(r['date'], 'isoformat'):
                r['date'] = r['date'].isoformat()

        return results

    def close(self):
        if self.conn and not self.conn.closed:
            self.conn.close()
            self.conn = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


if __name__ == "__main__":
    # Simple test run
    with StatsEngine() as engine:
        print("--- League Hit Rates ---")
        print(engine.get_overall_hit_rates())
        print("\n--- Trend (Overall, last 50) ---")
        print(engine.get_hit_rate_trend())
