CREATE TABLE IF NOT EXISTS user_sanctions (
  id BIGSERIAL PRIMARY KEY,
  target_user_id BIGINT NOT NULL REFERENCES users(id),
  moderator_user_id BIGINT NOT NULL REFERENCES users(id),
  type TEXT NOT NULL,
  reason TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS moderation_actions (
  id BIGSERIAL PRIMARY KEY,
  moderator_user_id BIGINT NOT NULL REFERENCES users(id),
  action_type TEXT NOT NULL,
  target_user_id BIGINT NULL REFERENCES users(id),
  object_type TEXT NOT NULL,
  object_id BIGINT NULL,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
