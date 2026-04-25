-- Learn job state + daily rate limit tables for Cloud Run migration.
-- Externalizes the in-memory _jobs dict and _daily_attempts counter so
-- that multi-instance deployments share state via Supabase Postgres.

-- ============================================================
-- learn_jobs: persisted async training job records
-- ============================================================
CREATE TABLE IF NOT EXISTS learn_jobs (
  job_id TEXT PRIMARY KEY,
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  session_id TEXT,
  status TEXT NOT NULL CHECK (status IN ('pending', 'running', 'completed', 'failed')),
  result JSONB,
  error TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  expires_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '24 hours'),
  CONSTRAINT learn_jobs_owner_chk CHECK (user_id IS NOT NULL OR session_id IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_learn_jobs_user ON learn_jobs(user_id) WHERE user_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_learn_jobs_session ON learn_jobs(session_id) WHERE session_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_learn_jobs_expires ON learn_jobs(expires_at);

-- Auto-update updated_at on row UPDATE (reuses function from 001_subscriptions.sql)
DROP TRIGGER IF EXISTS update_learn_jobs_updated_at ON learn_jobs;
CREATE TRIGGER update_learn_jobs_updated_at
  BEFORE UPDATE ON learn_jobs
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

-- RLS: authenticated users read their own; anonymous jobs cannot be
-- read directly (the FastAPI layer authorizes via session_id with the
-- service_role key).
ALTER TABLE learn_jobs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "users_read_own_jobs" ON learn_jobs;
CREATE POLICY "users_read_own_jobs"
  ON learn_jobs FOR SELECT
  USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "service_role_manages_jobs" ON learn_jobs;
CREATE POLICY "service_role_manages_jobs"
  ON learn_jobs FOR ALL
  USING (auth.role() = 'service_role');

-- ============================================================
-- daily_attempts: per-user daily rate limit counter (UTC date)
-- ============================================================
CREATE TABLE IF NOT EXISTS daily_attempts (
  rate_key TEXT NOT NULL,
  attempt_date DATE NOT NULL,
  count INTEGER NOT NULL DEFAULT 0,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (rate_key, attempt_date)
);

ALTER TABLE daily_attempts ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "service_role_manages_attempts" ON daily_attempts;
CREATE POLICY "service_role_manages_attempts"
  ON daily_attempts FOR ALL
  USING (auth.role() = 'service_role');

-- ============================================================
-- increment_daily_attempt: atomic check-and-increment
--   Returns (allowed, current_count).
--   - Inserts a new row at count=1 on first call of the UTC day.
--   - Increments existing row only if count < p_max.
--   - Returns allowed=false without side effects when the limit is hit.
-- ============================================================
CREATE OR REPLACE FUNCTION increment_daily_attempt(
  p_rate_key TEXT,
  p_max INTEGER
) RETURNS TABLE(allowed BOOLEAN, current_count INTEGER)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_today DATE := (NOW() AT TIME ZONE 'UTC')::date;
  v_count INTEGER;
BEGIN
  INSERT INTO daily_attempts (rate_key, attempt_date, count)
  VALUES (p_rate_key, v_today, 1)
  ON CONFLICT (rate_key, attempt_date)
  DO UPDATE SET
    count = daily_attempts.count + 1,
    updated_at = NOW()
  WHERE daily_attempts.count < p_max
  RETURNING count INTO v_count;

  IF v_count IS NULL THEN
    SELECT count INTO v_count FROM daily_attempts
    WHERE rate_key = p_rate_key AND attempt_date = v_today;
    RETURN QUERY SELECT FALSE, COALESCE(v_count, 0);
  ELSE
    RETURN QUERY SELECT TRUE, v_count;
  END IF;
END;
$$;
