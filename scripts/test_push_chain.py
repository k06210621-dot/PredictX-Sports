"""
Push 推播鏈手動測試腳本（DRY RUN）
模擬 push_cron.py 行為，不發送實際 APNs
"""
import sys
import os
sys.path.insert(0, '/Users/jero/PredictX Sports/analysis')

from datetime import datetime, timedelta
import psycopg2
import os

# 從環境變數取得 DB
database_url = os.environ.get('DATABASE_URL')
if not database_url:
    print("❌ DATABASE_URL 未設定")
    sys.exit(1)

conn = psycopg2.connect(database_url)
cur = conn.cursor()

today = datetime.now().strftime('%Y-%m-%d')
tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')

print(f"=" * 60)
print(f"PredictX Push 推播鏈手動測試")
print(f"執行時間: {datetime.now().isoformat()}")
print(f"查詢範圍: {today} ~ {tomorrow}")
print(f"=" * 60)

# === Step 1: 查詢高信心度賽事 ===
print("\n[Step 1] 查詢今天/明天 confidence > 8 的賽事")
print("-" * 60)
cur.execute("""
    SELECT g.game_id, g.match_date, 
           th.english_name as home_team, 
           ta.english_name as away_team,
           (ga.analysis_data->>'confidence')::numeric as confidence
    FROM predictx.games g
    JOIN predictx.game_analysis ga ON g.game_id = ga.game_id
    JOIN predictx.teams th ON g.home_team_id = th.team_id
    JOIN predictx.teams ta ON g.away_team_id = ta.team_id
    WHERE g.match_date IN (%s, %s)
      AND g.status = 'SCHEDULED'
      AND (ga.analysis_data->>'confidence')::numeric > 8
    ORDER BY g.match_date, confidence DESC
""", (today, tomorrow))

games = cur.fetchall()
if not games:
    print("  ⚠️  沒有任何賽事符合條件")
else:
    for g in games:
        print(f"  ✓ {g[1]} | {g[2]} vs {g[3]} | confidence={g[4]}")

# === Step 2: 查詢所有 confidence >= 8 的賽事（iOS App 顯示門檻）===
print("\n[Step 2] 查詢 confidence >= 8 的賽事（iOS App 顯示門檻）")
print("-" * 60)
cur.execute("""
    SELECT g.game_id, g.match_date, 
           th.english_name as home_team, 
           ta.english_name as away_team,
           (ga.analysis_data->>'confidence')::numeric as confidence
    FROM predictx.games g
    JOIN predictx.game_analysis ga ON g.game_id = ga.game_id
    JOIN predictx.teams th ON g.home_team_id = th.team_id
    JOIN predictx.teams ta ON g.away_team_id = ta.team_id
    WHERE g.match_date IN (%s, %s)
      AND g.status = 'SCHEDULED'
      AND (ga.analysis_data->>'confidence')::numeric >= 8
    ORDER BY g.match_date, confidence DESC
""", (today, tomorrow))

games_strict = cur.fetchall()
if not games_strict:
    print("  ⚠️  沒有任何賽事 confidence >= 8")
else:
    for g in games_strict:
        print(f"  ✓ {g[1]} | {g[2]} vs {g[3]} | confidence={g[4]}")

# === Step 3: 查詢 Premium 啟用推播的用戶 ===
print("\n[Step 3] 查詢 Premium 啟用推播的用戶")
print("-" * 60)
cur.execute("""
    SELECT device_token, updated_at
    FROM predictx.device_tokens 
    WHERE tier = 'premium' AND push_enabled = true
    ORDER BY updated_at DESC
""")

tokens = cur.fetchall()
if not tokens:
    print("  ⚠️  沒有任何 Premium 用戶啟用推播")
else:
    for t in tokens:
        token_preview = t[0][:16] + "..."
        print(f"  ✓ {token_preview} | updated: {t[1]}")

# === Step 4: 模擬 push_cron 推送動作 ===
print("\n[Step 4] 模擬 push_cron.py 推送")
print("-" * 60)
if not games:
    print("  ⚠️  跳過：沒有信心度 > 8 的賽事")
elif not tokens:
    print("  ⚠️  跳過：沒有 Premium 用戶啟用推播")
else:
    print(f"  即將推送 {len(games)} 場賽事給 {len(tokens)} 個用戶")
    for g in games:
        print(f"    → {g[2]} vs {g[3]} (confidence={g[4]})")

# === Step 5: 診斷 ===
print("\n[Step 5] 診斷結果")
print("-" * 60)
issues = []
if games_strict and not games:
    issues.append("⚠️  iOS App 顯示信心度 ≥ 8，但後端 push_cron 用 > 8，會漏推 confidence = 8 的賽事")
if not tokens:
    issues.append("⚠️  沒有 Premium 用戶啟用推播")
if not games and not games_strict:
    issues.append("ℹ️  今天/明天完全沒有高信心度賽事（可能是因為 6/30 的比賽還沒跑分析）")

if not issues:
    print("  ✅ 推播鏈正常")
else:
    for i in issues:
        print(f"  {i}")

conn.close()