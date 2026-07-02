
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
                JOIN predictx.game_analysis ga ON g.game_id = ga.game_id
                JOIN predictx.teams ht ON g.home_team_id = ht.team_id
                WHERE g.home_team_score IS NOT NULL
                  AND g.away_team_score IS NOT NULL
            """
        else:
            query = """
                SELECT g.game_id, g.home_team_score, g.away_team_score, ga.analysis_data, ht.league
                FROM predictx.games g
                JOIN predictx.game_analysis ga ON g.game_id = ga.game_id
                JOIN predictx.teams ht ON g.home_team_id = ht.team_id
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

        # 🆕 先處理 POSTPONED/CANCELLED 的賽事（標記為無法驗證，避免污染驗證率）
        postponed_count = self._settle_postponed_games()
        if postponed_count:
            print(f"  Settled {postponed_count} postponed/cancelled games (marked as not-evaluable).")

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
                UPDATE predictx.game_analysis 
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

        if actual_winner == 'draw':
            # 平手不計入驗證率（is_hit = None），避免污染命中率
            is_hit = None
            analysis_data['actual_result'] = {
                "is_hit": None,
                "actual_winner": 'draw',
                "predicted_winner": predicted_winner,
                "home_prob_norm": round(home_prob_norm, 4),
                "actual_score": f"{int(actual_home_score)}-{int(actual_away_score)}",
                "reason": "draw（平手，不予計算）",
                "settled_at": datetime.now().isoformat()
            }
        else:
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
            UPDATE predictx.game_analysis
            SET analysis_data = %s, updated_at = CURRENT_TIMESTAMP
            WHERE game_id = %s
        """
        self.cur.execute(update_query, (json.dumps(analysis_data), game_id))

        # 🆕 [2026-06-24] 同步補寫 ai_prediction_history 回流（只補尚未結算的歷史快照）
        # 注意：如果同一場有多個 prompt_version 快照，全部都會被更新
        try:
            self.cur.execute(
                """
                UPDATE predictx.ai_prediction_history
                SET settled_at = NOW(),
                    actual_winner = %s,
                    is_hit = %s
                WHERE game_id = %s::uuid
                  AND settled_at IS NULL
                """,
                (actual_winner, is_hit, game_id)
            )
        except Exception as hist_err:
            # 不讓歷史表寫入失敗影響結算
            print(f"  ⚠ ai_prediction_history update skip (non-fatal): {hist_err}")

        print(f"  Settled (win/loss): {int(actual_home_score)}-{int(actual_away_score)}, hit={is_hit}")

    def close(self):
        self.cur.close()
        self.conn.close()

    def _settle_postponed_games(self):
        """
        處理 POSTPONED / CANCELLED 的賽事
        目的：
          1. 避免「幽靈賽事」（status=POSTPONED 但無 actual_result，導致永遠「未驗證」）
          2. 明確標記為 is_hit=None（驗證率計算時會被過濾）
          3. 不會污染 AI 驗證率的分母與分子

        設計：
          - 只處理「已分析過 AI」但「actual_result 還是 NULL」且「狀態為 POSTPONED/CANCELLED」的賽事
          - 寫入 actual_result = {is_hit: None, reason: "postponed", ...}
        """
        query = """
            SELECT g.game_id, g.status, ga.analysis_data, ht.league
            FROM predictx.games g
            JOIN predictx.game_analysis ga ON g.game_id = ga.game_id
            JOIN predictx.teams ht ON g.home_team_id = ht.team_id
            WHERE LOWER(g.status) IN ('postponed', 'cancelled', 'suspended')
              AND (ga.analysis_data->'actual_result' IS NULL
                   OR (ga.analysis_data->'actual_result'->>'is_hit') IS NULL
                   OR (ga.analysis_data->'actual_result'->>'is_hit')::text = 'null')
        """
        try:
            self.cur.execute(query)
            postponed_games = self.cur.fetchall()
        except Exception:
            # 連線失效，重新建立
            self.conn.close()
            self._get_connection()
            self.cur = self.conn.cursor()
            self.cur.execute(query)
            postponed_games = self.cur.fetchall()

        if not postponed_games:
            return 0

        count = 0
        for game in postponed_games:
            game_id = game['game_id']
            league = game['league']
            status = game['status']
            analysis_data = game['analysis_data'] or {}

            # 寫入 actual_result，is_hit = None（驗證率計算會過濾掉）
            analysis_data['actual_result'] = {
                "is_hit": None,
                "actual_winner": None,
                "predicted_winner": None,
                "home_prob_norm": None,
                "actual_score": None,
                "reason": f"賽事{status}（無法驗證）",
                "settled_at": datetime.now().isoformat()
            }

            update_query = """
                UPDATE predictx.game_analysis
                SET analysis_data = %s, updated_at = CURRENT_TIMESTAMP
                WHERE game_id = %s
            """
            self.cur.execute(update_query, (json.dumps(analysis_data), game_id))
            count += 1
            print(f"  Marked {status}: {game_id[:8]} ({league})")

        self.conn.commit()
        return count

if __name__ == "__main__":
    engine = SettlementEngine()
    try:
        count = engine.settle_games(re_settle_all=True)
        print(f"Total settled: {count}")
    finally:
        engine.close()
