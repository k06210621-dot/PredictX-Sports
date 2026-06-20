#!/usr/bin/env bash
# run_settlement.sh — Settlement cron job entry point
# 每日 22:30 Asia/Taipei 執行
set -e
echo "=== PredictX Settlement Cron Start: $(date) ==="
cd "$(dirname "$0")"
python3 -c "
import os
import sys
sys.path.insert(0, '.')
from settlement_engine import SettlementEngine
engine = SettlementEngine()
count = engine.settle_games()
count2 = engine._settle_postponed_games()
print(f'Settled {count} FINAL games, marked {count2} POSTPONED games')
"
EXIT_CODE=$?
echo "=== PredictX Settlement Cron End: exit_code=$EXIT_CODE ==="
exit $EXIT_CODE