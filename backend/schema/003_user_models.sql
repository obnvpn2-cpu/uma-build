-- 003_user_models.sql
-- Stores user-saved models with snapshot metrics for comparison.

CREATE TABLE IF NOT EXISTS user_models (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id) NOT NULL,
  model_id TEXT NOT NULL,
  name TEXT NOT NULL DEFAULT '無題のモデル',
  roi DOUBLE PRECISION,
  hit_rate DOUBLE PRECISION,
  reliability_stars INTEGER,
  n_features INTEGER,
  feature_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
  data_years INTEGER DEFAULT 2,
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(user_id, model_id)
);

CREATE INDEX idx_user_models_user_id ON user_models(user_id);

ALTER TABLE user_models ENABLE ROW LEVEL SECURITY;

-- Users can read and delete their own models
CREATE POLICY "Users can read own models"
  ON user_models FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own models"
  ON user_models FOR DELETE
  USING (auth.uid() = user_id);

-- service_role can manage all (used by backend)
CREATE POLICY "Service role full access"
  ON user_models FOR ALL
  USING (auth.role() = 'service_role');
