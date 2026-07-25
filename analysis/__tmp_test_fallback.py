#!/usr/bin/env python3
"""實測 fallback LLM 是否可用：直接呼叫 _try_llm(fallback 端點)"""
import os, sys, json
sys.path.insert(0, '/Users/jero/PredictX Sports/analysis')

# 讓 railway run 注入的環境變數生效（FALLBACK_LLM_* 已由 railway run 提供）
print("=== Fallback LLM 實測 ===")
print(f"URL   = {os.environ.get('FALLBACK_LLM_URL')}")
print(f"MODEL = {os.environ.get('FALLBACK_LLM_MODEL')}")
print(f"KEY   = {os.environ.get('FALLBACK_LLM_API_KEY','')[:12]}...")

from analysis_engine import AnalysisEngine
eng = AnalysisEngine()

# 直接打 fallback 端點，模擬主模型失敗後的 fallback 呼叫
fake_prompt = '請只輸出 JSON: {"home_win_probability":0.5,"away_win_probability":0.5,"confidence":5,"summary":"test"}'
result = eng._try_llm(
    os.environ.get('FALLBACK_LLM_URL'),
    os.environ.get('FALLBACK_LLM_MODEL'),
    os.environ.get('FALLBACK_LLM_API_KEY'),
    fake_prompt
)
print(f"\n=== 結果 ===")
if result:
    print("✅ Fallback LLM 成功回傳可解析 JSON：")
    print(json.dumps(result, ensure_ascii=False, indent=2)[:500])
else:
    print("❌ Fallback LLM 失敗（回傳 None）")

eng.close()
