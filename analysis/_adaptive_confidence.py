# 🆕 [2026-07-25] 自適應置信度計算 - 基於特徵品質動態調整置信度
def _calculate_adaptive_confidence(self, features, base_confidence):
    """
    基於特徵品質動態調整置信度
    
    評估因子：
    1. 數據完整度 (先發投手數據、打者 PR、投手被打 PR)
    2. 戰績差距明顯度
    3. 投手 ERA 差距
    4. 排名差距
    5. CPBL 特有：投手被打 wOBA 差距、打者 wRC+ 差距
    
    Returns: adjusted_confidence (1-10)
    """
    lg = (features.get('league') or '').upper()
    adjusted_conf = base_confidence
    
    # 1. 數據完整度評估
    data_completeness = 0
    max_completeness = 0
    
    # 先發投手數據完整度
    mlb_p = features.get('mlb_pitchers') or {}
    npb_p = features.get('npb_pitchers') or {}
    cpbl_p = features.get('cpbl_pitchers') or {}
    pitcher_data = mlb_p or npb_p or cpbl_p or {}
    home_sp = pitcher_data.get('home_pitcher') or {}
    away_sp = pitcher_data.get('away_pitcher') or {}
    if home_sp.get('stats', {}).get('era') and away_sp.get('stats', {}).get('era'):
        data_completeness += 1
    max_completeness += 1
    
    # 打者 PR 完整度
    batter_pr = features.get('cpbl_advanced', {}).get('player_pr') or {}
    h_pr = batter_pr.get('home') or []
    a_pr = batter_pr.get('away') or []
    if h_pr and a_pr:
        data_completeness += 1
    max_completeness += 1
    
    # 投手被打 PR 完整度 (CPBL)
    pa_pr = features.get('cpbl_advanced', {}).get('pitcher_against_pr') or {}
    h_pa = pa_pr.get('home') or []
    a_pa = pa_pr.get('away') or []
    if h_pa and a_pa:
        data_completeness += 1
    max_completeness += 1
    
    # 牛棚數據完整度
    bullpen = features.get('bullpen') or {}
    if bullpen.get('home') and bullpen.get('away'):
        data_completeness += 1
    max_completeness += 1
    
    # 數據完整度加分 (最高 +1)
    if max_completeness > 0:
        completeness_ratio = data_completeness / max_completeness
        if completeness_ratio >= 0.75:
            adjusted_conf = min(10, adjusted_conf + 1)
        elif completeness_ratio >= 0.5:
            adjusted_conf = min(10, adjusted_conf + 0.5)
    
    # 2. 戰績差距明顯度加分
    home_standings = features.get('home_standings') or {}
    away_standings = features.get('away_standings') or {}
    h_wp = float(home_standings.get('win_pct', 0.5) or 0.5)
    a_wp = float(away_standings.get('win_pct', 0.5) or 0.5)
    wp_diff = abs(h_wp - a_wp)
    if wp_diff > 0.20:  # 勝率差 > 20%
        adjusted_conf = min(10, adjusted_conf + 1)
    elif wp_diff > 0.10:
        adjusted_conf = min(10, adjusted_conf + 0.5)
    
    # 3. 投手 ERA 差距
    mlb_p = features.get('mlb_pitchers') or {}
    npb_p = features.get('npb_pitchers') or {}
    cpbl_p = features.get('cpbl_pitchers') or {}
    pitcher_data = features.get('pitchers') or {}
    all_p = {**mlb_p, **npb_p, **cpbl_p, **pitcher_data}
    home_p = all_p.get('home_pitcher') or {}
    away_p = all_p.get('away_pitcher') or {}
    h_era = self._safe_float(home_p.get('stats', {}).get('era'))
    a_era = self._safe_float(away_p.get('stats', {}).get('era'))
    if h_era > 0 and a_era > 0:
        era_diff = abs(h_era - a_era)
        if era_diff > 1.5:
            adjusted_conf = min(10, adjusted_conf + 1)
        elif era_diff > 0.8:
            adjusted_conf = min(10, adjusted_conf + 0.5)
    
    # 3. CPBL 特有：投手被打 wOBA 差距
    if 'CPBL' in (features.get('league') or '').upper():
        pa_pr = features.get('cpbl_advanced', {}).get('pitcher_against_pr') or {}
        h_pa = pa_pr.get('home') or []
        a_pa = pa_pr.get('away') or []
        h_woba = [float(p.get('opponent_woba', 0)) for p in h_pa if p.get('opponent_woba')]
        a_woba = [float(p.get('opponent_woba', 0)) for p in a_pa if p.get('opponent_woba')]
        if h_woba and a_woba:
            avg_h_woba = sum(h_woba) / len(h_woba)
            avg_a_woba = sum(a_woba) / len(a_woba)
            woba_diff = abs(avg_h_woba - avg_a_woba)
            if woba_diff > 0.05:
                adjusted_conf = min(10, adjusted_conf + 1)
            elif woba_diff > 0.03:
                adjusted_conf = min(10, adjusted_conf + 0.5)
    
    # 4. 打者 wRC+ 差距
    batter_pr = features.get('cpbl_advanced', {}).get('player_pr') or {}
    h_pr = batter_pr.get('home') or []
    a_pr = batter_pr.get('away') or []
    h_wrc = [float(p.get('wrc_plus', 0)) for p in h_pr if p.get('wrc_plus')]
    a_wrc = [float(p.get('wrc_plus', 0)) for p in a_pr if p.get('wrc_plus')]
    if h_wrc and a_wrc:
        avg_h_wrc = sum(h_wrc) / len(h_wrc)
        avg_a_wrc = sum(a_wrc) / len(a_wrc)
        wrc_diff = abs(avg_h_wrc - avg_a_wrc)
        if wrc_diff > 15:
            adjusted_conf = min(10, adjusted_conf + 1)
        elif wrc_diff > 8:
            adjusted_conf = min(10, adjusted_conf + 0.5)
    
    # 5. 排名差距
    home_rank = features.get('home_standings', {}).get('rank')
    away_rank = features.get('away_standings', {}).get('rank')
    if home_rank and away_rank:
        rank_diff = abs(int(home_rank) - int(away_rank))
        if rank_diff > 10:
            adjusted_conf = min(10, adjusted_conf + 1)
        elif rank_diff > 5:
            adjusted_conf = min(10, adjusted_conf + 0.5)
    
    return min(10, max(1, round(adjusted_conf)))