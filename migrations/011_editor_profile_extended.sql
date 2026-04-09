ALTER TABLE editor_profiles
  ADD COLUMN IF NOT EXISTS skill_level TEXT,
  ADD COLUMN IF NOT EXISTS experience_description TEXT;
