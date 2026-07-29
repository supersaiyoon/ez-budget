from db import accounts, budgets, categories, payees, transactions


def test_add_master_category_inserts_master_category_row(con):

    category = categories.add_master_category(con, "Monthly Bills")

    assert category["id"] == 1
    assert category["name"] == "Monthly Bills"
    assert category["hidden"] == False


def test_list_master_categories_returns_visible_categories_in_id_order(con):
    categories.add_master_category(con, "Hidden Category", hidden=True)
    categories.add_master_category(con, "Monthly Bills")
    categories.add_master_category(con, "Everyday Expenses")

    category_rows = categories.list_master_categories(con)

    assert [category["name"] for category in category_rows] == [
        "Monthly Bills",
        "Everyday Expenses",
    ]


def test_list_hidden_master_categories_excludes_system_group(con):
    categories.get_or_create_income_category(con)
    hidden_user_category = categories.add_master_category(
        con,
        "Archived Goals",
        hidden=True,
    )
    categories.add_master_category(con, "Monthly Bills")

    category_rows = categories.list_hidden_master_categories(con)

    assert [category["id"] for category in category_rows] == [
        hidden_user_category["id"]
    ]
    assert [category["name"] for category in category_rows] == [
        "Archived Goals"
    ]


def test_get_master_category_by_name_returns_matching_category(con):
    categories.add_master_category(con, "Monthly Bills")
    everyday_expenses = categories.add_master_category(con, "Everyday Expenses")

    category = categories.get_master_category_by_name(con, "everyday expenses")

    assert category["id"] == everyday_expenses["id"]
    assert category["name"] == "Everyday Expenses"


def test_rename_master_category_updates_matching_row(con):
    category = categories.add_master_category(con, "Monthly Bills")

    renamed = categories.rename_master_category(
        con,
        category["id"],
        "Fixed Expenses",
    )

    assert renamed["id"] == category["id"]
    assert renamed["name"] == "Fixed Expenses"
    assert categories.get_master_category_by_name(
        con,
        "Monthly Bills",
    ) is None


def test_rename_master_category_rejects_duplicate_name(con):
    monthly_bills = categories.add_master_category(con, "Monthly Bills")
    categories.add_master_category(con, "Everyday Expenses")

    renamed = categories.rename_master_category(
        con,
        monthly_bills["id"],
        "everyday expenses",
    )

    assert renamed is None
    assert categories.get_master_category_by_name(
        con,
        "Monthly Bills",
    )["id"] == monthly_bills["id"]


def test_delete_master_category_removes_unused_children_and_allocations(con):
    expenses = categories.add_master_category(con, "Everyday Expenses")
    groceries = categories.add_budget_category(
        con,
        expenses["id"],
        "Groceries",
    )
    categories.add_budget_category(con, expenses["id"], "Dining Out")
    budget_month = budgets.get_or_create_budget_month(
        con,
        "2026-07-01",
    )
    budgets.set_budget_allocation(
        con,
        budget_month["id"],
        groceries["id"],
        50000,
    )

    deleted = categories.delete_master_category(
        con,
        expenses["id"],
    )

    assert deleted["id"] == expenses["id"]
    assert categories.get_master_category_by_name(
        con,
        "Everyday Expenses",
    ) is None
    assert budgets.list_budget_allocations(
        con,
        budget_month["id"],
    ) == []


def test_delete_master_category_preserves_group_with_transactions(con):
    expenses = categories.add_master_category(con, "Everyday Expenses")
    groceries = categories.add_budget_category(
        con,
        expenses["id"],
        "Groceries",
    )
    budget_month = budgets.get_or_create_budget_month(
        con,
        "2026-07-01",
    )
    budgets.set_budget_allocation(
        con,
        budget_month["id"],
        groceries["id"],
        50000,
    )
    checking = accounts.create_account(con, "Checking")
    grocery_store = payees.add_payee(con, "Grocery Store")
    transactions.add_transaction(
        con,
        checking["id"],
        grocery_store["id"],
        groceries["id"],
        "2026-07-21",
        -4250,
    )

    deleted = categories.delete_master_category(
        con,
        expenses["id"],
    )

    assert deleted is None
    assert categories.get_master_category_by_name(
        con,
        "Everyday Expenses",
    )["id"] == expenses["id"]
    assert categories.list_budget_categories(
        con,
        expenses["id"],
    )[0]["id"] == groceries["id"]
    assert len(
        budgets.list_budget_allocations(con, budget_month["id"])
    ) == 1


def test_set_master_category_hidden_filters_and_restores_group(con):
    expenses = categories.add_master_category(con, "Everyday Expenses")
    groceries = categories.add_budget_category(
        con,
        expenses["id"],
        "Groceries",
    )

    hidden = categories.set_master_category_hidden(
        con,
        expenses["id"],
        True,
    )

    assert hidden["hidden"] == True
    assert categories.list_master_categories(con) == []
    assert categories.list_transaction_categories(con) == []
    # Child keeps own visibility so restoring parent restores group
    assert categories.list_budget_categories(
        con,
        expenses["id"],
    )[0]["id"] == groceries["id"]

    restored = categories.set_master_category_hidden(
        con,
        expenses["id"],
        False,
    )

    assert restored["hidden"] == False
    assert categories.list_master_categories(con)[0]["id"] == expenses["id"]
    assert categories.list_transaction_categories(con)[0]["id"] == (
        groceries["id"]
    )


def test_add_budget_category_inserts_budget_category_row(con):
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


def test_list_budget_categories_returns_visible_categories_for_master_in_id_order(con):
    bills = categories.add_master_category(con, "Monthly Bills")
    expenses = categories.add_master_category(con, "Everyday Expenses")
    categories.add_budget_category(con, bills["id"], "Electricity")
    categories.add_budget_category(con, expenses["id"], "Hidden Expense", hidden=True)
    categories.add_budget_category(con, expenses["id"], "Groceries")
    categories.add_budget_category(con, expenses["id"], "Gas")

    category_rows = categories.list_budget_categories(con, expenses["id"])

    assert [category["name"] for category in category_rows] == ["Groceries", "Gas"]


def test_list_hidden_budget_categories_excludes_hidden_master_groups(con):
    expenses = categories.add_master_category(con, "Everyday Expenses")
    archived = categories.add_master_category(
        con,
        "Archived",
        hidden=True,
    )
    hidden_groceries = categories.add_budget_category(
        con,
        expenses["id"],
        "Groceries",
        hidden=True,
    )
    categories.add_budget_category(con, expenses["id"], "Dining Out")
    categories.add_budget_category(
        con,
        archived["id"],
        "Old Goal",
        hidden=True,
    )
    categories.get_or_create_income_category(con)

    category_rows = categories.list_hidden_budget_categories(con)

    assert len(category_rows) == 1
    assert category_rows[0]["id"] == hidden_groceries["id"]
    assert category_rows[0]["name"] == "Groceries"
    assert (
        category_rows[0]["master_category_name"]
        == "Everyday Expenses"
    )


def test_list_transaction_categories_joins_visible_categories_with_their_masters(con):
    # Duplicate names verify parent join while hidden rows verify filtering
    expenses = categories.add_master_category(con, "Everyday Expenses")
    household = categories.add_master_category(con, "Household")
    hidden_master = categories.add_master_category(con, "Hidden", hidden=True)
    expense_category = categories.add_budget_category(con, expenses["id"], "Other")
    household_category = categories.add_budget_category(con, household["id"], "Other")
    categories.add_budget_category(con, household["id"], "Hidden Item", hidden=True)
    categories.add_budget_category(con, hidden_master["id"], "Hidden Master Item")

    category_rows = categories.list_transaction_categories(con)

    assert [
        (row["id"], row["master_category_name"], row["category_name"])
        for row in category_rows
    ] == [
        (expense_category["id"], "Everyday Expenses", "Other"),
        (household_category["id"], "Household", "Other"),
    ]


def test_get_budget_category_by_name_returns_matching_category(con):
    bills = categories.add_master_category(con, "Monthly Bills")
    expenses = categories.add_master_category(con, "Everyday Expenses")
    categories.add_budget_category(con, bills["id"], "Other")
    expense_category = categories.add_budget_category(con, expenses["id"], "Other")

    category = categories.get_budget_category_by_name(con, expenses["id"], "other")

    assert category["id"] == expense_category["id"]
    assert category["master_budget_category_id"] == expenses["id"]
    assert category["name"] == "Other"


def test_rename_budget_category_updates_matching_row(con):
    expenses = categories.add_master_category(con, "Everyday Expenses")
    groceries = categories.add_budget_category(
        con,
        expenses["id"],
        "Groceries",
    )

    renamed = categories.rename_budget_category(
        con,
        groceries["id"],
        "Food",
    )

    assert renamed["id"] == groceries["id"]
    assert renamed["name"] == "Food"
    assert categories.get_budget_category_by_name(
        con,
        expenses["id"],
        "Groceries",
    ) is None


def test_rename_budget_category_rejects_duplicate_within_master(con):
    expenses = categories.add_master_category(con, "Everyday Expenses")
    groceries = categories.add_budget_category(
        con,
        expenses["id"],
        "Groceries",
    )
    categories.add_budget_category(con, expenses["id"], "Dining Out")

    renamed = categories.rename_budget_category(
        con,
        groceries["id"],
        "dining out",
    )

    assert renamed is None
    assert categories.get_budget_category_by_name(
        con,
        expenses["id"],
        "Groceries",
    )["id"] == groceries["id"]


def test_rename_budget_category_allows_name_used_under_other_master(con):
    expenses = categories.add_master_category(con, "Everyday Expenses")
    household = categories.add_master_category(con, "Household")
    groceries = categories.add_budget_category(
        con,
        expenses["id"],
        "Groceries",
    )
    categories.add_budget_category(con, household["id"], "Food")

    renamed = categories.rename_budget_category(
        con,
        groceries["id"],
        "Food",
    )

    assert renamed["name"] == "Food"


def test_delete_budget_category_removes_unused_category_allocations(con):
    expenses = categories.add_master_category(con, "Everyday Expenses")
    groceries = categories.add_budget_category(
        con,
        expenses["id"],
        "Groceries",
    )
    budget_month = budgets.get_or_create_budget_month(
        con,
        "2026-07-01",
    )
    budgets.set_budget_allocation(
        con,
        budget_month["id"],
        groceries["id"],
        50000,
    )

    deleted = categories.delete_budget_category(
        con,
        groceries["id"],
    )

    assert deleted["id"] == groceries["id"]
    assert categories.list_budget_categories(con, expenses["id"]) == []
    assert budgets.list_budget_allocations(
        con,
        budget_month["id"],
    ) == []


def test_delete_budget_category_preserves_category_with_transactions(con):
    expenses = categories.add_master_category(con, "Everyday Expenses")
    groceries = categories.add_budget_category(
        con,
        expenses["id"],
        "Groceries",
    )
    budget_month = budgets.get_or_create_budget_month(
        con,
        "2026-07-01",
    )
    budgets.set_budget_allocation(
        con,
        budget_month["id"],
        groceries["id"],
        50000,
    )
    checking = accounts.create_account(con, "Checking")
    grocery_store = payees.add_payee(con, "Grocery Store")
    transactions.add_transaction(
        con,
        checking["id"],
        grocery_store["id"],
        groceries["id"],
        "2026-07-21",
        -4250,
    )

    deleted = categories.delete_budget_category(
        con,
        groceries["id"],
    )

    assert deleted is None
    assert categories.get_budget_category_by_name(
        con,
        expenses["id"],
        "Groceries",
    )["id"] == groceries["id"]
    assert len(
        budgets.list_budget_allocations(con, budget_month["id"])
    ) == 1


def test_set_budget_category_hidden_filters_and_restores_category(con):
    expenses = categories.add_master_category(con, "Everyday Expenses")
    groceries = categories.add_budget_category(
        con,
        expenses["id"],
        "Groceries",
    )

    hidden = categories.set_budget_category_hidden(
        con,
        groceries["id"],
        True,
    )

    assert hidden["hidden"] == True
    assert categories.list_budget_categories(con, expenses["id"]) == []
    assert categories.list_transaction_categories(con) == []

    restored = categories.set_budget_category_hidden(
        con,
        groceries["id"],
        False,
    )

    assert restored["hidden"] == False
    assert categories.list_budget_categories(
        con,
        expenses["id"],
    )[0]["id"] == groceries["id"]
    assert categories.list_transaction_categories(con)[0]["id"] == (
        groceries["id"]
    )


def test_get_or_create_income_category_reuses_hidden_category(con):
    # Repeated lookup preserves one stable transaction category ID
    created = categories.get_or_create_income_category(con)
    reused = categories.get_or_create_income_category(con)

    assert reused["id"] == created["id"]
    assert created["name"] == "Income"
    assert created["hidden"] == True
    assert categories.list_master_categories(con) == []
    assert categories.list_transaction_categories(con) == []
