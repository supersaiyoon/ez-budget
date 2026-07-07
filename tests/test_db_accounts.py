from db.accounts import create_account, list_accounts
from db.connection import connect
from db.schema import initialize_database


def test_create_account_inserts_account_row():
    # In-memory db
    con = connect(":memory:")
    initialize_database(con)

    account_name = "Checking"

    create_account(con, account_name)
    # Parameter binding expects tuple so comma is required even for single value
    account = con.execute("SELECT * FROM accounts WHERE name = ?", (account_name,)).fetchone()

    assert account["id"] == 1
    assert account["name"] == "Checking"
    assert account["on_budget"] == 1
    assert account["closed"] == 0


def test_list_accounts_excludes_closed_accounts():
    con = connect(":memory:")
    initialize_database(con)

    checking = create_account(con, "Checking")
    create_account(con, "Credit Card")
    con.execute("UPDATE accounts SET closed = TRUE WHERE id = ?", (checking["id"],))
    con.commit()

    accounts = list_accounts(con)

    assert [account["name"] for account in accounts] == ["Credit Card"]
