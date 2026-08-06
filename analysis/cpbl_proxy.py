#!/usr/bin/env python3
"""
cpbl_proxy.py — 獨立 CPBL SP 代理服務（純 Flask app）

背景：
- PredictX-Sports 容器 (gunicorn) 連出 CPBL.com.tw 會被 HiNetCDN 擋（404）
- 用獨立容器 / 不同 egress IP 借出 CPBL 抓取能力

部署方式：
- Railway 獨立 service `PredictX-CPBL-Proxy`
- Start Command: python cpbl_proxy.py
- 對 CPBL SP 的內部路由：
  PredictX-Sports → internal DNS: predictx-cpbl-proxy.railway.internal/cpbl/sp
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
    """簡單 header-based 認證"""
    if not INTERNAL_SECRET:
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
    port = int(os.environ.get("PORT", "8080"))
    logger.info(f"Starting CPBL proxy on 0.0.0.0:{port}")
    # 使用 gunicorn 應是生產環境，但作為 fallback 保留 dev server
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
