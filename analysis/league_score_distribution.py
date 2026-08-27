"""
聯盟比分分布計算器

【P0-1, 2026-08-24】
從 predictx.games 計算該聯盟最近 N 天（預設 60 天）的比分分布參數，
供 analysis_engine.py 注入到 LLM prompt。

設計原則：
- 使用「實際比分」而非「預測比分」：避免 LLM 自我循環
- 樣本不足時 fallback 到硬編碼預設值
- 8 個指標反映「該聯盟比分有多散」而非「平均多少分」
"""
import os
import re
from typing import Optional

import psycopg2
from psycopg2.extras import RealDictCursor


LEAGUE_SAMPLE_THRESHOLD = 30  # 樣本少於此值時用 fallback
DEFAULT_DAYS_BACK = 60

# Fallback 預設值（基於 2026-08-25 實測 60 天真實結算數據）
# 意義：樣本不足/DB 連線失敗時，用「歷史均值」作為最佳猜測
FALLBACK_DISTRIBUTION = {
    'MLB': {
        'sample_size': 0,
        'is_fallback': True,
        'team_score_mean': 4.45,
        'team_score_std': 3.27,
        'total_score_mean': 8.89,
        'total_score_std': 4.54,
        'run_diff_mean': 3.59,
        'run_diff_std': 3.06,
        'blowout_rate': 0.196,   # ≥6 分差比例
        'close_game_rate': 0.476,  # ≤2 分差比例
    },
    'NPB': {
        'sample_size': 0,
        'is_fallback': True,
        'team_score_mean': 3.71,
        'team_score_std': 2.91,
        'total_score_mean': 7.41,
        'total_score_std': 3.88,
        'run_diff_mean': 3.37,
        'run_diff_std': 2.76,
        'blowout_rate': 0.188,
        'close_game_rate': 0.473,
    },
    'CPBL': {
        'sample_size': 0,
        'is_fallback': True,
        'team_score_mean': 3.83,
        'team_score_std': 3.12,
        'total_score_mean': 7.66,
        'total_score_std': 4.28,
        'run_diff_mean': 3.54,
        'run_diff_std': 2.84,
        'blowout_rate': 0.216,
        'close_game_rate': 0.495,
    },
}


def parse_score(s) -> Optional[tuple]:
    """解析 '4-2' / '5 - 3' / '4:3' 格式，回傳 (home, away) 或 None"""
    if not s:
        return None
    m = re.search(r'(\d+)\s*[-－–:：比]\s*(\d+)', str(s))
    if m:
        try:
            return int(m.group(1)), int(m.group(2))
        except (ValueError, TypeError):
            return None
    return None


def _get_conn():
    """建立 psycopg2 連線（DATABASE_PUBLIC_URL 優先）"""
    db_url = os.getenv('DATABASE_PUBLIC_URL') or os.getenv('DATABASE_URL')
    if not db_url:
        raise RuntimeError('No DATABASE_URL / DATABASE_PUBLIC_URL env var')
    if db_url.startswith('postgres://'):
        db_url = db_url.replace('postgres://', 'postgresql://', 1)
    return psycopg2.connect(db_url, cursor_factory=RealDictCursor)


def compute_league_distribution(
    league: str,
    days: int = DEFAULT_DAYS_BACK,
    sample_threshold: int = LEAGUE_SAMPLE_THRESHOLD,
) -> dict:
    """
    計算指定聯盟最近 N 天（預設 60 天）的 8 個比分分布指標。

    Args:
        league: 'MLB' / 'NPB' / 'CPBL' / 'NBA' / 'WNBA'
        days: 回看天數（預設 60）
        sample_threshold: 樣本低於此值時用 fallback

    Returns:
        dict 含 8 個指標 + sample_size + is_fallback
    """
    league_upper = league.upper()

    # 非棒球聯盟不計算（避免無意義資料）
    if league_upper not in ('MLB', 'NPB', 'CPBL'):
        return {
            'sample_size': 0,
            'is_fallback': True,
            'team_score_mean': 0.0,
            'team_score_std': 0.0,
            'total_score_mean': 0.0,
            'total_score_std': 0.0,
            'run_diff_mean': 0.0,
            'run_diff_std': 0.0,
            'blowout_rate': 0.0,
            'close_game_rate': 0.0,
        }

    try:
        conn = _get_conn()
    except Exception as e:
        print(f'  ⚠ league_distribution: DB connect failed, using fallback: {e}')
        return _get_fallback(league_upper)

    parsed_scores = []
    try:
        with conn:
            cur = conn.cursor()
            cur.execute(
                '''
                SELECT g.home_team_score, g.away_team_score
                FROM predictx.games g
                JOIN predictx.teams th ON g.home_team_id = th.team_id
                WHERE UPPER(th.league) = %s
                  AND g.match_date >= CURRENT_DATE - INTERVAL '%s days'
                  AND g.status = 'FINAL'
                  AND g.home_team_score IS NOT NULL
                  AND g.away_team_score IS NOT NULL
                ''',
                (league_upper, days),
            )
            rows = cur.fetchall()
            for r in rows:
                try:
                    home = int(float(r['home_team_score']))
                    away = int(float(r['away_team_score']))
                    parsed_scores.append((home, away))
                except (ValueError, TypeError):
                    continue
    except Exception as e:
        print(f'  ⚠ league_distribution: query failed, using fallback: {e}')
        return _get_fallback(league_upper)
    finally:
        try:
            conn.close()
        except Exception:
            pass

    n = len(parsed_scores)
    if n < sample_threshold:
        print(f'  ⚠ league_distribution: {league_upper} 樣本數 {n} < {sample_threshold}，使用 fallback')
        return _get_fallback(league_upper)

    return _compute_stats(parsed_scores, n)


def _compute_stats(parsed_scores: list, n: int) -> dict:
    """從已解析的 (home, away) list 計算 8 個分布指標"""
    team_scores = []  # 所有球隊的單場得分
    total_scores = []  # 單場總得分
    run_diffs = []  # 單場分差（絕對值）

    for home, away in parsed_scores:
        team_scores.append(home)
        team_scores.append(away)
        total_scores.append(home + away)
        run_diffs.append(abs(home - away))

    def _mean(vals):
        return sum(vals) / len(vals) if vals else 0.0

    def _std(vals, mu=None):
        if not vals:
            return 0.0
        if mu is None:
            mu = _mean(vals)
        variance = sum((v - mu) ** 2 for v in vals) / len(vals)
        return variance ** 0.5

    team_mean = _mean(team_scores)
    team_std = _std(team_scores, team_mean)
    total_mean = _mean(total_scores)
    total_std = _std(total_scores, total_mean)
    diff_mean = _mean(run_diffs)
    diff_std = _std(run_diffs, diff_mean)

    blowout_count = sum(1 for d in run_diffs if d >= 6)
    close_count = sum(1 for d in run_diffs if d <= 2)
    blowout_rate = blowout_count / n if n else 0.0
    close_rate = close_count / n if n else 0.0

    return {
        'sample_size': n,
        'is_fallback': False,
        'team_score_mean': round(team_mean, 2),
        'team_score_std': round(team_std, 2),
        'total_score_mean': round(total_mean, 2),
        'total_score_std': round(total_std, 2),
        'run_diff_mean': round(diff_mean, 2),
        'run_diff_std': round(diff_std, 2),
        'blowout_rate': round(blowout_rate, 3),
        'close_game_rate': round(close_rate, 3),
    }


def _get_fallback(league: str) -> dict:
    """取得 fallback 分布（複製一份避免污染原 dict）"""
    import copy
    return copy.deepcopy(FALLBACK_DISTRIBUTION.get(league, FALLBACK_DISTRIBUTION['NPB']))


def format_distribution_prompt_section(dist: dict, league: str) -> str:
    """
    將分布 dict 格式化成 prompt 段落。

    只用於棒球聯盟（MLB / NPB / CPBL）；其他聯盟回傳空字串。
    """
    if league.upper() not in ('MLB', 'NPB', 'CPBL'):
        return ''

    if dist.get('is_fallback'):
        source_note = '（樣本不足，使用預設值）'
    else:
        source_note = f'（基於最近 {dist.get("sample_size", "?")} 場已結算場次）'

    # 聯盟特性描述（給 LLM 看的「方法論」）
    league_guidance = {
        'MLB': (
            'MLB 比賽比分變異度較高（σ={run_diff_std}），表示比賽結果方差大；\n'
            '即使是中等勝率場次，仍有約 {blowout_rate_pct}% 機率出現 ≥6 分差。\n'
            '請以此分布特徵作為比分預測的參考依據，但**不要強制**依勝率產生特定比分。'
        ),
        'NPB': (
            'NPB 比分分布相對集中（σ={run_diff_std}），接近賽（≤2 分差）佔 {close_rate_pct}%；\n'
            '比分預測應反映此分布特徵，但同樣不得機械式套用。'
        ),
        'CPBL': (
            'CPBL 比分變異度介於 MLB 與 NPB 之間（σ={run_diff_std}），大比分率約 {blowout_rate_pct}%；\n'
            '比分預測應反映此分布特徵，但同樣不得機械式套用。'
        ),
    }

    guidance_template = league_guidance.get(league.upper(), '')
    guidance = guidance_template.format(
        run_diff_std=dist.get('run_diff_std', 0),
        blowout_rate_pct=int(dist.get('blowout_rate', 0) * 100),
        close_rate_pct=int(dist.get('close_game_rate', 0) * 100),
    )

    # 🆕 [2026-08-27] 總分均值引導：明確要求預測比分總和接近聯盟實際均值
    # 根因：LLM 傾向輸出低比分（CPBL 預測總分 6.57 vs 實際 7.83，低估 1.26 分）
    # 解法：把「單場總得分均值」轉成明確的比分總和引導，而非只講變異度
    total_mean = dist.get('total_score_mean', 0)
    team_mean = dist.get('team_score_mean', 0)
    total_guidance = (
        f"\n- **比分總和校準**：本聯盟單場總得分平均約 {total_mean} 分（單隊平均 {team_mean} 分）。"
        f"預測比分時，兩隊得分總和應落在 {total_mean} 分附近（合理區間 ±1 分），"
        f"避免系統性低估總分。"
    )

    section = f"""
===== {league.upper()} 比分分布特徵（最近 {DEFAULT_DAYS_BACK} 天實際結算）=====
{source_note}
- 球隊平均得分: {dist.get('team_score_mean', 0)} ± {dist.get('team_score_std', 0)}
- 單場總得分: {dist.get('total_score_mean', 0)} ± {dist.get('total_score_std', 0)}
- 分差分布: 平均 {dist.get('run_diff_mean', 0)} 分，標準差 {dist.get('run_diff_std', 0)}
- 大比分率 (≥6 分差): {int(dist.get('blowout_rate', 0) * 100)}%
- 接近賽率 (≤2 分差): {int(dist.get('close_game_rate', 0) * 100)}%

💡 分析指引：
{guidance}
{total_guidance}
"""
    return section


if __name__ == '__main__':
    # 本地測試
    for lg in ['MLB', 'NPB', 'CPBL', 'NBA']:
        d = compute_league_distribution(lg)
        print(f'{lg}: {d["sample_size"]} 場, fallback={d["is_fallback"]}')
        print(f'  σ_run_diff={d["run_diff_std"]}, blowout={d["blowout_rate"]}, close={d["close_game_rate"]}')
