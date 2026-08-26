#!/usr/bin/env python3
"""一次性重結算「之前標記為 POSTPONED 但實際後來打完」的賽事"""
import os
import sys

# 把 Railway 內部 DB URL 改成對外可解析的 proxy URL
db_url = os.environ.get('DATABASE_URL', '')
if 'postgres.railway.internal' in db_url:
    os.environ['DATABASE_URL'] = db_url.replace(
        'postgres.railway.internal:5432',
        'thomas.proxy.rlwy.net:49887'
    )

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import warnings
warnings.filterwarnings('ignore')

from settlement_engine import SettlementEngine


def main():
    engine = SettlementEngine()
    print("=== 執行 settle_games() 修正後版本 ===")
    print("    會自動找「之前標記為 POSTPONED 但現在 FINAL」的賽事並重結算")
    settled = engine.settle_games()
    print(f"\n總共結算: {settled} 場")
    engine.close()


if __name__ == '__main__':
    main()
