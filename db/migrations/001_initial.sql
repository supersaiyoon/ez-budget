CREATE TABLE IF NOT EXISTS accounts (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    on_budget   BOOLEAN NOT NULL,
    closed      BOOLEAN NOT NULL
);