CREATE TABLE IF NOT EXISTS users (
  id BIGSERIAL PRIMARY KEY,
  telegram_id BIGINT UNIQUE NOT NULL,
  username TEXT,
  display_name TEXT,
  role TEXT NOT NULL CHECK (role IN ('client','editor','moderator')),
  language TEXT NOT NULL DEFAULT 'ru',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS deals (
  id BIGSERIAL PRIMARY KEY,
  client_id BIGINT NOT NULL REFERENCES users(id),
  editor_id BIGINT NOT NULL REFERENCES users(id),
  status TEXT NOT NULL,
  price_minor BIGINT NOT NULL DEFAULT 0,
  currency TEXT NOT NULL DEFAULT 'USD',
  commission_rate NUMERIC(5,4) NOT NULL DEFAULT 0.1000,
  included_revisions INT NOT NULL DEFAULT 2,
  revisions_used INT NOT NULL DEFAULT 0,
  terms_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
  auto_accept_at TIMESTAMPTZ NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS deal_events (
  id UUID PRIMARY KEY,
  deal_id BIGINT NOT NULL REFERENCES deals(id),
  actor_user_id BIGINT NOT NULL REFERENCES users(id),
  event_type TEXT NOT NULL,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS held_messages (
  id BIGSERIAL PRIMARY KEY,
  deal_id BIGINT NOT NULL REFERENCES deals(id),
  sender_user_id BIGINT NOT NULL REFERENCES users(id),
  original_text TEXT,
  normalized_text TEXT,
  flag_reason TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('held','approved','rejected')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
