from db import budgets


def test_add_budget_month_inserts_month_row(con):
    budget_month = budgets.add_budget_month(con, "2026-07-01", 520000)

    assert budget_month["id"] == 1
    assert budget_month["month_date"] == "2026-07-01"
    assert budget_month["monthly_income"] == 520000
