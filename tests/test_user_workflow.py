from decimal import Decimal

import pytest

import budget_model
from ui.main_window import MainWindow


# Workflow test creates Qt pages while exercising one persistent database
pytestmark = pytest.mark.usefixtures("qapp")


def test_fresh_budget_workflow_survives_restart(tmp_path):
    db_path = tmp_path / "budget.db"
    window = MainWindow(db_path)

    # User setup creates category, funded account, and monthly assignment
    window.add_master_category("Monthly Bills")
    master_category = window.budgets[0].master_categories[0]
    window.add_subcategory(master_category.database_id, "Rent")
    rent = master_category.subcategories[0]
    window.add_account(
        "Checking",
        opening_balance=Decimal("2500.00"),
    )
    budget = window.budgets[0]
    rent.budgeted = Decimal("1000.00")
    window.budget_allocation_changed(budget, rent)

    # Spending flows from account transaction into Budget and Reports totals
    account = window.accounts[0]
    rent_transaction = budget_model.Transaction(
        date=budget.month_date.isoformat(),
        payee="Landlord",
        category="Rent",
        notes="monthly rent",
        outgoing=Decimal("800.00"),
        category_database_id=rent.database_id,
    )
    account.transactions.append(rent_transaction)
    assert window.save_transaction(account, rent_transaction) is True
    window.refresh_reports()

    assert account.working_balance == Decimal("1700.00")
    assert budget.monthly_income == Decimal("2500.00")
    assert rent.spent == Decimal("800.00")
    assert rent.remaining == Decimal("200.00")
    assert window.reports_page.table.item(0, 4).text() == "$200.00"

    # Close and reopen preserves active workflow before application restart
    assert window.close_account(account) is True
    assert window.reopen_account(account) is True
    window.close()
    window.con.close()

    reopened_window = MainWindow(db_path)
    reopened_budget = reopened_window.budgets[0]
    reopened_rent = reopened_budget.master_categories[0].subcategories[0]
    reopened_account = reopened_window.accounts[0]

    assert reopened_account.name == "Checking"
    assert reopened_account.working_balance == Decimal("1700.00")
    assert reopened_budget.monthly_income == Decimal("2500.00")
    assert reopened_rent.budgeted == Decimal("1000.00")
    assert reopened_rent.spent == Decimal("800.00")
    assert reopened_rent.remaining == Decimal("200.00")
    assert reopened_window.reports_page.table.item(0, 4).text() == "$200.00"
