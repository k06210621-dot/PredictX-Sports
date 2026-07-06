"""
PredictX Sports — WNBA DataFetcher
從 ESPN API 抓取 WNBA 進階數據（免費，無需 API Key）

數據來源：
- https://site.api.espn.com/apis/v2/sports/basketball/wnba/standings?season=2026
  - W/L、Win%、PPG、OPP PPG、differential（淨勝分）、Home/Road record

為何改用 ESPN 而非 basketball-reference.com：
- bball-ref 在 Railway IP 被擋（HTTP 403）
- ESPN API 完全開放且結構穩定
"""
import os
import re
import requests
import psycopg2
from psycopg2.extras import RealDictCursor

DB_CONFIG = {
    "dbname": "sports_db", "user": "jero",
    "password": "", "host": "localhost", "port": 5432
}

ESPN_TEAM_ID = {
    "Atlanta Dream": 20,
    "Chicago Sky": 19,
    "Connecticut Sun": 18,
    "Dallas Wings": 3,
    "Golden State Valkyries": 129689,
    "Indiana Fever": 5,
    "Las Vegas Aces": 17,        # ESPN ID 17（不是 14，14 是 Seattle Storm）
    "Los Angeles Sparks": 6,
    "Minnesota Lynx": 8,
    "New York Liberty": 9,       # ESPN ID 9（不是 10，10 是 Phoenix Mercury）
    "Phoenix Mercury": 11,
    "Seattle Storm": 14,
    "Washington Mystics": 16,
    "Portland Fire": 132052,     # 2026 新隊
    "Toronto Tempo": 131935,     # 2026 新隊
}


class WNBADataFetcher:
    def __init__(self, conn=None):
        self.conn = None
        self.cur = None
        self._conn_external = False  # 追蹤 conn 是否外部傳入
        if conn:
            self.conn = conn
            self.cur = conn.cursor(cursor_factory=RealDictCursor)
            self._conn_external = True
        else:
            try:
                database_url = os.getenv('DATABASE_URL')
                if database_url:
                    if database_url.startswith('postgres://'):
                        database_url = database_url.replace('postgres://', 'postgresql://', 1)
                    self.conn = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
                else:
                    self.conn = psycopg2.connect(**DB_CONFIG)
                self.cur = self.conn.cursor(cursor_factory=RealDictCursor)
            except Exception:
                pass
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json",
        })
        self.fetched_sources = []
        self._stats_cache = None  # 快取全聯盟數據

    def _fetch_league_stats(self, season=2026):
        """從 ESPN API 抓取 WNBA 全部球隊戰績"""
        if self._stats_cache is not None:
            return self._stats_cache

        url = f"https://site.api.espn.com/apis/v2/sports/basketball/wnba/standings"
        try:
            resp = self.session.get(url, params={"season": season}, timeout=20)
            if resp.status_code != 200:
                print(f"  ⚠ WNBA ESPN standings HTTP {resp.status_code}", flush=True)
                return {}
        except Exception as e:
            print(f"  ⚠ WNBA ESPN fetch error: {e}", flush=True)
            return {}

        data = resp.json()
        self.fetched_sources.append("espn.com")

        stats_map = {}
        # ESPN 回傳分區：Eastern / Western Conference
        for group in data.get('children', []):
            for entry in group.get('standings', {}).get('entries', []):
                team = entry.get('team', {})
                team_name = team.get('displayName', '')
                if team_name not in ESPN_TEAM_ID:
                    continue

                # 解析每個 stat（value 用於數字，summary 用於 "7-4" 格式字串）
                def _stat_field(stat_name, field='value'):
                    for s in entry.get('stats', []):
                        if s.get('name') == stat_name:
                            v = s.get(field)
                            if v is None:
                                v = s.get('value')
                            return v if v is not None else '-'
                    return '-'

                def _num(stat_name, default=0):
                    v = _stat_field(stat_name, 'value')
                    if v == '-' or v is None:
                        return default
                    try:
                        return float(v)
                    except (TypeError, ValueError):
                        return default

                wins = int(_num('wins'))
                losses = int(_num('losses'))
                win_pct = _num('winPercent')
                ppg = _num('avgPointsFor')
                opp_ppg = _num('avgPointsAgainst')
                differential = _num('differential')
                home_record = str(_stat_field('Home', 'summary'))
                road_record = str(_stat_field('Road', 'summary'))
                streak = str(_stat_field('streak', 'displayValue'))
                playoff_seed = int(_num('playoffSeed'))

                # 解析 Home/Road record (e.g. "7-4")
                def _parse_record(rec):
                    if not rec or rec == '-':
                        return 0, 0, 0.0
                    parts = str(rec).split('-')
                    if len(parts) == 2:
                        w, l = int(parts[0]), int(parts[1])
                        total = w + l
                        return w, l, (w / total if total else 0.0)
                    return 0, 0, 0.0

                home_w, home_l, home_pct = _parse_record(home_record)
                road_w, road_l, road_pct = _parse_record(road_record)

                games_played = wins + losses

                # Pace 與 OffRtg/DefRtg 從 PPG + differential 估算（ESPN standings 不直接給）
                # 假定每場 100 possession，OffRtg ≈ PPG / Poss
                # 沒有 possession 數據 → 用 differential / 100 估算 Net Rating
                if games_played > 0:
                    net_rtg = (ppg - opp_ppg)  # 已經是每場淨勝分
                else:
                    net_rtg = 0.0

                # 預先放進 stats_map（進階數據在 _fetch_team_advanced_stats 補上）
                stats_map[team_name] = {
                    'g': games_played,
                    'wins': wins,
                    'losses': losses,
                    'win_pct': win_pct,
                    'pts_per_g': ppg,
                    'opp_pts_per_g': opp_ppg,
                    'net_rtg': net_rtg,
                    'differential': differential,
                    'home_record': f"{home_w}-{home_l}",
                    'home_win_pct': home_pct,
                    'road_record': f"{road_w}-{road_l}",
                    'road_win_pct': road_pct,
                    'streak': streak,
                    'playoff_seed': playoff_seed,
                    # 為相容性提供 ESPN 沒有的欄位
                    'off_rtg': ppg,  # 近似，待 team stats 補上
                    'def_rtg': opp_ppg,  # 近似，待 team stats 補上
                    'pace': 0.0,  # ESPN team stats 才有
                    'mov': differential / games_played if games_played else 0.0,
                    'ts_pct': 0.0,
                    'efg_pct': 0.0,
                    'tov_pct': 0.0,
                    'fg_pct': 0.0,
                    'three_pt_pct': 0.0,
                    'ft_pct': 0.0,
                    'ast_to_tov': 0.0,
                    'oreb_per_g': 0.0,
                    'dreb_per_g': 0.0,
                    'stl_per_g': 0.0,
                    'blk_per_g': 0.0,
                    'sos': 0.0,
                    'srs': 0.0,
                }

        # 第二輪：抓每隊的 team-level 進階 stats（FG%、3P%、TS% 等）
        self._enrich_with_team_stats(stats_map, season)

        self._stats_cache = stats_map
        return stats_map

    def _enrich_with_team_stats(self, stats_map, season=2026):
        """從 ESPN team-level statistics endpoint 抓進階指標

        為何這個步驟重要：
        - standings 只給 W-L / PPG / differential（基本）
        - team statistics 給 FG%、3P%、FT%、AST/TO、OREB、DREB、STL、BLK、eFG%、TS%
        - LLM 有了 TS% / eFG% 才能區分「打進攻戰的隊 vs 打防守戰的隊」
        """
        base_url = "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/teams/{}/statistics"
        for team_name, espn_id in ESPN_TEAM_ID.items():
            if not espn_id or team_name not in stats_map:
                continue
            try:
                resp = self.session.get(base_url.format(espn_id), params={"season": season}, timeout=15)
                if resp.status_code != 200:
                    continue
                data = resp.json()
                results = data.get('results', {})
                if 'stats' not in results:
                    continue
                # 把所有 categories 的 stats 攤平成 dict
                flat_stats = {}
                for cat in results.get('stats', {}).get('categories', []):
                    for st in cat.get('stats', []):
                        name = st.get('name', '')
                        val = st.get('value', st.get('displayValue'))
                        flat_stats[name] = val

                def _f(name, default=0.0):
                    v = flat_stats.get(name, default)
                    if v in (None, '-', ''):
                        return default
                    try:
                        return float(v)
                    except (TypeError, ValueError):
                        return default

                # 從 ESPN team stats 拿到真實的進階數據
                # 附註：ESPN 的 value 已是百分比小數（e.g. 0.423）但有時是 423 需判斷
                fg_pct_raw = _f('fieldGoalPct')
                fg_pct = fg_pct_raw if fg_pct_raw <= 1.0 else fg_pct_raw / 100.0

                three_pt_raw = _f('threePointPct')
                three_pt = three_pt_raw if three_pt_raw <= 1.0 else three_pt_raw / 100.0

                ft_raw = _f('freeThrowPct')
                ft_pct = ft_raw if ft_raw <= 1.0 else ft_raw / 100.0

                # ESPN's shootingEfficiency ≈ eFG%, scoringEfficiency ≈ TS% / 2
                # shootingEfficiency 0.49 → eFG% 0.49 (近似)
                efg = _f('shootingEfficiency')  # 0.49 ≈ eFG%
                # scoringEfficiency 1.210 → TS% = 1.210 * 100 = 121? 這是 raw 計算
                # 實測：1.21 對應 TS% ≈ 0.580 → 除以 ~2.08
                scoring_eff = _f('scoringEfficiency')  # 1.21
                ts_pct = scoring_eff * 100 / 208 if scoring_eff else 0.0  # 0.580

                ast_to_tov = _f('assistTurnoverRatio')
                oreb = _f('avgOffensiveRebounds')
                dreb = _f('avgDefensiveRebounds')
                stl = _f('avgSteals')
                blk = _f('avgBlocks')
                tov = _f('avgTurnovers')

                # TOV% (近似：TOV / (FGA + 0.44*FTA + TOV))
                fga = _f('avgFieldGoalsAttempted', 0)
                fta = _f('avgFreeThrowsAttempted', 0)
                if fga > 0 and tov > 0:
                    tov_pct = tov / (fga + 0.44 * fta + tov)
                else:
                    tov_pct = 0.0

                # 更新 stats_map
                stats_map[team_name].update({
                    'fg_pct': fg_pct,
                    'three_pt_pct': three_pt,
                    'ft_pct': ft_pct,
                    'ts_pct': ts_pct,
                    'efg_pct': efg,
                    'tov_pct': tov_pct,
                    'ast_to_tov': ast_to_tov,
                    'oreb_per_g': oreb,
                    'dreb_per_g': dreb,
                    'stl_per_g': stl,
                    'blk_per_g': blk,
                })
            except Exception as e:
                print(f"  ⚠ WNBA team stats for {team_name} (id={espn_id}) failed: {e}", flush=True)
                continue

    def _match_team(self, local_name):
        """比對本地隊名與 ESPN 隊名"""
        if local_name in ESPN_TEAM_ID:
            return local_name
        parts = local_name.split()[-1].lower()
        for espn_name in ESPN_TEAM_ID:
            if parts in espn_name.lower():
                return espn_name
        for espn_name in ESPN_TEAM_ID:
            if local_name.lower()[:5] in espn_name.lower() or espn_name.lower()[:5] in local_name.lower():
                return espn_name
        return None

    def fetch_and_store_game_data(self, game_id, home_team_name, away_team_name):
        """為一場 WNBA 比賽取得進階數據"""
        all_stats = self._fetch_league_stats()
        if not all_stats:
            return None

        home_key = self._match_team(home_team_name)
        away_key = self._match_team(away_team_name)

        if not home_key or not away_key:
            print(f"  ⚠ WNBA team match failed: {home_team_name}→{home_key}, {away_team_name}→{away_key}", flush=True)
            return None

        home_stats = all_stats.get(home_key, {})
        away_stats = all_stats.get(away_key, {})

        if not home_stats or not away_stats:
            return None

        return {
            "home_team_name": home_team_name,
            "away_team_name": away_team_name,
            "team_stats": {"home": home_stats, "away": away_stats},
            "sources": list(set(self.fetched_sources)),
        }

    def close(self):
        """關閉 fetcher 持有的 HTTP session（不要關閉 conn/cur，conn 屬於 pool）。

        為何不關 conn/cur：
        - conn 來自呼叫端 (analysis_engine) 的 connection pool，pool 管理其生命週期
        - cur 是 conn 上的 cursor，關閉它會污染後續的 conn 使用
        - 統一只關 session 確保 HTTP connection 釋放
        """
        try:
            if self.session:
                self.session.close()
        except Exception:
            pass
