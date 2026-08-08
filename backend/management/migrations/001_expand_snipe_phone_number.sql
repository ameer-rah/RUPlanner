-- Required because SQLAlchemy create_all() does not alter existing columns.
ALTER TABLE snipes
    ALTER COLUMN phone_number TYPE VARCHAR(255);
