-- Accounts kept separate so transactions can support multiple balances later.
CREATE TABLE IF NOT EXISTS accounts (
    id                  INT PRIMARY KEY,
    name                TEXT NOT NULL,
    on_budget           BOOLEAN NOT NULL DEFAULT TRUE,
    closed              BOOLEAN NOT NULL DEFAULT FALSE
);

-- Payees normalized so repeated merchants do not need duplicate text.
CREATE TABLE IF NOT EXISTS payees (
    id                  INT PRIMARY KEY,
    name                TEXT NOT NULL UNIQUE
);

-- Categories stored independently so budgets and transactions can share labels.
CREATE TABLE IF NOT EXISTS budget_categories (
    id                  INT PRIMARY KEY,
    name                TEXT NOT NULL UNIQUE,
    hidden              BOOLEAN NOT NULL DEFAULT FALSE
);

-- Amount stored as integer so persisted money can avoid floating point drift.
CREATE TABLE IF NOT EXISTS transactions (
    id                  INT PRIMARY KEY,
    account_id          INT NOT NULL REFERENCES accounts(id),
    payee_id            INT REFERENCES payees(id),
    budget_category_id  INT REFERENCES budget_categories(id),
    transaction_date    TEXT NOT NULL,
    created_at          TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    notes               TEXT,
    amount              INT NOT NULL,
    cleared             BOOLEAN NOT NULL DEFAULT FALSE
);
