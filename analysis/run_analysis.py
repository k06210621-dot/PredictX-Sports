#!/usr/bin/env python3
"""
PredictX Sports 每日排程分析腳本
- 由 Railway Cron 或外部排程器呼叫
- 分析今日 + 明日賽事
- 執行結算（settlement）
- 支援 DATABASE_URL 環境變數（Railway 自動注入）
"""

import os
import sys
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta

# 確保 analysis/ 目錄在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from analysis_engine import AnalysisEngine
from settlement_engine import SettlementEngine


def get_db_connection():
    """優先使用 Railway 注入的 DATABASE_URL，fallback 到本地參數"""
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


def get_pending_games(conn, target_dates: list):
    """取得指定日期範圍內尚未分析（或分析過期）的 scheduled 賽事"""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    placeholders = ','.join(['%s'] * len(target_dates))
    query = f"""
        SELECT g.game_id::text
        FROM games g
        LEFT JOIN game_analysis ga ON g.game_id = ga.game_id
        WHERE g.status ILIKE 'scheduled'
          AND g.match_date::date IN ({placeholders})
          AND (ga.analysis_id IS NULL OR ga.updated_at < NOW() - INTERVAL '12 hours')
        ORDER BY g.match_date
    """
    cur.execute(query, target_dates)
    games = cur.fetchall()
    cur.close()
    return games


def save_analysis(conn, game_id, analysis_result):
    """寫入或更新 analysis_data"""
    if not analysis_result:
        return False
    cur = conn.cursor()
    try:
        cur.execute(
            """INSERT INTO game_analysis (game_id, analysis_data, updated_at)
               VALUES (%s, %s, CURRENT_TIMESTAMP)
               ON CONFLICT (game_id)
               DO UPDATE SET
                   analysis_data = EXCLUDED.analysis_data,
                   updated_at = CURRENT_TIMESTAMP""",
            (game_id, json.dumps(analysis_result))
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"  ❌ DB save error for {game_id}: {e}")
        conn.rollback()
        return False
    finally:
        cur.close()


def main():
    print(f"=== PredictX Daily Pipeline START === {datetime.now().isoformat()}")

    # 1. 連線資料庫
    try:
        conn = get_db_connection()
        print("✅ Database connected")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        sys.exit(1)

    # 2. 計算目標日期：今日 + 明日（台北時間）
    taipei_tz = datetime.now().astimezone().tzinfo
    today = datetime.now(taipei_tz).strftime('%Y-%m-%d')
    tomorrow = (datetime.now(taipei_tz) + timedelta(days=1)).strftime('%Y-%m-%d')
    target_dates = [today, tomorrow]
    print(f"📅 Target dates: {target_dates}")

    # 3. 分析賽事
    pending = get_pending_games(conn, target_dates)
    print(f"🔍 Found {len(pending)} games to analyze")

    if pending:
        engine = AnalysisEngine()
        success = 0
        for idx, game in enumerate(pending):
            game_id = game['game_id']
            try:
                result = engine.analyze_game(game_id)
                if result and save_analysis(conn, game_id, result):
                    print(f"  [{idx+1}/{len(pending)}] ✓ {game_id[:8]}...")
                    success += 1
                else:
                    print(f"  [{idx+1}/{len(pending)}] ✗ {game_id[:8]}... no result")
            except Exception as e:
                print(f"  [{idx+1}/{len(pending)}] ✗ {game_id[:8]}... Error: {e}")
        engine.close()
        print(f"📊 Analysis: {success}/{len(pending)} games analyzed")
    else:
        print("📊 No pending games to analyze")

    # 4. 執行結算
    try:
        settler = SettlementEngine()
        settled_count = settler.settle_games()
        print(f"💰 Settlement: {settled_count} games settled")
    except Exception as e:
        print(f"⚠️ Settlement failed: {e}")

    conn.close()
    print(f"=== PredictX Daily Pipeline END === {datetime.now().isoformat()}")


if __name__ == "__main__":
    main()
