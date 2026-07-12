#!/usr/bin/env python3
"""隔離測試 minimax-m3 單次呼叫（先修 URL 再建 engine）"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
url = os.getenv('DATABASE_URL', '')
if 'postgres.railway.internal' in url:
    os.environ['DATABASE_URL'] = url.replace('postgres.railway.internal:5432', 'thomas.proxy.rlwy.net:49887')
os.environ['CLOUD_LLM_PROVIDER'] = 'nvidia'
os.environ['CLOUD_LLM_MODEL'] = 'minimaxai/minimax-m3'

from analysis_engine import AnalysisEngine
eng = AnalysisEngine()
res = eng._try_llm(
    'https://integrate.api.nvidia.com/v1/chat/completions',
    'minimaxai/minimax-m3',
    os.getenv('NVIDIA_API_KEY', ''),
    '請嚴格只輸出 JSON: {"home_win_probability":0.5,"away_win_probability":0.5,"confidence":5}'
)
print('RESULT TYPE:', type(res))
print('RESULT:', str(res)[:500])
eng.close()
