from db import accounts, database, transactions


def test_add_transaction_inserts_transaction_row():
    con = database.connect(":memory:")
    database.initialize_database(con)
    account = accounts.create_account(con, "Checking")

    transaction = transactions.add_transaction(
        con,
        account["id"],
        "2026-07-13",
        -4250,
    )

    assert transaction["id"] == 1
    assert transaction["account_id"] == account["id"]
    assert transaction["transaction_date"] == "2026-07-13"
    assert transaction["amount"] == -4250
    assert transaction["cleared"] == 0


def test_list_transactions_returns_only_account_rows():
    con = database.connect(":memory:")
    database.initialize_database(con)
    checking = accounts.create_account(con, "Checking")
    credit_card = accounts.create_account(con, "Credit Card")

    transactions.add_transaction(con, checking["id"], "2026-07-13", -4250)
    transactions.add_transaction(con, credit_card["id"], "2026-07-11", -3000)
    transactions.add_transaction(con, checking["id"], "2026-07-12", -1200)

    transaction_rows = transactions.list_transactions(con, checking["id"])

    assert len(transaction_rows) == 2


def test_list_transactions_returns_rows_in_date_order():
    con = database.connect(":memory:")
    database.initialize_database(con)
    checking = accounts.create_account(con, "Checking")

    transactions.add_transaction(con, checking["id"], "2026-07-13", -4250)
    transactions.add_transaction(con, checking["id"], "2026-07-12", -1200)

    transaction_rows = transactions.list_transactions(con, checking["id"])

    assert transaction_rows[0]["transaction_date"] == "2026-07-12"
    assert transaction_rows[1]["transaction_date"] == "2026-07-13"
