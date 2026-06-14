#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/jero/PredictX Sports/analysis')
from analysis_engine import AnalysisEngine
import json

engine = AnalysisEngine()
game_id = '9ca5a0d1-14e4-473c-820a-fd2d10f6915d'
print("Starting analysis...")
result = engine.analyze_game(game_id)
if result:
    print("TYPE:", type(result))
    print("KEYS:", list(result.keys()))
    print("source_quality:", result.get('source_quality'))
    print("summary:", result.get('summary'))
    print("home_win_probability:", result.get('home_win_probability'))
else:
    print("Analysis returned None")
engine.close()