-- Cleanup cron for learn_jobs and old daily_attempts.
--
-- Run this in Supabase SQL Editor once. Requires the pg_cron extension,
-- which is preinstalled on Supabase but disabled by default. The two
-- CREATE EXTENSION lines below are idempotent.
--
-- After running this file:
--   SELECT * FROM cron.job;
-- should list 'cleanup-learn-jobs' and 'cleanup-daily-attempts'.

CREATE EXTENSION IF NOT EXISTS pg_cron;

-- learn_jobs: drop rows past their TTL (default 24h after insert).
-- Runs every hour at minute 17 to spread Supabase load.
SELECT cron.schedule(
  'cleanup-learn-jobs',
  '17 * * * *',
  $$DELETE FROM public.learn_jobs WHERE expires_at < NOW();$$
);

-- daily_attempts: keep only the last 30 days of rate-limit history.
-- Runs daily at 04:30 UTC (= 13:30 JST).
SELECT cron.schedule(
  'cleanup-daily-attempts',
  '30 4 * * *',
  $$DELETE FROM public.daily_attempts
    WHERE attempt_date < (CURRENT_DATE - INTERVAL '30 days');$$
);

-- To inspect / tear down:
--   SELECT jobid, jobname, schedule, command FROM cron.job;
--   SELECT cron.unschedule('cleanup-learn-jobs');
--   SELECT cron.unschedule('cleanup-daily-attempts');
