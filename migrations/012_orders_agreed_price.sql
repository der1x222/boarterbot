ALTER TABLE orders
  ADD COLUMN IF NOT EXISTS agreed_price_minor BIGINT;
