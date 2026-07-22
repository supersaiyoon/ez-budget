from db import budgets


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
