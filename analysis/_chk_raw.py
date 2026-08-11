#!/usr/bin/env python3
"""純 psycopg2 查 predictx.game_analysis 原始 analysis_data JSONB 的 actual_result。"""
import os, sys, json
import psycopg2
from psycopg2.extras import RealDictCursor

database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)
conn = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
cur = conn.cursor()

ids = [
    '60829a5a-0d9a-4972-9e17-d09234d25bff',
    '062bb239-d031-42ac-8637-61cbb84c115d',
    '1ef2b127-8f05-45c8-830c-e6b970fb4100',
    '66860d4b-6861-48a3-a522-d5f666096eac',
    'ac15fdfc-c460-4e9e-83d1-6ccf07763345',
    'acfba0fe-4e27-4090-8999-ad5c198cb260',
    'ed77c7af-d8ef-4adb-8e6e-325284e704af',
    'f9fbdc61-ac31-4b7c-966e-d229f63af1a7',
    '35b59529-dd32-4db1-866f-76aed97e8106',
    '97c8b8d9-4db0-4253-9378-18af7c888eef',
]
for gid in ids:
    cur.execute("""
        SELECT g.home_team_score, g.away_team_score, g.status,
               (ga.analysis_data ? 'actual_result') AS has_actual_result,
               ga.analysis_data->'actual_result' AS actual_result_raw
        FROM predictx.games g
        JOIN predictx.game_analysis ga ON g.game_id = ga.game_id
        WHERE g.game_id = %s::uuid
    """, (gid,))
    row = cur.fetchone()
    if not row:
        print(f"{gid[:8]}: NO ROW in game_analysis")
        continue
    hs, as_, st, has_ar, ar_raw = row
    print(f"{gid[:8]}: score={hs}-{as_} status={st} has_actual_result={has_ar}")
    if ar_raw:
        print(f"    actual_result={ar_raw}")
cur.close()
conn.close()
