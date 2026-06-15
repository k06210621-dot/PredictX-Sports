
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import json
import os

DB_CONFIG = {
    "dbname": "sports_db",
    "user": "jero",
    "password": "",
    "host": "localhost",
    "port": 5432
}

class SettlementEngine:
    def __init__(self, conn=None):
        if conn:
            self.conn = conn
            self.cur = conn.cursor(cursor_factory=RealDictCursor)
        else:
            database_url = os.getenv('DATABASE_URL')
            if database_url:
                if database_url.startswith('postgres://'):
                    database_url = database_url.replace('postgres://', 'postgresql://', 1)
                self.conn = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
            else:
                self.conn = psycopg2.connect(**DB_CONFIG)
            self.cur = self.conn.cursor(cursor_factory=RealDictCursor)

    def settle_games(self, re_settle_all=False):
        """結算已結束賽事，比對 AI 預測與實際結果"""
        if re_settle_all:
            print("Re-settling ALL games...")
            query = """
                SELECT g.game_id, g.home_team_score, g.away_team_score, ga.analysis_data, ht.league
                FROM predictx.games g
                JOIN game_analysis ga ON g.game_id = ga.game_id
                JOIN teams ht ON g.home_team_id = ht.team_id
                WHERE g.home_team_score IS NOT NULL
                  AND g.away_team_score IS NOT NULL
            """
        else:
            query = """
                SELECT g.game_id, g.home_team_score, g.away_team_score, ga.analysis_data, ht.league
                FROM predictx.games g
                JOIN game_analysis ga ON g.game_id = ga.game_id
                JOIN teams ht ON g.home_team_id = ht.team_id
                WHERE (LOWER(g.status) = 'final')
                  AND (ga.analysis_data->'actual_result' IS NULL)
                  AND g.home_team_score IS NOT NULL
                  AND g.away_team_score IS NOT NULL
            """
        
        self.cur.execute(query)
        pending_games = self.cur.fetchall()
        
        if not pending_games:
            print("No games pending settlement.")
            return 0

        settled_count = 0
        for game in pending_games:
            game_id = game['game_id']
            actual_home_score = float(game['home_team_score'])
            actual_away_score = float(game['away_team_score'])
            analysis_data = game['analysis_data']
            league = game['league']
            
            # 1. 判定實際結果
            actual_total_goals = actual_home_score + actual_away_score
            
            if league == 'FIFA':
                # FIFA 使用 Over/Under 2.5 結算
                actual_over_under = actual_total_goals > 2.5
                predicted_over_under = analysis_data.get('over_under_2_5', None)
                
                if predicted_over_under is not None:
                    is_hit = (actual_over_under == predicted_over_under)
                    actual_result = {
                        "is_hit": is_hit,
                        "settlement_type": "over_under_2.5",
                        "actual_over_under": actual_over_under,
                        "predicted_over_under": predicted_over_under,
                        "actual_total_goals": actual_total_goals,
                        "actual_score": f"{int(actual_home_score)}-{int(actual_away_score)}",
                        "settled_at": datetime.now().isoformat()
                    }
                else:
                    # 無 over_under 預測時，回退到勝負判斷
                    self._settle_win_loss(game_id, actual_home_score, actual_away_score, analysis_data)
                    settled_count += 1
                    continue
            else:
                # 棒球/籃球使用勝負結算
                self._settle_win_loss(game_id, actual_home_score, actual_away_score, analysis_data)
                settled_count += 1
                continue
            
            # 5. 更新 analysis_data
            analysis_data['actual_result'] = actual_result
            
            update_query = """
                UPDATE game_analysis 
                SET analysis_data = %s, updated_at = CURRENT_TIMESTAMP 
                WHERE game_id = %s
            """
            self.cur.execute(update_query, (json.dumps(analysis_data), game_id))
            settled_count += 1
            
        self.conn.commit()
        print(f"Successfully settled {settled_count} games.")
        return settled_count

    def _settle_win_loss(self, game_id, actual_home_score, actual_away_score, analysis_data):
        """以勝負結算（棒球/籃球用）"""
        # 判定實際勝方
        if actual_home_score > actual_away_score:
            actual_winner = 'home'
        elif actual_away_score > actual_home_score:
            actual_winner = 'away'
        else:
            actual_winner = 'draw'

        # 判定 AI 預測勝方
        home_prob = float(analysis_data.get('home_win_probability', 0.5))
        away_prob = float(analysis_data.get('away_win_probability', 0.5))
        total = home_prob + away_prob
        home_prob_norm = home_prob / total if total > 0 else 0.5

        if home_prob_norm > 0.5:
            predicted_winner = 'home'
        elif home_prob_norm < 0.5:
            predicted_winner = 'away'
        else:
            confidence = float(analysis_data.get('confidence', 5))
            predicted_winner = 'home' if confidence >= 5 else 'draw'

        is_hit = (actual_winner == predicted_winner)

        analysis_data['actual_result'] = {
            "is_hit": is_hit,
            "actual_winner": actual_winner,
            "predicted_winner": predicted_winner,
            "home_prob_norm": round(home_prob_norm, 4),
            "actual_score": f"{int(actual_home_score)}-{int(actual_away_score)}",
            "settled_at": datetime.now().isoformat()
        }

        update_query = """
            UPDATE game_analysis 
            SET analysis_data = %s, updated_at = CURRENT_TIMESTAMP 
            WHERE game_id = %s
        """
        self.cur.execute(update_query, (json.dumps(analysis_data), game_id))
        print(f"  Settled (win/loss): {int(actual_home_score)}-{int(actual_away_score)}, hit={is_hit}")

    def close(self):
        self.cur.close()
        self.conn.close()

if __name__ == "__main__":
    engine = SettlementEngine()
    try:
        count = engine.settle_games(re_settle_all=True)
        print(f"Total settled: {count}")
    finally:
        engine.close()
