#!/usr/bin/env python3
"""還原 2026-06-14 NPB 6 場的原始 analysis_data（從備份檔）"""
import os, sys, gzip, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import psycopg2
from psycopg2.extras import RealDictCursor

BACKUP = 'backup/npb_0614_analysis_backup_20260711_093213.json.gz'

def main():
    url = os.getenv('DATABASE_URL', '')
    if 'postgres.railway.internal' in url:
        url = url.replace('postgres.railway.internal:5432', 'thomas.proxy.rlwy.net:49887')
    conn = psycopg2.connect(url, cursor_factory=RealDictCursor)
    cur = conn.cursor()

    with gzip.open(BACKUP, 'rt', encoding='utf-8') as f:
        data = json.load(f)

    restored = 0
    for r in data:
        gid = r['game_id']
        ad = r['analysis_data']
        if ad is None:
            print(f"  skip {gid[:8]} (no analysis_data in backup)")
            continue
        cur.execute(
            """UPDATE predictx.game_analysis
               SET analysis_data = %s, updated_at = CURRENT_TIMESTAMP
               WHERE game_id = %s::uuid""",
            (json.dumps(ad), gid)
        )
        restored += 1
        print(f"  ✓ 還原 {gid[:8]}... conf={ad.get('confidence')}")

    conn.commit()
    cur.close()
    conn.close()
    print(f"還原完成: {restored} 場")

if __name__ == '__main__':
    main()
