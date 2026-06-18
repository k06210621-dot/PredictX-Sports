#!/usr/bin/env python3
"""
fix_predicted_scores.py
=======================
一次性校正腳本：掃描所有 game_analysis 的 predicted_score，
確保與 home_win_probability / away_win_probability 一致。

背景：
commit c9cc11a 之後新分析會自動校正，但既有 37 場分析仍存矛盾。
本腳本把同樣的 _reconcile_predicted_score 邏輯套用到歷史資料。

使用：
    python fix_predicted_scores.py --dry-run   # 只看會改幾筆
    python fix_predicted_scores.py            # 實際 UPDATE
"""

import os
import re
import sys
import json
import argparse
import psycopg2
from psycopg2.extras import RealDictCursor

# 不同聯盟的合理分數範圍（與 analysis_engine.py 一致）
SCORE_RANGES = {
    "MLB": (2, 9),
    "NBA": (95, 135),
    "NPB": (2, 9),
    "CPBL": (2, 9),
}


def reconcile_predicted_score(predicted_score, home_prob, away_prob, league=""):
    """與 AnalysisEngine._reconcile_predicted_score 邏輯一致"""
    lo, hi = SCORE_RANGES.get((league or "").upper(), (2, 9))

    original_score = None
    if predicted_score:
        m = re.search(r'(\d+)\s*[-－–]\s*(\d+)', str(predicted_score))
        if m:
            original_score = (int(m.group(1)), int(m.group(2)))

    prob_diff = abs(home_prob - away_prob)
    if prob_diff < 0.05:
        return predicted_score, False  # 不需校正

    home_favorite = home_prob > away_prob

    if original_score is None:
        mid = (lo + hi) // 2
        original_score = (mid, mid)
    h_score, a_score = original_score

    changed = False

    if home_favorite and h_score <= a_score:
        changed = True
        if h_score == a_score:
            h_score = min(h_score + 1, hi)
        else:
            # 翻轉：max → favorite, min → underdog，再 +1 給 favorite
            new_fav = max(h_score, a_score) + 1
            new_und = min(h_score, a_score)
            if home_favorite:
                h_score, a_score = new_fav, new_und
            else:
                h_score, a_score = new_und, new_fav
    elif (not home_favorite) and a_score <= h_score:
        changed = True
        if h_score == a_score:
            a_score = min(a_score + 1, hi)
        else:
            new_fav = max(h_score, a_score) + 1
            new_und = min(h_score, a_score)
            if home_favorite:
                h_score, a_score = new_fav, new_und
            else:
                h_score, a_score = new_und, new_fav

    h_score = max(lo, min(hi, h_score))
    a_score = max(lo, min(hi, a_score))

    favorite_score = h_score if home_favorite else a_score
    underdog_score = a_score if home_favorite else h_score
    if favorite_score - underdog_score < 1 and prob_diff > 0.1:
        changed = True
        underdog_score = max(lo, favorite_score - 2)
        if home_favorite:
            h_score, a_score = favorite_score, underdog_score
        else:
            h_score, a_score = underdog_score, favorite_score

    return f"{h_score}-{a_score}", changed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="只統計，不 UPDATE")
    args = parser.parse_args()

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ 需要 DATABASE_URL 環境變數")
        sys.exit(1)
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    conn = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
    cur = conn.cursor()

    # 抓所有有 analysis_data 的 game
    cur.execute("""
        SELECT ga.game_id,
               ga.analysis_data,
               g.match_date,
               th.league
        FROM predictx.game_analysis ga
        JOIN predictx.games g ON ga.game_id = g.game_id
        JOIN predictx.teams th ON g.home_team_id = th.team_id
    """)
    rows = cur.fetchall()
    print(f"總分析數: {len(rows)} 場\n")

    total_changed = 0
    by_league = {}

    for row in rows:
        game_id = row['game_id']
        data = row['analysis_data'] or {}
        league = row['league'] or ''

        hp = data.get('home_win_probability')
        ap = data.get('away_win_probability')
        ps = data.get('predicted_score')

        if hp is None or ap is None or not ps:
            continue

        try:
            hp = float(hp)
            ap = float(ap)
        except (ValueError, TypeError):
            continue

        new_ps, changed = reconcile_predicted_score(ps, hp, ap, league)
        by_league.setdefault(league, {"scanned": 0, "changed": 0})

        by_league[league]["scanned"] += 1
        if changed:
            by_league[league]["changed"] += 1
            total_changed += 1

            print(f"[{league}] {row['match_date']} game_id={game_id[:8]}")
            print(f"  原始: prob=home{hp:.2f}/away{ap:.2f}, score={ps}")
            print(f"  校正: score={new_ps}")

            if not args.dry_run:
                # 更新 JSONB
                cur.execute("""
                    UPDATE predictx.game_analysis
                    SET analysis_data = jsonb_set(
                        analysis_data,
                        '{predicted_score}',
                        %s::jsonb,
                        true
                    )
                    WHERE game_id = %s::uuid
                """, (json.dumps(new_ps), game_id))

    if not args.dry_run:
        conn.commit()
        print(f"\n✅ 已 UPDATE {total_changed} 場")
    else:
        print(f"\n[DRY RUN] 將 UPDATE {total_changed} 場（不實際執行）")

    print("\n=== 各聯盟統計 ===")
    for lg, stats in by_league.items():
        print(f"  {lg}: 掃描 {stats['scanned']} 場, 矛盾 {stats['changed']} 場")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()