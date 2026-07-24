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


def test_list_budget_allocations_returns_only_requested_month(con):
    july = budgets.add_budget_month(con, "2026-07-01")
    august = budgets.add_budget_month(con, "2026-08-01")
    master_category = categories.add_master_category(con, "Monthly Bills")
    rent = categories.add_budget_category(
        con,
        master_category["id"],
        "Rent",
    )
    utilities = categories.add_budget_category(
        con,
        master_category["id"],
        "Utilities",
    )
    july_rent = budgets.add_budget_allocation(
        con,
        july["id"],
        rent["id"],
        185000,
    )
    july_utilities = budgets.add_budget_allocation(
        con,
        july["id"],
        utilities["id"],
        25000,
    )
    budgets.add_budget_allocation(
        con,
        august["id"],
        rent["id"],
        190000,
    )

    allocations = budgets.list_budget_allocations(con, july["id"])

    assert [allocation["id"] for allocation in allocations] == [
        july_rent["id"],
        july_utilities["id"],
    ]
    assert [allocation["budget_category_id"] for allocation in allocations] == [
        rent["id"],
        utilities["id"],
    ]
    assert [allocation["amount"] for allocation in allocations] == [
        185000,
        25000,
    ]


def test_update_budget_allocation_replaces_only_matching_amount(con):
    budget_month = budgets.add_budget_month(con, "2026-07-01")
    master_category = categories.add_master_category(con, "Monthly Bills")
    rent = categories.add_budget_category(
        con,
        master_category["id"],
        "Rent",
    )
    utilities = categories.add_budget_category(
        con,
        master_category["id"],
        "Utilities",
    )
    rent_allocation = budgets.add_budget_allocation(
        con,
        budget_month["id"],
        rent["id"],
        185000,
    )
    budgets.add_budget_allocation(
        con,
        budget_month["id"],
        utilities["id"],
        25000,
    )

    updated = budgets.update_budget_allocation(
        con,
        budget_month["id"],
        rent["id"],
        190000,
    )
    allocations = budgets.list_budget_allocations(con, budget_month["id"])

    assert updated["id"] == rent_allocation["id"]
    assert updated["amount"] == 190000
    assert [allocation["amount"] for allocation in allocations] == [
        190000,
        25000,
    ]


def test_set_budget_allocation_updates_existing_and_inserts_missing(con):
    budget_month = budgets.add_budget_month(con, "2026-07-01")
    master_category = categories.add_master_category(con, "Monthly Bills")
    rent = categories.add_budget_category(
        con,
        master_category["id"],
        "Rent",
    )
    utilities = categories.add_budget_category(
        con,
        master_category["id"],
        "Utilities",
    )
    existing = budgets.add_budget_allocation(
        con,
        budget_month["id"],
        rent["id"],
        185000,
    )

    updated = budgets.set_budget_allocation(
        con,
        budget_month["id"],
        rent["id"],
        190000,
    )
    created = budgets.set_budget_allocation(
        con,
        budget_month["id"],
        utilities["id"],
        25000,
    )

    assert updated["id"] == existing["id"]
    assert updated["amount"] == 190000
    assert created["budget_category_id"] == utilities["id"]
    assert created["amount"] == 25000
    assert con.execute("SELECT COUNT(*) FROM budget_allocations").fetchone()[0] == 2
