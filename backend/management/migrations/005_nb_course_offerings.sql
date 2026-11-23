BEGIN;

CREATE TABLE IF NOT EXISTS course_imports (
    year integer NOT NULL,
    term varchar(8) NOT NULL,
    level varchar(1) NOT NULL,
    course_count integer NOT NULL,
    synced_at timestamp NOT NULL,
    PRIMARY KEY (year, term, level)
);

CREATE TABLE IF NOT EXISTS course_offerings (
    year integer NOT NULL,
    term varchar(8) NOT NULL,
    level varchar(1) NOT NULL,
    raw_code varchar(20) NOT NULL REFERENCES courses(raw_code),
    PRIMARY KEY (year, term, level, raw_code)
);

COMMIT;
