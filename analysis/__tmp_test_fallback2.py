#!/usr/bin/env python3
"""實測 fallback LLM：不初始化 AnalysisEngine（避免 DB 連線），直接呼叫 requests 打 fallback 端點"""
import os, sys, json, requests

URL = os.environ.get('FALLBACK_LLM_URL')
MODEL = os.environ.get('FALLBACK_LLM_MODEL')
KEY = os.environ.get('FALLBACK_LLM_API_KEY')

print("=== Fallback LLM 實測 (直接打 NVIDIA 端點) ===")
print(f"URL   = {URL}")
print(f"MODEL = {MODEL}")
print(f"KEY   = {KEY[:12]}...")

payload = {
    "model": MODEL,
    "messages": [
        {"role": "system", "content": "你只輸出 JSON，不要其他文字。"},
        {"role": "user", "content": '請只輸出 JSON: {"home_win_probability":0.5,"away_win_probability":0.5,"confidence":5,"summary":"test fallback"}'}
    ],
    "temperature": 0.5,
    "max_tokens": 11796,
    "stream": False
}
headers = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}

ok = False
for attempt in range(3):
    try:
        resp = requests.post(URL, json=payload, headers=headers, timeout=120)
        print(f"  attempt {attempt+1}: HTTP {resp.status_code}")
        if resp.status_code == 429:
            import time; time.sleep(10 * (2**attempt)); continue
        resp.raise_for_status()
        data = resp.json()
        if "choices" in data:
            c = data["choices"][0].get("message", {}).get("content", "").strip()
        elif "message" in data:
            c = data["message"].get("content", "").strip()
        else:
            c = ""
        if not c:
            print("  ⚠ 空回應"); continue
        parsed = json.loads(c)
        print("✅ Fallback LLM 成功回傳可解析 JSON：")
        print(json.dumps(parsed, ensure_ascii=False, indent=2)[:400])
        ok = True
        break
    except Exception as e:
        print(f"  attempt {attempt+1} 例外: {e}")
        if attempt < 2:
            import time; time.sleep(5 * (2**attempt)); continue
        break

print("\n=== 結論 ===")
print("✅ Fallback LLM 可用" if ok else "❌ Fallback LLM 仍失敗")
