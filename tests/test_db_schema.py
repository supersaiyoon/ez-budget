from db.connection import connect
from db.schema import initialize_database


def test_initialize_database_creates_core_tables():
    con = connect(":memory:")

    initialize_database(con)

    table_names = {
        row["name"]
        for row in con.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }

    assert {
        "accounts",
        "payees",
        "master_budget_categories",
        "budget_categories",
        "transactions",
    }.issubset(table_names)


def test_schema_allows_inserting_related_transaction():
    con = connect(":memory:")
    initialize_database(con)

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
