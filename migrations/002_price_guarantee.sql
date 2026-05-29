-- Price Guarantee migration
-- Add tables for price guarantee tracking

-- 1. Update products table to add price guarantee fields
ALTER TABLE products ADD COLUMN original_price REAL;  -- 初始团购价格
ALTER TABLE products ADD COLUMN original_order_no TEXT;  -- 初始订单号
ALTER TABLE products ADD COLUMN original_channel TEXT;  -- 初始购买渠道（团购）
ALTER TABLE products ADD COLUMN current_guaranteed_price REAL;  -- 当前已保的最低价格
ALTER TABLE products ADD COLUMN pending_guarantee_price REAL;  -- 待保价（已提交未到账）
ALTER TABLE products ADD COLUMN store_activity TEXT;  -- 店铺活动
ALTER TABLE products ADD COLUMN group_activity TEXT;  -- 团购活动

-- 2. Price guarantee records table: 保价记录表
CREATE TABLE IF NOT EXISTS price_guarantee_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    low_price_channel TEXT NOT NULL,  -- 低价渠道
    low_price_order_no TEXT,  -- 低价订单号
    low_price REAL NOT NULL,  -- 发现的低价
    guarantee_amount REAL NOT NULL,  -- 保价金额 = 原价 - 低价
    status TEXT NOT NULL DEFAULT 'pending',  -- pending:待保价 / confirmed:已保价 / rejected:已拒绝
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- 提交保价时间
    confirmed_at TIMESTAMP,  -- 保价到账时间
    note TEXT,  -- 备注
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
);

-- 3. Create indexes
CREATE INDEX IF NOT EXISTS idx_price_guarantee_records_product_id ON price_guarantee_records(product_id);
CREATE INDEX IF NOT EXISTS idx_price_guarantee_records_status ON price_guarantee_records(status);
