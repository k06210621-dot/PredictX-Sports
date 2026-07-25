#!/usr/bin/env python3
import sys, os, json
from pathlib import Path

# Load and set up environment variables from hermes .env file
env_path = str(Path.home() / '.hermes' / '.env')
if Path(env_path).exists():
    for line in open(env_path):
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            os.environ[k] = v

os.environ['PREDICTX_MODEL'] = 'cloud'

sys.path.insert(0, str(Path.home() / 'PredictX Sports/analysis'))
exec(open(str(Path.home() / '.hermes/scripts/auto_analyze_upcoming.py')).read())
