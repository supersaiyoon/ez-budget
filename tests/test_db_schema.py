import sqlite3

import pytest

from db import database


def test_initialize_database_creates_core_tables():
    con = database.connect(":memory:")

    database.initialize_database(con)

    table_names = {
        row["name"]
        for row in con.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }

    assert {
        "accounts",
        "app_settings",
        "budget_allocations",
        "budget_months",
        "payees",
        "master_budget_categories",
        "budget_categories",
        "transactions",
    }.issubset(table_names)


def test_budget_month_requires_unique_date():
    con = database.connect(":memory:")
    database.initialize_database(con)
    columns = {
        column["name"]: column
        for column in con.execute("PRAGMA table_info(budget_months)")
    }

    budget_month = con.execute(
        "INSERT INTO budget_months (month_date) VALUES (?) RETURNING *",
        ("2026-07-01",),
    ).fetchone()

    assert columns["month_date"]["notnull"] == True
    assert "monthly_income" not in columns
    assert budget_month["month_date"] == "2026-07-01"
    with pytest.raises(sqlite3.IntegrityError):
        con.execute(
            "INSERT INTO budget_months (month_date) VALUES (?)",
            ("2026-07-01",),
        )


def test_budget_allocations_require_month_and_category_relationships():
    con = database.connect(":memory:")
    database.initialize_database(con)
    # Schema metadata verifies relationships without creating dependency rows
    columns = {
        column["name"]: column
        for column in con.execute("PRAGMA table_info(budget_allocations)")
    }
    foreign_keys = {
        foreign_key["from"]: foreign_key
        for foreign_key in con.execute("PRAGMA foreign_key_list(budget_allocations)")
    }

    assert columns["budget_month_id"]["notnull"] == True
    assert columns["budget_category_id"]["notnull"] == True
    assert foreign_keys["budget_month_id"]["table"] == "budget_months"
    assert foreign_keys["budget_month_id"]["to"] == "id"
    assert foreign_keys["budget_category_id"]["table"] == "budget_categories"
    assert foreign_keys["budget_category_id"]["to"] == "id"


def test_category_tables_include_display_order():
    con = database.connect(":memory:")
    database.initialize_database(con)

    master_columns = {
        column["name"]: column
        for column in con.execute("PRAGMA table_info(master_budget_categories)")
    }
    category_columns = {
        column["name"]: column
        for column in con.execute("PRAGMA table_info(budget_categories)")
    }

    assert master_columns["display_order"]["notnull"] == True
    assert category_columns["display_order"]["notnull"] == True


def test_initialize_database_migrates_category_display_order_columns():
    con = database.connect(":memory:")
    con.executescript(
        """
        CREATE TABLE master_budget_categories (
            id                  INTEGER PRIMARY KEY,
            name                TEXT NOT NULL UNIQUE,
            hidden              BOOLEAN NOT NULL DEFAULT FALSE
        );
        CREATE TABLE budget_categories (
            id                          INTEGER PRIMARY KEY,
            master_budget_category_id   INT NOT NULL,
            name                        TEXT NOT NULL,
            hidden                      BOOLEAN NOT NULL DEFAULT FALSE,
            UNIQUE (master_budget_category_id, name)
        );
        INSERT INTO master_budget_categories (name) VALUES ('Monthly Bills');
        INSERT INTO master_budget_categories (name) VALUES ('Everyday Expenses');
        INSERT INTO budget_categories (master_budget_category_id, name)
        VALUES (1, 'Rent');
        INSERT INTO budget_categories (master_budget_category_id, name)
        VALUES (1, 'Electricity');
        """
    )

    database.initialize_database(con)

    master_rows = con.execute(
        """
        SELECT id, display_order
        FROM master_budget_categories
        ORDER BY id
        """
    ).fetchall()
    category_rows = con.execute(
        """
        SELECT id, display_order
        FROM budget_categories
        ORDER BY id
        """
    ).fetchall()
    assert [row["display_order"] for row in master_rows] == [1, 2]
    assert [row["display_order"] for row in category_rows] == [1, 2]


def test_budget_allocations_reject_duplicate_month_and_category():
    con = database.connect(":memory:")
    database.initialize_database(con)
    budget_month_id = con.execute(
        "INSERT INTO budget_months (month_date) VALUES (?) RETURNING id",
        ("2026-07-01",),
    ).fetchone()["id"]
    master_category_id = con.execute(
        "INSERT INTO master_budget_categories (name) VALUES (?) RETURNING id",
        ("Everyday Expenses",),
    ).fetchone()["id"]
    budget_category_id = con.execute(
        """
        INSERT INTO budget_categories (master_budget_category_id, name)
        VALUES (?, ?)
        RETURNING id
        """,
        (master_category_id, "Groceries"),
    ).fetchone()["id"]
    allocation_values = (budget_month_id, budget_category_id, 42500)

    con.execute(
        """
        INSERT INTO budget_allocations (budget_month_id, budget_category_id, amount)
        VALUES (?, ?, ?)
        """,
        allocation_values,
    )

    with pytest.raises(sqlite3.IntegrityError):
        con.execute(
            """
            INSERT INTO budget_allocations (budget_month_id, budget_category_id, amount)
            VALUES (?, ?, ?)
            """,
            allocation_values,
        )


def test_transaction_relationship_columns_are_required():
    con = database.connect(":memory:")
    database.initialize_database(con)

    # Ensures assertions fail if columns are missing or nullable
    payee_required = False
    budget_category_required = False

    for column in con.execute("PRAGMA table_info(transactions)"):
        if column["name"] == "payee_id":
            payee_required = column["notnull"]
        if column["name"] == "budget_category_id":
            budget_category_required = column["notnull"]

    assert payee_required == True
    assert budget_category_required == True


def test_transaction_income_month_date_is_optional_text():
    con = database.connect(":memory:")
    database.initialize_database(con)

    # Ordinary spending transactions leave income target empty
    columns = {
        column["name"]: column
        for column in con.execute("PRAGMA table_info(transactions)")
    }

    assert columns["income_month_date"]["type"] == "TEXT"
    assert columns["income_month_date"]["notnull"] == False


def test_budget_category_names_are_unique_within_each_master():
    con = database.connect(":memory:")
    database.initialize_database(con)
    bills_id = con.execute(
        "INSERT INTO master_budget_categories (name) VALUES (?) RETURNING id",
        ("Monthly Bills",),
    ).fetchone()["id"]
    spending_id = con.execute(
        "INSERT INTO master_budget_categories (name) VALUES (?) RETURNING id",
        ("Everyday Spending",),
    ).fetchone()["id"]

    con.execute(
        "INSERT INTO budget_categories (master_budget_category_id, name) VALUES (?, ?)",
        (bills_id, "Other"),
    )
    con.execute(
        "INSERT INTO budget_categories (master_budget_category_id, name) VALUES (?, ?)",
        (spending_id, "Other"),
    )

    with pytest.raises(sqlite3.IntegrityError):
        con.execute(
            "INSERT INTO budget_categories (master_budget_category_id, name) VALUES (?, ?)",
            (bills_id, "Other"),
        )


def test_schema_allows_inserting_related_transaction():
    con = database.connect(":memory:")
    database.initialize_database(con)

    account_id = con.execute(
        "INSERT INTO accounts (name) VALUES (?) RETURNING id",
        ("Checking",),
    ).fetchone()["id"]
    payee_id = con.execute(
        "INSERT INTO payees (name) VALUES (?) RETURNING id",
        ("Grocery Market",),
    ).fetchone()["id"]
    master_category_id = con.execute(
        "INSERT INTO master_budget_categories (name) VALUES (?) RETURNING id",
        ("Everyday Spending",),
    ).fetchone()["id"]
    budget_category_id = con.execute(
        """
        INSERT INTO budget_categories (master_budget_category_id, name)
        VALUES (?, ?)
        RETURNING id
        """,
        (master_category_id, "Groceries"),
    ).fetchone()["id"]

    transaction_id = con.execute(
        """
        INSERT INTO transactions (
            account_id,
            payee_id,
            budget_category_id,
            transaction_date,
            notes,
            amount,
            cleared
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        RETURNING id
        """,
        (
            account_id,
            payee_id,
            budget_category_id,
            "2026-07-06",
            "weekly groceries",
            -14238,
            False,
        ),
    ).fetchone()["id"]

    row = con.execute(
        """
        SELECT
            transactions.amount,
            accounts.name AS account_name,
            payees.name AS payee_name,
            budget_categories.name AS category_name,
            master_budget_categories.name AS master_category_name
        FROM transactions
        JOIN accounts ON accounts.id = transactions.account_id
        JOIN payees ON payees.id = transactions.payee_id
        JOIN budget_categories ON budget_categories.id = transactions.budget_category_id
        JOIN master_budget_categories
            ON master_budget_categories.id = budget_categories.master_budget_category_id
        WHERE transactions.id = ?
        """,
        (transaction_id,),
    ).fetchone()

    assert row["amount"] == -14238
    assert row["account_name"] == "Checking"
    assert row["payee_name"] == "Grocery Market"
    assert row["category_name"] == "Groceries"
    assert row["master_category_name"] == "Everyday Spending"
