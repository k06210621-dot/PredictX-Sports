#!/usr/bin/env bash
# run_ingest.sh — Ingest cron job entry point (改為長時間服務模式)
# 【2026-08-06】改為啟動 serve_cpbl.py，內含：
#   - Flask HTTP server on $PORT (預設 8080) 提供 /cpbl/sp API
#   - 背景 thread 每日 09:30 / 17:30 台北時間觸發 run_all_ingest.py
# 這樣 PredictX-Sports (gunicorn) 連 CPBL 被 HiNetCDN 阻擋時，
# 可以透過內部 routing 借用本容器的 egress IP 取得先發投手。
set -e
echo "=== PredictX Ingest + CPBL Proxy Start: $(date) ==="
cd "$(dirname "$0")"
exec python3 serve_cpbl.py
