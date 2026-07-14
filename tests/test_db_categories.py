from db import categories, database


def test_add_master_category_inserts_master_category_row():
    con = database.connect(":memory:")
    database.initialize_database(con)

    category = categories.add_master_category(con, "Monthly Bills")

    assert category["id"] == 1
    assert category["name"] == "Monthly Bills"
    assert category["hidden"] == False


def test_add_budget_category_inserts_budget_category_row():
    con = database.connect(":memory:")
    database.initialize_database(con)
    master_category = categories.add_master_category(con, "Everyday Expenses")

    category = categories.add_budget_category(
        con,
        master_category["id"],
        "Groceries",
    )

    assert category["id"] == 1
    assert category["master_budget_category_id"] == master_category["id"]
    assert category["name"] == "Groceries"
    assert category["hidden"] == False


def test_get_budget_category_by_name_returns_matching_category():
    con = database.connect(":memory:")
    database.initialize_database(con)
    master_category = categories.add_master_category(con, "Everyday Expenses")
    categories.add_budget_category(con, master_category["id"], "Groceries")
    gas = categories.add_budget_category(con, master_category["id"], "Gas")

    category = categories.get_budget_category_by_name(con, "Gas")

    assert category["id"] == gas["id"]
    assert category["name"] == "Gas"
