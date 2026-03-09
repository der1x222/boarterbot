CREATE TABLE IF NOT EXISTS editor_profiles (
  user_id BIGINT PRIMARY KEY REFERENCES users(id),
  name TEXT,
  skills TEXT,
  price_from_minor BIGINT,
  portfolio_url TEXT,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS client_profiles (
  user_id BIGINT PRIMARY KEY REFERENCES users(id),
  name TEXT,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);