#!/usr/bin/env python3
"""
serve_cpbl.py — CPBL SP 代理服務（PredictX-All-Ingest 容器內運行的 Flask app）

功能：
1. 啟動 Flask 在 $PORT (Railway 預設)
2. GET /cpbl/sp?date=YYYY-MM-DD → 透過此容器（cron egress IP）抓 CPBL 先發投手
3. PredictX-Sports web 容器內部呼叫此服務，避免 gunicorn worker 被 HiNetCDN 擋

環境變數：
- PORT (Railway 自動設)
- INTERNAL_SECRET (PredictX-Sports 與 All-Ingest 共享)
- DATABASE_URL, NOUS_API_KEY, OLLAMA_API_KEY (CPBLDataFetcher 會需要)
"""
import os
import sys
import logging
import threading
import time as _t
import subprocess
from datetime import datetime, timezone, timedelta

from flask import Flask, jsonify, request, abort

logger = logging.getLogger("serve_cpbl")
if not logger.handlers:
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(logging.Formatter('[serve_cpbl] %(message)s'))
    logger.addHandler(h)
    logger.setLevel(logging.INFO)
    logger.propagate = False

INTERNAL_SECRET = os.environ.get("INTERNAL_SECRET", "")
TAIPEI_TZ = timezone(timedelta(hours=8))


def run_ingest_thread():
    """背景 thread — 每天 09:30 / 17:30 台北時間觸發 run_all_ingest.py"""
    logger.info("Ingest cron thread started")
    last_run = {"hhmm": None}
    while True:
        try:
            now_taipei = datetime.now(TAIPEI_TZ)
            hour = now_taipei.hour
            minute = now_taipei.minute
            is_cron_time = (
                (hour == 9 and 30 <= minute) or
                (hour == 17 and 30 <= minute)
            )
            if is_cron_time and last_run["hhmm"] != f"{hour:02d}:{minute:02d}":
                last_run["hhmm"] = f"{hour:02d}:{minute:02d}"
                logger.info(f"Triggering run_all_ingest at {hour:02d}:{minute:02d}")
                try:
                    result = subprocess.run(
                        ["python3", "run_all_ingest.py"],
                        capture_output=True, text=True, timeout=600,
                    )
                    logger.info(
                        f"run_all_ingest done: code={result.returncode}, "
                        f"stdout_tail={result.stdout[-200:]}"
                    )
                except Exception as e:
                    logger.error(f"run_all_ingest failed: {e}")
            _t.sleep(60)
        except Exception as e:
            logger.error(f"Ingest loop error: {e}")
            _t.sleep(60)


app = Flask(__name__)


def _check_internal_secret(req):
    """簡單 header-based 認證 — INTERNAL_SECRET 環境變數共享"""
    if not INTERNAL_SECRET:
        # 沒設就不擋（生產環境一定要設）
        logger.warning("INTERNAL_SECRET not set, allowing all requests")
        return True
    secret = req.headers.get("X-Internal-Secret", "")
    return secret == INTERNAL_SECRET


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "cpbl-proxy"}), 200


@app.route("/cpbl/sp", methods=["GET"])
def cpbl_sp():
    """GET /cpbl/sp?date=YYYY-MM-DD
    回傳: {"status": "ok", "date": "...", "starters": {...}, "count": N}"""
    if not _check_internal_secret(request):
        abort(401, description="Unauthorized: invalid X-Internal-Secret")

    date_str = request.args.get("date")
    if not date_str:
        date_str = datetime.now(TAIPEI_TZ).strftime("%Y-%m-%d")

    logger.info(f"GET /cpbl/sp?date={date_str}")
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from cpbl_data_fetcher import CPBLDataFetcher
        fetcher = CPBLDataFetcher()
        starters = fetcher.get_today_starting_pitchers(date_str)
        fetcher.close()
        return jsonify({
            "status": "ok",
            "date": date_str,
            "starters": starters,
            "count": len(starters) if starters else 0,
        }), 200
    except Exception as e:
        logger.error(f"CPBL SP fetch error: {e}")
        import traceback
        return jsonify({
            "status": "error",
            "error": str(e),
            "trace": traceback.format_exc()[:500],
        }), 500


@app.route("/", methods=["GET"])
def root():
    return jsonify({
        "service": "PredictX-CPBL-Proxy",
        "endpoints": ["/health", "/cpbl/sp?date=YYYY-MM-DD"],
    }), 200


if __name__ == "__main__":
    # 啟動背景 cron thread（取代原本 Railway cron schedule）
    cron_t = threading.Thread(target=run_ingest_thread, daemon=True)
    cron_t.start()

    # 啟動 Flask
    port = int(os.environ.get("PORT", "8080"))
    logger.info(f"Starting CPBL proxy on 0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
