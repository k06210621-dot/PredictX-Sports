#!/usr/bin/env python3
"""臨時測試：驗證當前 CLOUD_LLM_PROVIDER 是否真能回傳且可被 JSON parser 解析。
不碰資料庫，只讀 Railway 注入的環境變數並打一次 LLM 請求。"""
import os, json, re, sys, time

# --- 複製 analysis_engine.py 的 provider 分支邏輯 ---
PROVIDER = os.environ.get("CLOUD_LLM_PROVIDER", "ollama")
if PROVIDER == "openrouter":
    URL = "https://openrouter.ai/api/v1/chat/completions"
    MODEL = os.environ.get("CLOUD_LLM_MODEL", "meta-llama/llama-3.3-70b-instruct:free")
    KEY = os.environ.get("OPENROUTER_API_KEY", "")
elif PROVIDER == "groq":
    URL = "https://api.groq.com/openai/v1/chat/completions"
    MODEL = os.environ.get("CLOUD_LLM_MODEL", "llama-3.3-70b-versatile")
    KEY = os.environ.get("GROQ_API_KEY", "")
elif PROVIDER == "nous":
    URL = "https://inference-api.nousresearch.com/v1/chat/completions"
    MODEL = os.environ.get("CLOUD_LLM_MODEL", "stepfun/step-3.7-flash:free")
    KEY = os.environ.get("NOUS_API_KEY", "")
elif PROVIDER == "ollama":
    URL = "https://api.ollama.com/api/chat"
    MODEL = os.environ.get("CLOUD_LLM_MODEL", "qwen3-coder-next")
    KEY = os.environ.get("OLLAMA_API_KEY", "")
else:
    URL = "https://integrate.api.nvidia.com/v1/chat/completions"
    MODEL = os.environ.get("CLOUD_LLM_MODEL", "deepseek-ai/deepseek-v4-flash")
    KEY = os.environ.get("NVIDIA_API_KEY", "")

print(f"[TEST] provider={PROVIDER} model={MODEL} url={URL}")
print(f"[TEST] api_key_present={'YES' if KEY else 'NO'}")

# 模擬分析服務送出的 system 指令（與 analysis_engine.py:1791 一致）
SYSTEM = ("你是一位頂尖的運動賽事分析師，擁有 20 年球評經驗。請根據提供的數據進行深度分析，"
          "並嚴格按照要求的 JSON 格式輸出。只輸出 JSON，不要有任何其他文字。")
# 極簡 user prompt，要求扁平 JSON（避免 reasoning 截斷型失敗）
USER = ('用 JSON 回傳一支 NBA 比賽的預測，格式嚴格如下，不要任何解釋、不要 reasoning 欄位：\n'
        '{"home_win_probability":0.55,"away_win_probability":0.45,"predicted_score":"110-105",'
        '"confidence":7,"key_factors":["主場優勢"],"radar_chart":{"home_team":[7,6,5,6,7,6],"away_team":[5,6,7,5,6,5]}}\n'
        '只輸出這個 JSON。')

payload = {
    "model": MODEL,
    "messages": [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": USER},
    ],
    "temperature": 0.5,
    "max_tokens": 9830,
    "stream": False,
}
headers = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}

try:
    import requests
    t0 = time.time()
    r = requests.post(URL, json=payload, headers=headers, timeout=120)
    dt = time.time() - t0
    print(f"[TEST] HTTP {r.status_code} in {dt:.1f}s")
    if r.status_code != 200:
        print("[TEST] NON-200 BODY:", r.text[:500])
        sys.exit(1)
    data = r.json()
    if "choices" in data:
        content = data["choices"][0].get("message", {}).get("content", "").strip()
    elif "message" in data:
        content = data["message"].get("content", "").strip()
    else:
        content = ""
    print(f"[TEST] raw content length={len(content)}")
    print(f"[TEST] raw head: {content[:300]!r}")
except Exception as e:
    print(f"[TEST] REQUEST FAILED: {e}")
    sys.exit(1)

# --- 複製 _parse_json_response 的核心邏輯 ---
def parse(text):
    try:
        return json.loads(text), "direct"
    except json.JSONDecodeError:
        start = text.find('{')
        if start < 0:
            return None, "no-brace"
        depth = 0
        end = start
        for i, c in enumerate(text[start:], start=start):
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        try:
            return json.loads(text[start:end]), f"extracted(end={end})"
        except json.JSONDecodeError:
            return None, "unparseable"

result, how = parse(content)
if result is None:
    print(f"[TEST] ❌ PARSE FAILED ({how}) — 模型回傳無法被 parser 解析")
    sys.exit(2)
else:
    print(f"[TEST] ✅ PARSE OK via {how}")
    print(f"[TEST] keys={list(result.keys())}")
    sys.exit(0)
