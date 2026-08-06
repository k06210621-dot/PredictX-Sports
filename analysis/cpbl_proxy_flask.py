#!/usr/bin/env python3
"""
cpbl_proxy_flask.py — Flask app for CPBL SP proxy（搭配 gunicorn 使用）

部署：在 Railway 用 gunicorn 啟動 cpbl_proxy_flask:app
"""
import os
import sys
import logging

from flask import Flask, jsonify, request, abort

logger = logging.getLogger("cpbl_proxy")
if not logger.handlers:
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(logging.Formatter('[cpbl_proxy] %(message)s'))
    logger.addHandler(h)
    logger.setLevel(logging.INFO)
    logger.propagate = False

INTERNAL_SECRET = os.environ.get("INTERNAL_SECRET", "")

app = Flask(__name__)


def _check_internal_secret(req):
    if not INTERNAL_SECRET:
        logger.warning("INTERNAL_SECRET not set")
        return True
    return req.headers.get("X-Internal-Secret", "") == INTERNAL_SECRET


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "cpbl-proxy"}), 200


@app.route("/cpbl/sp", methods=["GET"])
def cpbl_sp():
    if not _check_internal_secret(request):
        abort(401)
    date_str = request.args.get("date")
    if not date_str:
        from datetime import datetime, timezone, timedelta
        date_str = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")
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
        return jsonify({"status": "error", "error": str(e),
                        "trace": traceback.format_exc()[:500]}), 500


@app.route("/", methods=["GET"])
def root():
    return jsonify({
        "service": "PredictX-CPBL-Proxy",
        "endpoints": ["/health", "/cpbl/sp?date=YYYY-MM-DD"],
    }), 200
