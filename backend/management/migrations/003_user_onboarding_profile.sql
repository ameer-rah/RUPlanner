BEGIN;

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS onboarding_completed BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS planner_profile JSONB,
    ADD COLUMN IF NOT EXISTS last_plan JSONB;

-- Existing users with saved work have already completed onboarding.
UPDATE users AS u
SET onboarding_completed = TRUE
WHERE EXISTS (
    SELECT 1 FROM saved_schedules AS s WHERE s.user_id = u.id
);

COMMIT;
