-- Migration: Add platform column for Android FCM support
-- March 2024 / PredictX Sports dual-platform push backend

-- Add platform column (ios/android) to device_tokens table
ALTER TABLE predictx.device_tokens 
ADD COLUMN IF NOT EXISTS platform VARCHAR(16) DEFAULT 'ios';

-- Re-index for platform-aware queries
CREATE INDEX IF NOT EXISTS idx_device_tokens_platform 
ON predictx.device_tokens(platform, tier) 
WHERE push_enabled = TRUE;