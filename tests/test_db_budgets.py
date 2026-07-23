from db import budgets, categories


def test_add_budget_month_inserts_month_row(con):
    budget_month = budgets.add_budget_month(con, "2026-07-01", 520000)

    assert budget_month["id"] == 1
    assert budget_month["month_date"] == "2026-07-01"
    assert budget_month["monthly_income"] == 520000


def test_get_budget_month_by_date_returns_matching_month(con):
    budgets.add_budget_month(con, "2026-07-01", 520000)
    august = budgets.add_budget_month(con, "2026-08-01", 540000)

    budget_month = budgets.get_budget_month_by_date(con, "2026-08-01")

    assert budget_month["id"] == august["id"]
    assert budget_month["monthly_income"] == 540000
    assert budgets.get_budget_month_by_date(con, "2026-09-01") is None


def test_get_or_create_budget_month_reuses_existing_and_adds_missing(con):
    existing = budgets.add_budget_month(con, "2026-07-01", 520000)

    reused = budgets.get_or_create_budget_month(con, "2026-07-01")
    created = budgets.get_or_create_budget_month(con, "2026-08-01")

    assert reused["id"] == existing["id"]
    assert created["month_date"] == "2026-08-01"
    assert created["monthly_income"] == 0
    assert con.execute("SELECT COUNT(*) FROM budget_months").fetchone()[0] == 2


def test_add_budget_allocation_inserts_category_amount(con):
    budget_month = budgets.add_budget_month(con, "2026-07-01")
    master_category = categories.add_master_category(con, "Monthly Bills")
    budget_category = categories.add_budget_category(
        con,
        master_category["id"],
        "Rent",
    )

    allocation = budgets.add_budget_allocation(
        con,
        budget_month["id"],
        budget_category["id"],
        185000,
    )

    assert allocation["id"] == 1
    assert allocation["budget_month_id"] == budget_month["id"]
    assert allocation["budget_category_id"] == budget_category["id"]
    assert allocation["amount"] == 185000
