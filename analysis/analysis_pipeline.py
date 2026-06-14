import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
from analysis_engine import AnalysisEngine

# --- 配置區 ---
DB_CONFIG = {
    "dbname": "sports_db",
    "user": "jero",
    "password": "",
    "host": "localhost",
    "port": 5432
}

class AnalysisPipeline:
    def __init__(self):
        self.conn = psycopg2.connect(**DB_CONFIG)
        self.cur = self.conn.cursor(cursor_factory=RealDictCursor)
        self.engine = AnalysisEngine()

    def get_pending_games(self, target_date=None):
        """
        獲取需要分析的比賽：
        1. 比賽狀態為 'SCHEDULED'
        2. 比賽日期等於 target_date (若提供)
        3. 沒有分析結果 或 分析結果已過期 (12小時)
        """
        if target_date:
            # 篩選特定日期的賽事 (status 為全小寫)
            query = """
                SELECT g.game_id 
                FROM predictx.games g
                LEFT JOIN predictx.game_analysis ga ON g.game_id = ga.game_id
                WHERE g.status ILIKE 'scheduled'
                  AND g.match_date = %s
                  AND (ga.analysis_id IS NULL OR ga.updated_at < NOW() - INTERVAL '12 hours')
            """
            self.cur.execute(query, (target_date,))
        else:
            # 預設篩選當天 (status 為全小寫)
            query = """
                SELECT g.game_id 
                FROM predictx.games g
                LEFT JOIN predictx.game_analysis ga ON g.game_id = ga.game_id
                WHERE g.status ILIKE 'scheduled'
                  AND g.match_date = CURRENT_DATE
                  AND (ga.analysis_id IS NULL OR ga.updated_at < NOW() - INTERVAL '12 hours')
            """
            self.cur.execute(query)
        
        return self.cur.fetchall()

    def save_analysis(self, game_id, analysis_result):
        if not analysis_result:
            return False
            
        query = """
            INSERT INTO predictx.game_analysis (game_id, analysis_data, updated_at)
            VALUES (%s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (game_id) 
            DO UPDATE SET 
                analysis_data = EXCLUDED.analysis_data,
                updated_at = CURRENT_TIMESTAMP;
        """
        try:
            self.cur.execute(query, (game_id, json.dumps(analysis_result)))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Database Save Error for game {game_id}: {e}")
            self.conn.rollback()
            return False

    def run_pipeline(self, target_date=None):
        date_str = target_date if target_date else "TODAY"
        print(f"Starting Analysis Pipeline for {date_str}...")
        
        pending_games = self.get_pending_games(target_date)
        print(f"Found {len(pending_games)} games to analyze.")
        
        success_count = 0
        for game in pending_games:
            game_id = game['game_id']
            try:
                result = self.engine.analyze_game(game_id)
                if result and self.save_analysis(game_id, result):
                    print(f"Successfully analyzed and saved game {game_id}")
                    success_count += 1
            except Exception as e:
                print(f"Unexpected error analyzing game {game_id}: {e}")
        
        print(f"Pipeline finished. Processed {success_count}/{len(pending_games)} games.")

    def close(self):
        self.engine.close()
        self.cur.close()
        self.conn.close()

if __name__ == "__main__":
    import sys
    pipeline = AnalysisPipeline()
    try:
        # 支援命令行參數: python analysis_pipeline.py [YYYY-MM-DD]
        target = sys.argv[1] if len(sys.argv) > 1 else None
        pipeline.run_pipeline(target_date=target)
    finally:
        pipeline.close()
