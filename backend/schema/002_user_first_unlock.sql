-- First-unlock tracking table
-- Records which users have consumed their one-time full-results reveal.

CREATE TABLE IF NOT EXISTS user_first_unlock (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id) NOT NULL UNIQUE,
  model_id TEXT,
  used_at TIMESTAMPTZ DEFAULT now()
);

-- Index for fast lookup by user_id (UNIQUE already creates one, but explicit for clarity)
CREATE INDEX IF NOT EXISTS idx_user_first_unlock_user_id ON user_first_unlock(user_id);

-- RLS: users can read their own record; only service_role can insert
ALTER TABLE user_first_unlock ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own first_unlock"
  ON user_first_unlock FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Service role can insert first_unlock"
  ON user_first_unlock FOR INSERT
  WITH CHECK (true);
