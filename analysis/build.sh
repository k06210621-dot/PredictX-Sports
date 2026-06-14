#!/usr/bin/env bash
# Railway 部署後自動建立資料庫 schema 並 seed 種子資料
# 只在 predictx.games 為空時才 seed（冪等設計）

set -e

echo "=== Checking if DB needs initialization ==="

# 測試連線 + 檢查表是否存在
TABLE_EXISTS=$(psql "$DATABASE_URL" -tAc "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='predictx' AND table_name='games');" 2>&1)

if [ "$TABLE_EXISTS" = "t" ]; then
    echo "✅ predictx.games already exists, skip initialization."
    exit 0
fi

echo "=== Applying schema ==="
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f /app/analysis/db/schema.sql

echo "=== Seeding data ==="
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f /app/analysis/db/seed_core.sql

# 驗證
GAME_COUNT=$(psql "$DATABASE_URL" -tAc "SELECT COUNT(*) FROM predictx.games;" 2>&1)
echo "✅ seed done. predictx.games has $GAME_COUNT rows."
