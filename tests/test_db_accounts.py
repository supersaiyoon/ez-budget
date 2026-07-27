from db import accounts, categories, payees, transactions


def test_create_account_inserts_account_row(con):

    account_name = "Checking"

    accounts.create_account(con, account_name)
    # Parameter binding expects tuple so comma is required even for single value
    account = con.execute("SELECT * FROM accounts WHERE name = ?", (account_name,)).fetchone()

    assert account["id"] == 1
    assert account["name"] == "Checking"
    assert account["on_budget"] == True
    assert account["closed"] == False


def test_list_accounts_excludes_closed_accounts(con):

    checking = accounts.create_account(con, "Checking")
    accounts.create_account(con, "Credit Card")
    con.execute("UPDATE accounts SET closed = TRUE WHERE id = ?", (checking["id"],))
    con.commit()

    account_rows = accounts.list_accounts(con)

    assert [account["name"] for account in account_rows] == ["Credit Card"]


def test_list_closed_accounts_excludes_open_accounts(con):

    checking = accounts.create_account(con, "Checking")
    accounts.create_account(con, "Credit Card")
    con.execute("UPDATE accounts SET closed = TRUE WHERE id = ?", (checking["id"],))
    con.commit()

    account_rows = accounts.list_closed_accounts(con)

    assert [account["name"] for account in account_rows] == ["Checking"]
    assert account_rows[0]["closed"] == True


def test_get_account_by_name_returns_matching_account(con):
    accounts.create_account(con, "Checking")
    credit_card = accounts.create_account(con, "Credit Card")

    account = accounts.get_account_by_name(con, "credit card")

    assert account["id"] == credit_card["id"]
    assert account["name"] == "Credit Card"


def test_delete_account_removes_empty_account(con):
    checking = accounts.create_account(con, "Checking")
    accounts.create_account(con, "Credit Card")

    deleted = accounts.delete_account(con, checking["id"])

    assert deleted["id"] == checking["id"]
    assert deleted["name"] == "Checking"
    assert [row["name"] for row in accounts.list_accounts(con)] == [
        "Credit Card"
    ]


def test_delete_account_keeps_account_with_transactions(con):
    checking = accounts.create_account(con, "Checking")
    grocery_store = payees.add_payee(con, "Grocery Store")
    master_category = categories.add_master_category(
        con,
        "Everyday Expenses",
    )
    groceries = categories.add_budget_category(
        con,
        master_category["id"],
        "Groceries",
    )
    transactions.add_transaction(
        con,
        checking["id"],
        grocery_store["id"],
        groceries["id"],
        "2026-07-21",
        -4250,
    )

    deleted = accounts.delete_account(con, checking["id"])

    assert deleted is None
    assert accounts.get_account_by_name(con, "Checking")["id"] == checking["id"]


def test_has_accounts_reports_whether_accounts_exist(con):

    assert accounts.has_accounts(con) is False

    accounts.create_account(con, "Checking")

    assert accounts.has_accounts(con) is True
