from db import accounts, database


def test_create_account_inserts_account_row():
    # In-memory db
    con = database.connect(":memory:")
    database.initialize_database(con)

    account_name = "Checking"

    accounts.create_account(con, account_name)
    # Parameter binding expects tuple so comma is required even for single value
    account = con.execute("SELECT * FROM accounts WHERE name = ?", (account_name,)).fetchone()

    assert account["id"] == 1
    assert account["name"] == "Checking"
    assert account["on_budget"] == 1
    assert account["closed"] == 0


def test_list_accounts_excludes_closed_accounts():
    con = database.connect(":memory:")
    database.initialize_database(con)

    checking = accounts.create_account(con, "Checking")
    accounts.create_account(con, "Credit Card")
    con.execute("UPDATE accounts SET closed = TRUE WHERE id = ?", (checking["id"],))
    con.commit()

    accounts = accounts.list_accounts(con)

    assert [account["name"] for account in accounts] == ["Credit Card"]


def test_has_accounts_reports_whether_accounts_exist():
    con = database.connect(":memory:")
    database.initialize_database(con)

    assert accounts.has_accounts(con) is False

    accounts.create_account(con, "Checking")

    assert accounts.has_accounts(con) is True
