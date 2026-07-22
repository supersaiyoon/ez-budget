-- Accounts kept separate so transactions can support multiple balances later
CREATE TABLE IF NOT EXISTS accounts (
    id                  INTEGER PRIMARY KEY,
    name                TEXT NOT NULL,
    on_budget           BOOLEAN NOT NULL DEFAULT TRUE,
    closed              BOOLEAN NOT NULL DEFAULT FALSE
);

-- One row per calendar month keeps income separate from category allocations
CREATE TABLE IF NOT EXISTS budget_months (
    id                  INTEGER PRIMARY KEY,
    month_date          TEXT NOT NULL UNIQUE,
    monthly_income      INT NOT NULL DEFAULT 0
);

-- Normalize payees
CREATE TABLE IF NOT EXISTS payees (
    id                  INTEGER PRIMARY KEY,
    name                TEXT NOT NULL UNIQUE
);

-- Normalize master budget categories
CREATE TABLE IF NOT EXISTS master_budget_categories (
    id                  INTEGER PRIMARY KEY,
    name                TEXT NOT NULL UNIQUE,
    hidden              BOOLEAN NOT NULL DEFAULT FALSE
);

-- Budgets and transactions can share labels
CREATE TABLE IF NOT EXISTS budget_categories (
    id                          INTEGER PRIMARY KEY,
    master_budget_category_id   INT NOT NULL REFERENCES master_budget_categories(id),
    name                        TEXT NOT NULL,
    hidden                      BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (master_budget_category_id, name)
);

-- Monthly rows store user-assigned cents for each budget category
CREATE TABLE IF NOT EXISTS budget_allocations (
    id                  INTEGER PRIMARY KEY,
    budget_month_id     INT NOT NULL REFERENCES budget_months(id),
    budget_category_id  INT NOT NULL REFERENCES budget_categories(id),
    amount              INT NOT NULL DEFAULT 0
);

-- Amount stored as integer to avoid floating point drift
CREATE TABLE IF NOT EXISTS transactions (
    id                  INTEGER PRIMARY KEY,
    account_id          INT NOT NULL REFERENCES accounts(id),
    payee_id            INT NOT NULL REFERENCES payees(id),
    budget_category_id  INT NOT NULL REFERENCES budget_categories(id),
    transaction_date    TEXT NOT NULL,
    created_at          TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    notes               TEXT,
    amount              INT NOT NULL,
    cleared             BOOLEAN NOT NULL DEFAULT FALSE
);
