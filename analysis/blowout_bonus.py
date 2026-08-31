"""
MLB blowout bonus calculator
計算「打爆係數」bonus（0~3），用於放大 MLB 比分差距。

觸發條件：一方先發易被狙擊（高 ERA / 負 K-BB）+ 對手打線火力強（場均得分高）。
只在 MLB 使用；NPB/CPBL 回傳 0。

🆕 [2026-08-31] 擴充 NPB/CPBL 也納入 blowout 計算（原本只 MLB）。
   理由：CPBL 預測分差 79% 為 1 分，但實際 CPBL 平均分差 2.89，
   需要「投手近況偏差」作為擴充觸發條件，把「最近 3 場 ERA 偏差大」的場次拉大比分。
"""
def compute_blowout_bonus(features, home_favorite):
    try:
        league = (features.get('league') or '').upper()
        # 🆕 [2026-08-31] 擴充：NPB/CPBL 也納入（原只 MLB）
        if league not in ('MLB', 'NPB', 'CPBL'):
            return 0
        bonus = 0
        # 投手 stats 來源依聯盟不同
        if league == 'MLB':
            pitchers = features.get('mlb_pitchers') or {}
        elif league == 'NPB':
            pitchers = features.get('npb_pitchers') or {}
        else:  # CPBL
            pitchers = features.get('cpbl_pitchers') or {}
        hp = (pitchers.get('home_pitcher') or {}).get('stats') or {}
        ap = (pitchers.get('away_pitcher') or {}).get('stats') or {}
        und_stats = ap if home_favorite else hp

        # 觸發 1: underdog 投手 ERA 偏高（MLB 原本邏輯）
        und_era = float(und_stats.get('era') or 0)
        if und_era >= 6.0:
            bonus += 2
        elif und_era >= 5.0:
            bonus += 1

        # 觸發 2: underdog 投手 K-BB 為負（MLB 原本邏輯）
        try:
            und_k9 = float(und_stats.get('k_per_9') or 0)
            und_bb9 = float(und_stats.get('bb_per_9') or 0)
            if und_k9 - und_bb9 < 0:
                bonus += 1
        except (ValueError, TypeError):
            pass

        # 觸發 3: favorite 打線場均得分高（MLB 原本邏輯）
        fav_form = features.get('home_recent_form' if home_favorite else 'away_recent_form') or {}
        fav_avg = float(fav_form.get('avg_goals_for') or 0)
        if fav_avg >= 6.5:
            bonus += 2
        elif fav_avg >= 5.5:
            bonus += 1

        # 🆕 [2026-08-31] 觸發 4: 投手近況偏差（NPB/CPBL/MLB 都套用）
        # 邏輯：若 LLM 偵測到 underdog 投手「近 3 場 ERA」嚴重偏離整季 ERA，
        #       表示該投手正處於失控/超神狀態，會拉大比分差距。
        # 資料來源：features['narrative'] 或 features['pitcher_recent'] 等結構
        #          （由 prompt 中的「home_pitcher 降溫中（近3場 ERA=7.69, 整季=4.21）」
        #          等提示注入）
        try:
            # 嘗試從多個可能的 features 路徑取得「近 3 場 ERA」
            und_recent_era = None
            und_season_era = und_era
            # 路徑 A: features.pitcher_recent.{home|away}.recent_era
            recent = features.get('pitcher_recent') or {}
            side = 'home' if home_favorite else 'away'
            und_recent_era = float((recent.get(side) or {}).get('recent_era') or 0)
            # 若沒拿到，嘗試路徑 B: features.npb_pitchers 或 cpbl_pitchers 內的 recent_era
            if not und_recent_era and isinstance(und_stats, dict):
                und_recent_era = float(und_stats.get('recent_era') or 0)
            if und_recent_era > 0 and und_season_era > 0:
                diff = und_recent_era - und_season_era
                # 偏差 > 2.0：明顯失控（近 3 場嚴重高於整季）
                if diff > 2.0:
                    bonus += 1
        except (ValueError, TypeError, AttributeError):
            pass

        return min(bonus, 4)  # 🆕 [2026-08-31] 上限 3 → 4（允許投手近況偏差再 +1）
    except Exception:
        return 0
