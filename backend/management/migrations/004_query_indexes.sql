-- Index the authenticated list/delete paths and the worker's polling query.
CREATE INDEX IF NOT EXISTS ix_saved_schedules_user_created
    ON saved_schedules (user_id, created_at);

CREATE INDEX IF NOT EXISTS ix_snipes_user_active
    ON snipes (user_id, active);

CREATE INDEX IF NOT EXISTS ix_snipes_pollable
    ON snipes (active, notified_at);
