ALTER TABLE editor_profiles
  ADD COLUMN IF NOT EXISTS avg_price_minor BIGINT;

CREATE TABLE IF NOT EXISTS order_reviews (
  id BIGSERIAL PRIMARY KEY,
  order_id BIGINT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  reviewer_user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  reviewee_user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  rating SMALLINT NOT NULL CHECK (rating BETWEEN 1 AND 5),
  comment TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (order_id, reviewer_user_id, reviewee_user_id)
);

CREATE INDEX IF NOT EXISTS idx_order_reviews_reviewee_created_at
  ON order_reviews(reviewee_user_id, created_at DESC);
