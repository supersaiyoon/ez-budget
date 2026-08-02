from db import accounts, categories, payees, transactions


def _create_transaction(con, payee):
    # Minimal related rows for payee usage tests
    account = accounts.create_account(con, "Checking")
    master_category = categories.add_master_category(con, "Everyday Expenses")
    category = categories.add_budget_category(con, master_category["id"], "Groceries")
    return transactions.add_transaction(
        con,
        account["id"],
        payee["id"],
        category["id"],
        "2026-07-13",
        -4250,
    )


def test_add_payee_inserts_payee_row(con):

    payee = payees.add_payee(con, "Grocery Store")

    assert payee["id"] == 1
    assert payee["name"] == "Grocery Store"


def test_get_payee_by_name_returns_matching_payee(con):
    payees.add_payee(con, "Grocery Store")
    fuel_stop = payees.add_payee(con, "Fuel Stop")

    payee = payees.get_payee_by_name(con, "fUeL sToP")

    assert payee["id"] == fuel_stop["id"]
    assert payee["name"] == "Fuel Stop"


def test_get_or_create_payee_reuses_existing_payee(con):
    existing_payee = payees.add_payee(con, "Grocery Store")

    payee = payees.get_or_create_payee(con, "grocery store")

    assert payee["id"] == existing_payee["id"]
    assert con.execute("SELECT COUNT(*) FROM payees").fetchone()[0] == 1


def test_get_or_create_payee_adds_missing_payee(con):

    payee = payees.get_or_create_payee(con, "Fuel Stop")

    assert payee["id"] == 1
    assert payee["name"] == "Fuel Stop"


def test_list_payees_excludes_income_placeholder(con):
    payees.add_payee(con, "Grocery Store")
    payees.add_payee(con, payees.INCOME_PAYEE_NAME)
    payees.add_payee(con, "Fuel Stop")

    payee_names = [payee["name"] for payee in payees.list_payees(con)]

    assert payee_names == ["Fuel Stop", "Grocery Store"]


def test_rename_payee_updates_payee_row(con):
    payee = payees.add_payee(con, "Grocery Store")

    renamed_payee = payees.rename_payee(con, payee["id"], "Grocery Market")

    assert renamed_payee["id"] == payee["id"]
    assert renamed_payee["name"] == "Grocery Market"
    assert payees.get_payee_by_name(con, "Grocery Market")["id"] == payee["id"]


def test_rename_payee_keeps_transaction_links(con):
    payee = payees.add_payee(con, "Grocery Store")
    _create_transaction(con, payee)

    payees.rename_payee(con, payee["id"], "Grocery Market")

    assert payees.count_transactions_for_payee(con, payee["id"]) == 1


def test_rename_payee_rejects_blank_name(con):
    payee = payees.add_payee(con, "Grocery Store")

    renamed_payee = payees.rename_payee(con, payee["id"], "  ")

    assert renamed_payee is None
    assert payees.get_payee_by_name(con, "Grocery Store") is not None


def test_rename_payee_rejects_case_insensitive_duplicate(con):
    grocery_store = payees.add_payee(con, "Grocery Store")
    fuel_stop = payees.add_payee(con, "Fuel Stop")

    renamed_payee = payees.rename_payee(con, fuel_stop["id"], "grocery store")

    assert renamed_payee is None
    assert payees.get_payee_by_name(con, "Fuel Stop")["id"] == fuel_stop["id"]
    assert payees.get_payee_by_name(con, "Grocery Store")["id"] == grocery_store["id"]


def test_count_transactions_for_payee_returns_usage_count(con):
    payee = payees.add_payee(con, "Grocery Store")

    _create_transaction(con, payee)

    assert payees.count_transactions_for_payee(con, payee["id"]) == 1


def test_delete_unused_payee_removes_payee(con):
    payee = payees.add_payee(con, "Grocery Store")

    deleted_payee = payees.delete_unused_payee(con, payee["id"])

    assert deleted_payee["id"] == payee["id"]
    assert payees.get_payee_by_name(con, "Grocery Store") is None


def test_delete_used_payee_returns_none(con):
    payee = payees.add_payee(con, "Grocery Store")
    _create_transaction(con, payee)

    deleted_payee = payees.delete_unused_payee(con, payee["id"])

    assert deleted_payee is None
    assert payees.get_payee_by_name(con, "Grocery Store") is not None


def test_reassign_transactions_to_existing_payee_and_delete_old_payee(con):
    old_payee = payees.add_payee(con, "Grocery Store")
    new_payee = payees.add_payee(con, "Grocery Market")
    _create_transaction(con, old_payee)

    deleted_payee = payees.reassign_transactions_and_delete_payee(
        con,
        old_payee["id"],
        "grocery market",
    )

    assert deleted_payee["id"] == old_payee["id"]
    assert payees.get_payee_by_name(con, "Grocery Store") is None
    assert payees.count_transactions_for_payee(con, new_payee["id"]) == 1


def test_reassign_transactions_to_new_payee_and_delete_old_payee(con):
    old_payee = payees.add_payee(con, "Grocery Store")
    _create_transaction(con, old_payee)

    deleted_payee = payees.reassign_transactions_and_delete_payee(
        con,
        old_payee["id"],
        "Grocery Market",
    )
    new_payee = payees.get_payee_by_name(con, "Grocery Market")

    assert deleted_payee["id"] == old_payee["id"]
    assert new_payee is not None
    assert payees.count_transactions_for_payee(con, new_payee["id"]) == 1


def test_reassign_transactions_rejects_same_payee(con):
    payee = payees.add_payee(con, "Grocery Store")
    _create_transaction(con, payee)

    deleted_payee = payees.reassign_transactions_and_delete_payee(
        con,
        payee["id"],
        "grocery store",
    )

    assert deleted_payee is None
    assert payees.get_payee_by_name(con, "Grocery Store") is not None
