from db import categories, database


def test_add_master_category_inserts_master_category_row():
    con = database.connect(":memory:")
    database.initialize_database(con)

    category = categories.add_master_category(con, "Monthly Bills")

    assert category["id"] == 1
    assert category["name"] == "Monthly Bills"
    assert category["hidden"] == False


def test_list_master_categories_returns_visible_categories_in_id_order():
    con = database.connect(":memory:")
    database.initialize_database(con)
    categories.add_master_category(con, "Hidden Category", hidden=True)
    categories.add_master_category(con, "Monthly Bills")
    categories.add_master_category(con, "Everyday Expenses")

    category_rows = categories.list_master_categories(con)

    assert [category["name"] for category in category_rows] == [
        "Monthly Bills",
        "Everyday Expenses",
    ]


def test_get_master_category_by_name_returns_matching_category():
    con = database.connect(":memory:")
    database.initialize_database(con)
    categories.add_master_category(con, "Monthly Bills")
    everyday_expenses = categories.add_master_category(con, "Everyday Expenses")

    category = categories.get_master_category_by_name(con, "everyday expenses")

    assert category["id"] == everyday_expenses["id"]
    assert category["name"] == "Everyday Expenses"


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


def test_list_budget_categories_returns_visible_categories_for_master_in_id_order():
    con = database.connect(":memory:")
    database.initialize_database(con)
    bills = categories.add_master_category(con, "Monthly Bills")
    expenses = categories.add_master_category(con, "Everyday Expenses")
    categories.add_budget_category(con, bills["id"], "Electricity")
    categories.add_budget_category(con, expenses["id"], "Hidden Expense", hidden=True)
    categories.add_budget_category(con, expenses["id"], "Groceries")
    categories.add_budget_category(con, expenses["id"], "Gas")

    category_rows = categories.list_budget_categories(con, expenses["id"])

    assert [category["name"] for category in category_rows] == ["Groceries", "Gas"]


def test_get_budget_category_by_name_returns_matching_category():
    con = database.connect(":memory:")
    database.initialize_database(con)
    bills = categories.add_master_category(con, "Monthly Bills")
    expenses = categories.add_master_category(con, "Everyday Expenses")
    categories.add_budget_category(con, bills["id"], "Other")
    expense_category = categories.add_budget_category(con, expenses["id"], "Other")

    category = categories.get_budget_category_by_name(con, expenses["id"], "other")

    assert category["id"] == expense_category["id"]
    assert category["master_budget_category_id"] == expenses["id"]
    assert category["name"] == "Other"
