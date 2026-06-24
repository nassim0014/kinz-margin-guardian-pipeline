-- ============================================================
-- Kinz Margin Guardian Pipeline — Database Schema
-- ============================================================

-- Products with COGS
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    category VARCHAR(100),
    cogs_tnd NUMERIC(10, 3) NOT NULL,
    b2b_price_tnd NUMERIC(10, 3),
    b2c_price_tnd NUMERIC(10, 3),
    alert_threshold_pct NUMERIC(5, 2) DEFAULT 40.00,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Daily competitor prices (simulated ingestion)
CREATE TABLE IF NOT EXISTS daily_prices (
    id SERIAL PRIMARY KEY,
    product_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
    price_date DATE NOT NULL,
    competitor_price_tnd NUMERIC(10, 3) NOT NULL,
    source VARCHAR(50) DEFAULT 'simulated',
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(product_id, price_date)
);

-- Margin history (calculated by the DAG)
CREATE TABLE IF NOT EXISTS margin_history (
    id SERIAL PRIMARY KEY,
    product_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
    calc_date DATE NOT NULL,
    b2c_margin_pct NUMERIC(5, 2),
    b2b_margin_pct NUMERIC(5, 2),
    b2c_price_tnd NUMERIC(10, 3),
    b2b_price_tnd NUMERIC(10, 3),
    cogs_tnd NUMERIC(10, 3),
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(product_id, calc_date)
);

-- Alert log
CREATE TABLE IF NOT EXISTS alerts (
    id SERIAL PRIMARY KEY,
    product_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
    alert_date TIMESTAMP DEFAULT NOW(),
    alert_type VARCHAR(20),
    margin_pct NUMERIC(5, 2),
    threshold_pct NUMERIC(5, 2),
    message TEXT,
    notified BOOLEAN DEFAULT FALSE
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_daily_prices_product_date ON daily_prices(product_id, price_date);
CREATE INDEX IF NOT EXISTS idx_margin_history_product_date ON margin_history(product_id, calc_date);
CREATE INDEX IF NOT EXISTS idx_alerts_product ON alerts(product_id);
CREATE INDEX IF NOT EXISTS idx_alerts_date ON alerts(alert_date);
