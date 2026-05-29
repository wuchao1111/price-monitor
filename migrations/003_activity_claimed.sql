-- Add fields for tracking if store/group activity benefits were claimed
ALTER TABLE products ADD COLUMN store_activity_claimed INTEGER DEFAULT 0;  -- 0:未领取 / 1:已领取
ALTER TABLE products ADD COLUMN group_activity_claimed INTEGER DEFAULT 0;  -- 0:未领取 / 1:已领取
