#!/usr/bin/env python3
"""列出 Nous Portal 可用模型（只印 model id，不印 key）。"""
import os, json
KEY = os.environ.get("NOUS_API_KEY", "")
URL = "https://inference-api.nousresearch.com/v1/models"
print(f"[INFO] api_key_present={'YES' if KEY else 'NO'}")
try:
    import requests
    r = requests.get(URL, headers={"Authorization": f"Bearer {KEY}"}, timeout=60)
    print(f"[INFO] HTTP {r.status_code}")
    if r.status_code != 200:
        print(r.text[:800])
        raise SystemExit(1)
    data = r.json()
    models = data.get("data", data if isinstance(data, list) else [])
    print(f"[INFO] total models returned: {len(models)}")
    # 優先印出含 free / step / flash / mini 等字樣（通常是免費層）
    for m in models:
        mid = m.get("id") or m.get("name") or m.get("model")
        if not mid:
            continue
        tag = ""
        if any(k in mid.lower() for k in ["free", "step", "flash", "mini", "nano", "lite"]):
            tag = "  <== 可能免費層"
        print(f"  {mid}{tag}")
except Exception as e:
    print(f"[ERR] {e}")
    raise SystemExit(1)
