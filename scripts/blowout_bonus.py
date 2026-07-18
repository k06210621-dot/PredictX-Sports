"""
MLB blowout bonus calculator
計算「打爆係數」bonus（0~3），用於放大 MLB 比分差距。

觸發條件：一方先發易被狙擊（高 ERA / 負 K-BB）+ 對手打線火力強（場均得分高）。
只在 MLB 使用；NPB/CPBL 回傳 0。
"""
def compute_blowout_bonus(features, home_favorite):
    try:
        if (features.get('league') or '').upper() != 'MLB':
            return 0
        bonus = 0
        pitchers = features.get('mlb_pitchers') or {}
        hp = (pitchers.get('home_pitcher') or {}).get('stats') or {}
        ap = (pitchers.get('away_pitcher') or {}).get('stats') or {}
        und_stats = ap if home_favorite else hp

        und_era = float(und_stats.get('era') or 0)
        if und_era >= 6.0:
            bonus += 2
        elif und_era >= 5.0:
            bonus += 1

        try:
            und_k9 = float(und_stats.get('k_per_9') or 0)
            und_bb9 = float(und_stats.get('bb_per_9') or 0)
            if und_k9 - und_bb9 < 0:
                bonus += 1
        except (ValueError, TypeError):
            pass

        fav_form = features.get('home_recent_form' if home_favorite else 'away_recent_form') or {}
        fav_avg = float(fav_form.get('avg_goals_for') or 0)
        if fav_avg >= 6.5:
            bonus += 2
        elif fav_avg >= 5.5:
            bonus += 1
        return min(bonus, 3)
    except Exception:
        return 0
