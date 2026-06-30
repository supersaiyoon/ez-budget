from decimal import Decimal

import pytest

from budget_model import (
    create_next_month_budget,
    create_sample_accounts,
    create_sample_budget,
    create_sample_budgets,
    parse_money,
)


def test_positive_adjustment_increases_budget_and_reduces_available():
    budget = create_sample_budget()
    starting_budgeted = budget.total_budgeted
    starting_available = budget.available_to_budget

    # Positive adjustment should consume unassigned income
    budget.apply_adjustment("Everyday Spending", "Groceries", "100")

    assert budget.total_budgeted == starting_budgeted + Decimal("100.00")
    assert budget.available_to_budget == starting_available - Decimal("100.00")


def test_negative_adjustment_reduces_budget_and_increases_available():
    budget = create_sample_budget()
    starting_budgeted = budget.total_budgeted
    starting_available = budget.available_to_budget

    # Negative adjustment should free dollars back to available pool
    budget.apply_adjustment("Monthly Bills", "Water", "-25")

    assert budget.total_budgeted == starting_budgeted - Decimal("25.00")
    assert budget.available_to_budget == starting_available + Decimal("25.00")


def test_remaining_amount_equals_budgeted_minus_spent():
    budget = create_sample_budget()
    groceries = budget.get_subcategory("Everyday Spending", "Groceries")

    assert groceries.remaining == groceries.budgeted - groceries.spent


def test_invalid_input_is_rejected_without_changing_state():
    budget = create_sample_budget()
    starting_budgeted = budget.total_budgeted

    # Failed parse must leave the budget untouched
    with pytest.raises(ValueError):
        budget.apply_adjustment("Savings", "Vacation", "abc")

    assert budget.total_budgeted == starting_budgeted


def test_category_totals_roll_up_from_subcategories():
    budget = create_sample_budget()
    monthly_bills = budget.master_categories[0]

    # Expected values calculated independently from model properties
    expected_budgeted = sum(item.budgeted for item in monthly_bills.subcategories)
    expected_spent = sum(item.spent for item in monthly_bills.subcategories)

    assert monthly_bills.budgeted == expected_budgeted
    assert monthly_bills.spent == expected_spent
    assert monthly_bills.remaining == expected_budgeted - expected_spent


def test_parse_money_accepts_currency_formatting():
    assert parse_money("$1,234.5") == Decimal("1234.50")


def test_sample_budgets_include_multiple_months():
    budgets = create_sample_budgets()

    # Date range gives UI month comparison enough data to render
    assert len(budgets) > 2
    assert budgets[0].month_name == "March 2026"
    assert budgets[-1].month_name == "August 2026"


def test_adjusting_one_month_does_not_change_another_month():
    budgets = create_sample_budgets()
    april = budgets[1]
    may = budgets[2]
    starting_april_budgeted = april.total_budgeted
    starting_may_budgeted = may.total_budgeted

    # Month objects should not share category or subcategory instances
    may.apply_adjustment("Savings", "Vacation", "75")

    assert may.total_budgeted == starting_may_budgeted + Decimal("75.00")
    assert april.total_budgeted == starting_april_budgeted


def test_next_month_budget_advances_month_and_keeps_categories():
    budgets = create_sample_budgets()
    next_budget = create_next_month_budget(budgets[-1])

    # Generated month needs same budget shape for the table to keep working
    assert next_budget.month_name == "September 2026"
    assert next_budget.monthly_income == budgets[-1].monthly_income
    assert [category.name for category in next_budget.master_categories] == [
        category.name for category in budgets[-1].master_categories
    ]


def test_next_month_budget_starts_unbudgeted_and_unspent():
    next_budget = create_next_month_budget(create_sample_budgets()[-1])

    # New month should start as a fresh planning period
    assert next_budget.total_budgeted == Decimal("0.00")
    assert next_budget.total_spent == Decimal("0.00")
    assert next_budget.available_to_budget == next_budget.monthly_income


def test_sample_accounts_include_checking_and_credit_card():
    accounts = create_sample_accounts()

    assert [account.name for account in accounts] == ["Checking", "Credit Card"]
    assert accounts[0].transactions
    assert accounts[1].transactions


def test_account_balances_use_incoming_minus_outgoing():
    checking = create_sample_accounts()[0]

    # Expected balances mirror accounting direction without using Account properties
    expected_working = sum(
        transaction.incoming - transaction.outgoing for transaction in checking.transactions
    )
    expected_cleared = sum(
        transaction.incoming - transaction.outgoing
        for transaction in checking.transactions
        if transaction.cleared
    )

    assert checking.working_balance == expected_working
    assert checking.cleared_balance == expected_cleared
