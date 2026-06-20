-- migration_thesportsdb_cache.sql
-- TheSportsDB 查詢快取表（避免每場 AI 都重新查 API）

CREATE TABLE IF NOT EXISTS predictx.thesportsdb_cache (
    cache_key TEXT PRIMARY KEY,        -- 例: "h2h_innings:Uni-President 7-ELEVEn Lions:TSG Hawks:2026"
    cache_data JSONB NOT NULL,         -- 快取內容（逐局比分、球場等）
    cached_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL  -- 過期時間
);

CREATE INDEX IF NOT EXISTS idx_thesportsdb_cache_expires 
    ON predictx.thesportsdb_cache(expires_at);
