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
  ADD COLUMN IF NOT EXISTS client_confirmed_completion BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS reserved_amount_minor BIGINT DEFAULT 0,
  ADD COLUMN IF NOT EXISTS reserved_revision_amount_minor BIGINT DEFAULT 0;

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

CREATE TABLE IF NOT EXISTS withdrawal_requests (
  id SERIAL PRIMARY KEY,
  user_id BIGINT NOT NULL REFERENCES users(id),
  amount_minor BIGINT NOT NULL, -- amount to withdraw
  fee_minor BIGINT NOT NULL, -- 10% fee
  net_amount_minor BIGINT NOT NULL, -- amount - fee
  payment_details TEXT NOT NULL, -- JSON with payment info
  status TEXT DEFAULT 'pending', -- pending, completed, rejected
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  processed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_withdrawal_requests_user_id ON withdrawal_requests(user_id);
CREATE INDEX IF NOT EXISTS idx_withdrawal_requests_status ON withdrawal_requests(status);