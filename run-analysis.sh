#!/bin/bash
cd /Users/jero/sports-ingestion
python3 src/ai_analysis_engine.py 2>&1 | tee output.log
