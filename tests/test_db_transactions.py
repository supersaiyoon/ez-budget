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


def test_update_transaction_replaces_editable_fields(con):
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
    updated_payee = payees.add_payee(con, "Fuel Stop")
    updated_master = categories.add_master_category(con, "Transportation")
    updated_category = categories.add_budget_category(
        con,
        updated_master["id"],
        "Gas",
    )

    updated_transaction = transactions.update_transaction(
        con,
        transaction["id"],
        updated_payee["id"],
        updated_category["id"],
        "2026-07-14",
        -5899,
        "fuel purchase",
        cleared=True,
    )

    assert updated_transaction["id"] == transaction["id"]
    assert updated_transaction["account_id"] == account["id"]
    assert updated_transaction["payee_id"] == updated_payee["id"]
    assert updated_transaction["budget_category_id"] == updated_category["id"]
    assert updated_transaction["transaction_date"] == "2026-07-14"
    assert updated_transaction["amount"] == -5899
    assert updated_transaction["notes"] == "fuel purchase"
    assert updated_transaction["cleared"] == True


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


def test_list_category_transaction_totals_sums_amounts_within_date_range(con):
    checking, payee, category = _create_transaction_dependencies(con)
    transactions.add_transaction(
        con,
        checking["id"],
        payee["id"],
        category["id"],
        "2026-07-01",
        -4250,
    )
    transactions.add_transaction(
        con,
        checking["id"],
        payee["id"],
        category["id"],
        "2026-07-31",
        1000,
    )
    transactions.add_transaction(
        con,
        checking["id"],
        payee["id"],
        category["id"],
        "2026-08-01",
        -2000,
    )

    category_totals = transactions.list_category_transaction_totals(
        con,
        "2026-07-01",
        "2026-07-31",
    )

    assert len(category_totals) == 1
    assert category_totals[0]["budget_category_id"] == category["id"]
    assert category_totals[0]["total_amount"] == -3250


def test_list_category_transaction_totals_excludes_off_budget_accounts(con):
    checking, payee, category = _create_transaction_dependencies(con)
    tracking = accounts.create_account(con, "Tracking", on_budget=False)
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
        tracking["id"],
        payee["id"],
        category["id"],
        "2026-07-14",
        -2000,
    )

    category_totals = transactions.list_category_transaction_totals(
        con,
        "2026-07-01",
        "2026-07-31",
    )

    assert category_totals[0]["total_amount"] == -4250


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
