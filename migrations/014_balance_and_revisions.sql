ALTER TABLE users
  ADD COLUMN IF NOT EXISTS virtual_balance_minor BIGINT DEFAULT 0,
  ADD COLUMN IF NOT EXISTS total_earned_minor BIGINT DEFAULT 0,
  ADD COLUMN IF NOT EXISTS verified_for_withdrawal BOOLEAN DEFAULT FALSE;

ALTER TABLE orders
  ADD COLUMN IF NOT EXISTS revision_requested BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS revision_price_minor BIGINT,
  ADD COLUMN IF NOT EXISTS revision_status TEXT DEFAULT 'none', -- none, requested, accepted, payment_pending, paid, completed
  ADD COLUMN IF NOT EXISTS revision_description TEXT,
  ADD COLUMN IF NOT EXISTS revision_payment_link TEXT,
  ADD COLUMN IF NOT EXISTS revision_stripe_session_id TEXT,
  ADD COLUMN IF NOT EXISTS final_video_sent BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS client_confirmed_completion BOOLEAN DEFAULT FALSE;

CREATE TABLE IF NOT EXISTS balance_transactions (
  id SERIAL PRIMARY KEY,
  user_id BIGINT NOT NULL REFERENCES users(id),
  amount_minor BIGINT NOT NULL,
  transaction_type TEXT NOT NULL, -- earned, withdrawn, refunded
  order_id BIGINT REFERENCES orders(id),
  description TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_balance_transactions_user_id ON balance_transactions(user_id);
CREATE INDEX IF NOT EXISTS idx_balance_transactions_created_at ON balance_transactions(created_at);