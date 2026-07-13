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
