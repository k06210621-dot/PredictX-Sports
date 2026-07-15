#!/usr/bin/env python3
"""Execute PredictX AI analysis for upcoming matches."""
import sys, os, json

# Load environment variables from .env file
os.environ['PREDICTX_MODEL'] = 'cloud'

sys.path.insert(0, '/Users/jero/PredictX Sports/analysis')

# Execute the upstream script content (already handles env loading)
script_path = '/Users/jero/.hermes/scripts/auto_analyze_upcoming.py'
with open(script_path) as f: exec(f.read())
