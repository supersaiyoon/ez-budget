from db import accounts, categories, payees, transactions


def _create_transaction_dependencies(con):
    # Every persisted transaction requires these related database rows
    account = accounts.create_account(con, "Checking")
    payee = payees.add_payee(con, "Grocery Store")
    master_category = categories.add_master_category(con, "Everyday Expenses")
    category = categories.add_budget_category(con, master_category["id"], "Groceries")
    return account, payee, category


def test_add_transaction_inserts_transaction_row(con):
    account, payee, category = _create_transaction_dependencies(con)

    transaction = transactions.add_transaction(
        con,
        account["id"],
        payee["id"],
        category["id"],
        "2026-07-13",
        -4250,
        "weekly groceries",
    )

    assert transaction["id"] == 1
    assert transaction["account_id"] == account["id"]
    assert transaction["payee_id"] == payee["id"]
    assert transaction["budget_category_id"] == category["id"]
    assert transaction["transaction_date"] == "2026-07-13"
    assert transaction["amount"] == -4250
    assert transaction["notes"] == "weekly groceries"
    assert transaction["cleared"] == False


def test_list_transactions_returns_only_account_rows(con):
    checking, payee, category = _create_transaction_dependencies(con)
    credit_card = accounts.create_account(con, "Credit Card")

    transactions.add_transaction(
        con,
        checking["id"],
        payee["id"],
        category["id"],
        "2026-07-13",
        -4250,
    )
    transactions.add_transaction(
        con,
        credit_card["id"],
        payee["id"],
        category["id"],
        "2026-07-11",
        -3000,
    )
    transactions.add_transaction(
        con,
        checking["id"],
        payee["id"],
        category["id"],
        "2026-07-12",
        -1200,
    )

    transaction_rows = transactions.list_transactions(con, checking["id"])

    assert len(transaction_rows) == 2


def test_list_transactions_returns_rows_in_date_order(con):
    checking, payee, category = _create_transaction_dependencies(con)

    transactions.add_transaction(
        con,
        checking["id"],
        payee["id"],
        category["id"],
        "2026-07-13",
        -4250,
    )
    transactions.add_transaction(
        con,
        checking["id"],
        payee["id"],
        category["id"],
        "2026-07-12",
        -1200,
    )

    transaction_rows = transactions.list_transactions(con, checking["id"])

    assert transaction_rows[0]["transaction_date"] == "2026-07-12"
    assert transaction_rows[1]["transaction_date"] == "2026-07-13"


def test_list_transactions_returns_payee_and_category_names(con):
    checking, payee, category = _create_transaction_dependencies(con)

    transactions.add_transaction(
        con,
        checking["id"],
        payee["id"],
        category["id"],
        "2026-07-13",
        -4250,
    )

    transaction_rows = transactions.list_transactions(con, checking["id"])

    assert transaction_rows[0]["payee_name"] == "Grocery Store"
    assert transaction_rows[0]["category_name"] == "Groceries"
    assert transaction_rows[0]["budget_category_id"] == category["id"]


def test_list_transactions_returns_notes(con):
    checking, payee, category = _create_transaction_dependencies(con)

    transactions.add_transaction(
        con,
        checking["id"],
        payee["id"],
        category["id"],
        "2026-07-13",
        -4250,
        "weekly groceries",
    )

    transaction_rows = transactions.list_transactions(con, checking["id"])

    assert transaction_rows[0]["notes"] == "weekly groceries"


def test_has_transactions_reports_whether_transactions_exist(con):
    assert transactions.has_transactions(con) == False

    checking, payee, category = _create_transaction_dependencies(con)
    transactions.add_transaction(
        con,
        checking["id"],
        payee["id"],
        category["id"],
        "2026-07-13",
        -4250,
    )

    assert transactions.has_transactions(con) == True
