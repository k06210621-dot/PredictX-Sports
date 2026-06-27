-- Push Notification device_tokens 表（2026-06-27 新增）
CREATE TABLE IF NOT EXISTS predictx.device_tokens (
    device_token TEXT PRIMARY KEY,
    tier TEXT NOT NULL DEFAULT 'free',
    push_enabled BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_device_tokens_tier_enabled
ON predictx.device_tokens(tier, push_enabled)
WHERE push_enabled = true;
