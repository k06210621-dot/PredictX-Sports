#!/usr/bin/env python3
"""回測腳本：分析 2026-07-10 WNBA 鳳凰城水星 vs 印第安納狂熱的預測邏輯偏差"""

import os, json
from analysis_engine import AnalysisEngine


def run_backtest_7_10():
    print("="*80)
    engine = AnalysisEngine()
    
    # 查詢所有 WNBA teams，找出正確的 team_id
    engines.execute("SELECT id as team_id, english_name FROM predictx.teams WHERE league='WNBA' ORDER BY position")
    