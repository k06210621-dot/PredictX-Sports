#!/usr/bin/env bash
# run_ingest.sh — Ingest cron job entry point
# 每日 02:00 Asia/Taipei 執行
set -e
echo "=== PredictX Ingest Cron Start: $(date) ==="
cd "$(dirname "$0")"
python3 run_all_ingest.py
EXIT_CODE=$?
echo "=== PredictX Ingest Cron End: exit_code=$EXIT_CODE ==="
exit $EXIT_CODE