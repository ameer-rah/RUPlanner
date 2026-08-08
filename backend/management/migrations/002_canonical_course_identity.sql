BEGIN;

-- Backfill canonical identity for legacy rows when component columns exist.
UPDATE courses
SET raw_code = offering_unit_code || ':' || subject_code || ':' || course_number
WHERE raw_code IS NULL
  AND offering_unit_code IS NOT NULL
  AND subject_code IS NOT NULL
  AND course_number IS NOT NULL;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM courses WHERE raw_code IS NULL) THEN
        RAISE EXCEPTION 'Cannot migrate courses: rows with no canonical Rutgers raw_code remain';
    END IF;
END $$;

ALTER TABLE courses DROP CONSTRAINT IF EXISTS courses_pkey;
ALTER TABLE courses DROP CONSTRAINT IF EXISTS courses_raw_code_key;
ALTER TABLE courses ALTER COLUMN raw_code SET NOT NULL;
ALTER TABLE courses ALTER COLUMN credits TYPE DOUBLE PRECISION USING credits::DOUBLE PRECISION;
ALTER TABLE courses ADD CONSTRAINT courses_pkey PRIMARY KEY (raw_code);
DROP INDEX IF EXISTS ix_courses_raw_code;
CREATE INDEX IF NOT EXISTS ix_courses_code ON courses (code);

COMMIT;
