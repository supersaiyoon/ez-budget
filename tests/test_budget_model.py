from datetime import date
from decimal import Decimal

import pytest
import budget_model

from budget_model import (
    create_empty_budget,
    create_next_month_budget,
    create_sample_accounts,
    create_sample_budget,
    create_sample_budgets,
    parse_money,
)


def test_empty_budget_starts_current_month_with_zero_values():
    budget = create_empty_budget()
    current_month = date.today().replace(day=1)

    assert budget.month_date == current_month
    assert budget.month_name == current_month.strftime("%B %Y")
    assert budget.monthly_income == Decimal("0.00")
    assert budget.master_categories == []
    assert budget.total_budgeted == Decimal("0.00")
    assert budget.total_spent == Decimal("0.00")


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


def test_next_month_budget_keeps_master_category_database_id():
    budget = create_sample_budget()
    budget.master_categories[0].database_id = 12

    next_budget = create_next_month_budget(budget)

    assert next_budget.master_categories[0].database_id == 12


def test_next_month_budget_keeps_subcategory_database_id():
    budget = create_sample_budget()
    budget.master_categories[0].subcategories[0].database_id = 24

    next_budget = create_next_month_budget(budget)
    next_subcategory = next_budget.master_categories[0].subcategories[0]

    assert next_subcategory.database_id == 24


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


def test_account_keeps_database_id():
    account = budget_model.Account("Checking", database_id=12)

    assert account.database_id == 12


def test_account_keeps_budget_and_closed_state():
    account = budget_model.Account("Tracking", on_budget=False, closed=True)

    assert account.on_budget is False
    assert account.closed is True


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


def test_transaction_amount_in_cents_makes_outgoing_negative():
    transaction = budget_model.Transaction(
        date="2026-07-14",
        payee="Grocery Store",
        category="Groceries",
        notes="",
        outgoing=Decimal("142.38"),
    )

    amount = budget_model.transaction_amount_in_cents(transaction)

    assert amount == -14238


def test_transaction_amount_in_cents_keeps_incoming_positive():
    transaction = budget_model.Transaction(
        date="2026-07-14",
        payee="Online Return",
        category="Clothing",
        notes="Refund",
        incoming=Decimal("34.99"),
    )

    amount = budget_model.transaction_amount_in_cents(transaction)

    assert amount == 3499


def test_transaction_amounts_from_cents_makes_negative_amount_outgoing():
    outgoing, incoming = budget_model.transaction_amounts_from_cents(-12345)

    assert outgoing == Decimal("123.45")
    assert incoming == Decimal("0.00")


def test_transaction_amounts_from_cents_makes_positive_amount_incoming():
    outgoing, incoming = budget_model.transaction_amounts_from_cents(12345)

    assert outgoing == Decimal("0.00")
    assert incoming == Decimal("123.45")


def test_transaction_amounts_from_cents_keeps_zero_in_both_fields():
    outgoing, incoming = budget_model.transaction_amounts_from_cents(0)

    assert outgoing == Decimal("0.00")
    assert incoming == Decimal("0.00")


def test_transaction_from_database_row_maps_outgoing_transaction():
    transaction_row = {
        "id": 17,
        "budget_category_id": 23,
        "transaction_date": "2026-07-13",
        "payee_name": "Grocery Store",
        "category_name": "Groceries",
        "notes": "weekly groceries",
        "amount": -4250,
        "cleared": 1,
    }

    transaction = budget_model.transaction_from_database_row(transaction_row)

    assert transaction.date == "2026-07-13"
    assert transaction.payee == "Grocery Store"
    assert transaction.category == "Groceries"
    assert transaction.notes == "weekly groceries"
    assert transaction.outgoing == Decimal("42.50")
    assert transaction.incoming == Decimal("0.00")
    assert transaction.cleared is True
    assert transaction.database_id == 17
    assert transaction.category_database_id == 23


def test_transaction_from_database_row_maps_incoming_transaction():
    transaction_row = {
        "id": 18,
        "budget_category_id": 24,
        "transaction_date": "2026-07-14",
        "payee_name": "Online Return",
        "category_name": "Clothing",
        "notes": None,
        "amount": 3499,
        "cleared": 0,
    }

    transaction = budget_model.transaction_from_database_row(transaction_row)

    assert transaction.notes == ""
    assert transaction.outgoing == Decimal("0.00")
    assert transaction.incoming == Decimal("34.99")
    assert transaction.cleared is False


def test_new_transaction_starts_without_database_id():
    transaction = budget_model.Transaction(
        date="2026-07-15",
        payee="Fuel Stop",
        category="Gas",
        notes="",
    )

    assert transaction.database_id is None
    assert transaction.category_database_id is None
