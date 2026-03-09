ALTER TABLE editor_profiles
  ADD COLUMN IF NOT EXISTS verification_status TEXT NOT NULL DEFAULT 'not_submitted'
  CHECK (verification_status IN ('not_submitted','pending','verified','rejected'));

ALTER TABLE editor_profiles
  ADD COLUMN IF NOT EXISTS verification_note TEXT;

ALTER TABLE editor_profiles
  ADD COLUMN IF NOT EXISTS test_submission TEXT;