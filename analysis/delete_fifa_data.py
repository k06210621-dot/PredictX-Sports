"""
FIFA 資料清除腳本
於 2026-06-17 一次性執行，清空 predictx schema 中所有 FIFA 相關資料
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import psycopg2
from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    print("ERROR: DATABASE_URL 環境變數未設定")
    sys.exit(1)

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

try:
    print("🗑️  開始清除 FIFA 資料...")

    # 1. 清除 FIFA 分析資料
    cur.execute("""
        DELETE FROM predictx.game_analysis
        WHERE game_id IN (
            SELECT id FROM predictx.games WHERE league = 'FIFA'
        )
    """)
    print(f"   ✅ 清除 game_analysis (FIFA): {cur.rowcount} 筆")

    # 2. 清除 FIFA 賽事
    cur.execute("DELETE FROM predictx.games WHERE league = 'FIFA'")
    print(f"   ✅ 清除 games (FIFA): {cur.rowcount} 筆")

    # 3. 清除 FIFA 球隊
    cur.execute("DELETE FROM predictx.teams WHERE league = 'FIFA'")
    print(f"   ✅ 清除 teams (FIFA): {cur.rowcount} 筆")

    conn.commit()
    print("✅ FIFA 資料清除完成")

except Exception as e:
    conn.rollback()
    print(f"❌ 清除失敗: {e}")
    raise
finally:
    cur.close()
    conn.close()
