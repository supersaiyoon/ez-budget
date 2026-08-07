from datetime import date
from decimal import Decimal

import pytest

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QInputDialog,
    QMessageBox,
    QPushButton,
)

import budget_model
from db import accounts, budgets, categories, database, payees, transactions
from ui import payees_dialog
from ui.main_window import AccountDialog, MainWindow


# Every test in this module creates Qt widgets and requires the shared application
pytestmark = pytest.mark.usefixtures("qapp")


def navigation_text_rows(window):
    # Embedded button rows have empty item text
    return [
        window.nav.item(row).text()
        for row in range(window.nav.count())
        if window.nav.item(row).text()
    ]


def test_new_window_leaves_account_table_empty():
    window = MainWindow(":memory:")

    assert accounts.has_accounts(window.con) == False


def test_new_window_initializes_hidden_income_category():
    window = MainWindow(":memory:")

    # Controller retains ID while visible Budget category list stays empty
    income_category = categories.get_or_create_income_category(window.con)

    assert window.income_category_id == income_category["id"]
    assert categories.list_master_categories(window.con) == []
    assert window.budgets[0].master_categories == []


def test_new_window_loads_hidden_category_rows(tmp_path):
    db_path = tmp_path / "budget.db"
    con = database.connect(db_path)
    database.initialize_database(con)
    visible_master = categories.add_master_category(
        con,
        "Everyday Expenses",
    )
    hidden_subcategory = categories.add_budget_category(
        con,
        visible_master["id"],
        "Groceries",
        hidden=True,
    )
    budget_month = budgets.get_or_create_budget_month(
        con,
        date.today().replace(day=1).isoformat(),
    )
    budgets.set_budget_allocation(
        con,
        budget_month["id"],
        hidden_subcategory["id"],
        50000,
    )
    checking = accounts.create_account(con, "Checking")
    grocery_store = payees.add_payee(con, "Grocery Store")
    transactions.add_transaction(
        con,
        checking["id"],
        grocery_store["id"],
        hidden_subcategory["id"],
        date.today().isoformat(),
        -4250,
    )
    hidden_master = categories.add_master_category(
        con,
        "Archived Goals",
        hidden=True,
    )
    categories.add_budget_category(
        con,
        hidden_master["id"],
        "Old Goal",
    )
    con.close()

    window = MainWindow(db_path)

    assert [
        row["name"] for row in window.hidden_master_category_rows
    ] == ["Archived Goals"]
    assert [
        row["name"] for row in window.hidden_subcategory_rows
    ] == ["Groceries"]
    assert window.hidden_subcategory_rows[0][
        "master_category_name"
    ] == "Everyday Expenses"
    assert window.budget_page.hidden_master_category_rows == (
        window.hidden_master_category_rows
    )
    assert window.budget_page.hidden_subcategory_rows == (
        window.hidden_subcategory_rows
    )
    assert window.budgets[0].master_categories[0].subcategories == []
    assert window.budgets[0].hidden_budgeted == Decimal("500.00")
    assert window.budgets[0].hidden_spent == Decimal("42.50")
    assert window.budgets[0].total_budgeted == Decimal("500.00")
    assert window.budgets[0].total_spent == Decimal("42.50")


def test_hidden_master_restore_button_restores_group(tmp_path):
    db_path = tmp_path / "budget.db"
    con = database.connect(db_path)
    database.initialize_database(con)
    hidden_master = categories.add_master_category(
        con,
        "Archived Goals",
        hidden=True,
    )
    subcategory = categories.add_budget_category(
        con,
        hidden_master["id"],
        "Old Goal",
    )
    con.close()

    window = MainWindow(db_path)
    window.add_account("Checking")
    restore_button = window.budget_page.findChild(
        QPushButton,
        "restoreMasterCategoryButton",
    )

    restore_button.click()

    assert all(
        [
            category.database_id
            for category in budget.master_categories
        ] == [hidden_master["id"]]
        for budget in window.budgets
    )
    assert all(
        budget.master_categories[0].subcategories[0].database_id
        == subcategory["id"]
        for budget in window.budgets
    )
    assert categories.get_master_category_by_name(
        window.con,
        "Archived Goals",
    )["hidden"] == False
    assert window.hidden_master_category_rows == []
    assert window.transaction_pages[0].category_rows[0][
        "category_name"
    ] == "Old Goal"
    assert window.budget_page.feedback.text() == (
        'Restored master category "Archived Goals".'
    )


def test_hidden_subcategory_restore_button_restores_category(tmp_path):
    db_path = tmp_path / "budget.db"
    con = database.connect(db_path)
    database.initialize_database(con)
    master_category = categories.add_master_category(
        con,
        "Everyday Expenses",
    )
    hidden_subcategory = categories.add_budget_category(
        con,
        master_category["id"],
        "Groceries",
        hidden=True,
    )
    con.close()

    window = MainWindow(db_path)
    window.add_account("Checking")
    restore_button = window.budget_page.findChild(
        QPushButton,
        "restoreSubcategoryButton",
    )

    restore_button.click()

    assert all(
        budget.master_categories[0].subcategories[0].database_id
        == hidden_subcategory["id"]
        for budget in window.budgets
    )
    assert categories.get_budget_category_by_name(
        window.con,
        master_category["id"],
        "Groceries",
    )["hidden"] == False
    assert window.hidden_subcategory_rows == []
    assert window.transaction_pages[0].category_rows[0][
        "category_name"
    ] == "Groceries"
    assert window.budget_page.feedback.text() == (
        'Restored subcategory "Groceries".'
    )


def test_new_window_loads_saved_account_details(tmp_path):
    db_path = tmp_path / "budget.db"
    con = database.connect(db_path)
    database.initialize_database(con)
    saved_account = accounts.create_account(con, "Tracking", on_budget=False)
    accounts.create_account(con, "Checking")
    con.close()

    window = MainWindow(db_path)
    loaded_account = window.accounts[1]

    assert [account.name for account in window.accounts] == ["Checking", "Tracking"]
    assert loaded_account.name == "Tracking"
    assert loaded_account.database_id == saved_account["id"]
    assert loaded_account.on_budget is False
    assert loaded_account.closed is False
    assert (
        window.transaction_pages[0].on_transaction_changed
        == window.save_transaction
    )
    assert (
        window.transaction_pages[0].on_transaction_delete_requested
        == window.delete_transaction
    )


def test_new_window_loads_saved_transactions_into_account(tmp_path):
    db_path = tmp_path / "budget.db"
    con = database.connect(db_path)
    database.initialize_database(con)
    checking = accounts.create_account(con, "Checking")
    payee = payees.add_payee(con, "Grocery Store")
    master_category = categories.add_master_category(con, "Everyday Expenses")
    category = categories.add_budget_category(con, master_category["id"], "Groceries")
    savings = categories.add_master_category(con, "Savings")
    categories.add_budget_category(con, savings["id"], "Vacation")
    saved_transaction = transactions.add_transaction(
        con,
        checking["id"],
        payee["id"],
        category["id"],
        "2026-07-13",
        -4250,
        "weekly groceries",
        cleared=True,
    )
    con.close()

    window = MainWindow(db_path)
    loaded_transaction = window.accounts[0].transactions[0]

    assert loaded_transaction.date == "2026-07-13"
    assert loaded_transaction.payee == "Grocery Store"
    assert loaded_transaction.category == "Groceries"
    assert loaded_transaction.notes == "weekly groceries"
    assert loaded_transaction.outgoing == Decimal("42.50")
    assert loaded_transaction.incoming == Decimal("0.00")
    assert loaded_transaction.cleared is True
    assert loaded_transaction.database_id == saved_transaction["id"]
    assert window.transaction_pages[0].table.rowCount() == 2
    category_input = window.transaction_pages[0].table.cellWidget(0, 2)
    # Dated rows include virtual income choices before normal category suggestions
    assert [category_input.itemText(index) for index in range(category_input.count())] == [
        "Income for this month",
        "Income for next month",
        "Groceries",
        "Vacation",
    ]
    assert category_input.currentText() == "Groceries"
    assert category_input.currentData()["database_id"] == category["id"]


def test_new_window_loads_current_month_transaction_spending(tmp_path):
    db_path = tmp_path / "budget.db"
    con = database.connect(db_path)
    database.initialize_database(con)
    checking = accounts.create_account(con, "Checking")
    payee = payees.add_payee(con, "Grocery Store")
    master_category = categories.add_master_category(con, "Everyday Expenses")
    category = categories.add_budget_category(con, master_category["id"], "Groceries")
    transactions.add_transaction(
        con,
        checking["id"],
        payee["id"],
        category["id"],
        date.today().replace(day=1).isoformat(),
        -4250,
    )
    con.close()

    window = MainWindow(db_path)
    groceries = window.budgets[0].master_categories[0].subcategories[0]

    assert groceries.spent == Decimal("42.50")


def test_save_transaction_inserts_then_updates_same_database_row():
    window = MainWindow(":memory:")
    window.add_master_category("Everyday Expenses")
    master_category_id = window.budgets[0].master_categories[0].database_id
    window.add_subcategory(master_category_id, "Groceries")
    category_id = (
        window.budgets[0].master_categories[0].subcategories[0].database_id
    )
    window.add_account("Checking")
    transaction = budget_model.Transaction(
        date="2026-07-21",
        payee="Grocery Store",
        category="Groceries",
        notes="weekly groceries",
        outgoing=Decimal("42.50"),
        category_database_id=category_id,
    )

    first_save = window.save_transaction(window.accounts[0], transaction)
    transaction.payee = "Fuel Stop"
    transaction.notes = "fuel purchase"
    transaction.outgoing = Decimal("58.99")
    transaction.cleared = True
    second_save = window.save_transaction(window.accounts[0], transaction)
    saved_rows = transactions.list_transactions(
        window.con,
        window.accounts[0].database_id,
    )

    assert first_save is True
    assert second_save is True
    assert transaction.database_id == saved_rows[0]["id"]
    assert saved_rows[0]["payee_name"] == "Fuel Stop"
    assert saved_rows[0]["amount"] == -5899
    assert saved_rows[0]["notes"] == "fuel purchase"
    assert saved_rows[0]["cleared"] == True
    assert len(saved_rows) == 1


def test_delete_transaction_removes_saved_row_and_account_model():
    window = MainWindow(":memory:")
    window.add_master_category("Everyday Expenses")
    master_category_id = window.budgets[0].master_categories[0].database_id
    window.add_subcategory(master_category_id, "Groceries")
    category_id = (
        window.budgets[0].master_categories[0].subcategories[0].database_id
    )
    groceries = window.budgets[0].master_categories[0].subcategories[0]
    window.add_account("Checking")
    account = window.accounts[0]
    transaction = budget_model.Transaction(
        date=window.budgets[0].month_date.isoformat(),
        payee="Grocery Store",
        category="Groceries",
        notes="",
        outgoing=Decimal("42.50"),
        category_database_id=category_id,
    )
    account.transactions.append(transaction)
    window.save_transaction(account, transaction)
    assert groceries.spent == Decimal("42.50")

    deleted = window.delete_transaction(account, transaction)

    assert deleted is True
    assert account.transactions == []
    assert transactions.list_transactions(window.con, account.database_id) == []
    assert groceries.spent == Decimal("0.00")


def test_delete_transaction_refreshes_assigned_income():
    window = MainWindow(":memory:")
    window.add_account("Checking")
    account = window.accounts[0]
    budget = window.budgets[0]
    transaction = budget_model.Transaction(
        date=budget.month_date.isoformat(),
        payee="Employer",
        category="Income for this month",
        notes="",
        incoming=Decimal("2000.00"),
        category_database_id=window.income_category_id,
        income_month_date=budget.month_date.isoformat(),
    )
    account.transactions.append(transaction)
    window.save_transaction(account, transaction)
    assert budget.monthly_income == Decimal("2000.00")

    window.delete_transaction(account, transaction)

    assert budget.monthly_income == Decimal("0.00")


def test_confirmed_transaction_delete_survives_restart(tmp_path, monkeypatch):
    db_path = tmp_path / "budget.db"
    window = MainWindow(db_path)
    window.add_master_category("Everyday Expenses")
    master_category_id = window.budgets[0].master_categories[0].database_id
    window.add_subcategory(master_category_id, "Groceries")
    groceries = window.budgets[0].master_categories[0].subcategories[0]
    window.add_account("Checking")
    account = window.accounts[0]
    transaction = budget_model.Transaction(
        date=window.budgets[0].month_date.isoformat(),
        payee="Grocery Store",
        category="Groceries",
        notes="",
        outgoing=Decimal("42.50"),
        category_database_id=groceries.database_id,
    )
    account.transactions.append(transaction)
    window.save_transaction(account, transaction)
    window.close()
    window.con.close()

    # Startup-loaded account page sends confirmed deletion through controller
    reopened_window = MainWindow(db_path)
    reopened_account = reopened_window.accounts[0]
    reopened_page = reopened_window.transaction_pages[0]
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args: QMessageBox.StandardButton.Yes,
    )

    reopened_page.table.cellWidget(0, 7).findChild(QPushButton).click()

    assert reopened_account.transactions == []
    assert reopened_page.table.rowCount() == 1
    assert transactions.list_transactions(
        reopened_window.con,
        reopened_account.database_id,
    ) == []

    reopened_window.close()
    reopened_window.con.close()

    final_window = MainWindow(db_path)

    assert final_window.accounts[0].transactions == []


def test_save_transaction_inserts_income_target_month():
    window = MainWindow(":memory:")
    window.add_account("Checking")
    transaction = budget_model.Transaction(
        date="2026-07-25",
        payee="Employer",
        category="Income for next month",
        notes="",
        incoming=Decimal("2000.00"),
        category_database_id=window.income_category_id,
        income_month_date="2026-08-01",
    )

    # Insert branch preserves hidden category and concrete target month
    saved = window.save_transaction(window.accounts[0], transaction)
    saved_row = transactions.list_transactions(
        window.con,
        window.accounts[0].database_id,
    )[0]

    assert saved is True
    assert saved_row["budget_category_id"] == window.income_category_id
    assert saved_row["income_month_date"] == "2026-08-01"


def test_save_transaction_refreshes_income_after_insert():
    window = MainWindow(":memory:")
    window.add_account("Checking")
    current_budget = window.budgets[0]
    next_budget = window.budgets[1]
    transaction = budget_model.Transaction(
        date=current_budget.month_date.isoformat(),
        payee="Employer",
        category="Income for next month",
        notes="",
        incoming=Decimal("2000.00"),
        category_database_id=window.income_category_id,
        income_month_date=next_budget.month_date.isoformat(),
    )

    window.save_transaction(window.accounts[0], transaction)

    assert current_budget.monthly_income == Decimal("0.00")
    assert next_budget.monthly_income == Decimal("2000.00")


def test_previous_month_navigation_loads_saved_income():
    window = MainWindow(":memory:")
    window.add_account("Checking")
    previous_month = budget_model.previous_month(window.budgets[0].month_date)
    transaction = budget_model.Transaction(
        date=previous_month.isoformat(),
        payee="Employer",
        category="Income for this month",
        notes="",
        incoming=Decimal("2000.00"),
        category_database_id=window.income_category_id,
        income_month_date=previous_month.isoformat(),
    )

    window.save_transaction(window.accounts[0], transaction)
    window.budget_page.month_scroller.previous_button.click()

    assert window.budgets[0].month_date == previous_month
    assert window.budgets[0].monthly_income == Decimal("2000.00")


def test_save_transaction_updates_income_target_month():
    window = MainWindow(":memory:")
    window.add_account("Checking")
    current_budget = window.budgets[0]
    next_budget = window.budgets[1]
    transaction = budget_model.Transaction(
        date=current_budget.month_date.isoformat(),
        payee="Employer",
        category="Income for this month",
        notes="",
        incoming=Decimal("2000.00"),
        category_database_id=window.income_category_id,
        income_month_date=current_budget.month_date.isoformat(),
    )
    window.save_transaction(window.accounts[0], transaction)
    saved_database_id = transaction.database_id

    # Updated assignment keeps original transaction row
    transaction.category = "Income for next month"
    transaction.income_month_date = next_budget.month_date.isoformat()
    window.save_transaction(window.accounts[0], transaction)
    saved_rows = transactions.list_transactions(
        window.con,
        window.accounts[0].database_id,
    )

    assert len(saved_rows) == 1
    assert saved_rows[0]["id"] == saved_database_id
    assert saved_rows[0]["income_month_date"] == next_budget.month_date.isoformat()
    assert current_budget.monthly_income == Decimal("0.00")
    assert next_budget.monthly_income == Decimal("2000.00")


def test_save_transaction_waits_for_required_fields():
    window = MainWindow(":memory:")
    window.add_account("Checking")
    transaction = budget_model.Transaction(
        date="2026-07-21",
        payee="Grocery Store",
        category="",
        notes="",
        outgoing=Decimal("42.50"),
    )

    saved = window.save_transaction(window.accounts[0], transaction)

    assert saved is False
    assert transaction.database_id is None
    assert transactions.has_transactions(window.con) is False


def test_load_budget_income_applies_assigned_transaction_total():
    window = MainWindow(":memory:")
    window.add_account("Checking")
    budget = window.budgets[0]
    transaction = budget_model.Transaction(
        date=budget.month_date.isoformat(),
        payee="Employer",
        category="Income for this month",
        notes="",
        incoming=Decimal("2000.00"),
        category_database_id=window.income_category_id,
        income_month_date=budget.month_date.isoformat(),
    )
    window.save_transaction(window.accounts[0], transaction)
    budget.monthly_income = Decimal("99.00")

    window.load_budget_income(budget)

    assert budget.monthly_income == Decimal("2000.00")


def test_load_budget_allocations_applies_requested_month_amount():
    window = MainWindow(":memory:")
    window.add_master_category("Monthly Bills")
    master_category_id = window.budgets[0].master_categories[0].database_id
    window.add_subcategory(master_category_id, "Rent")
    next_budget = window.budgets[1]
    next_rent = next_budget.master_categories[0].subcategories[0]
    budget_month = budgets.get_or_create_budget_month(
        window.con,
        next_budget.month_date.isoformat(),
    )
    budgets.set_budget_allocation(
        window.con,
        budget_month["id"],
        next_rent.database_id,
        185000,
    )

    window.load_budget_allocations(next_budget)

    assert next_rent.budgeted == Decimal("1850.00")


def test_refresh_budget_income_updates_each_generated_month():
    window = MainWindow(":memory:")
    window.add_account("Checking")
    current_budget = window.budgets[0]
    next_budget = window.budgets[1]
    current_income = budget_model.Transaction(
        date=current_budget.month_date.isoformat(),
        payee="Employer",
        category="Income for this month",
        notes="",
        incoming=Decimal("2000.00"),
        category_database_id=window.income_category_id,
        income_month_date=current_budget.month_date.isoformat(),
    )
    next_income = budget_model.Transaction(
        date=current_budget.month_date.isoformat(),
        payee="Employer",
        category="Income for next month",
        notes="",
        incoming=Decimal("750.00"),
        category_database_id=window.income_category_id,
        income_month_date=next_budget.month_date.isoformat(),
    )
    window.save_transaction(window.accounts[0], current_income)
    window.save_transaction(window.accounts[0], next_income)
    current_budget.monthly_income = Decimal("99.00")
    next_budget.monthly_income = Decimal("99.00")

    window.refresh_budget_income()

    assert current_budget.monthly_income == Decimal("2000.00")
    assert next_budget.monthly_income == Decimal("750.00")


def test_load_budget_spending_applies_month_transaction_totals():
    window = MainWindow(":memory:")
    window.add_master_category("Everyday Expenses")
    master_category = window.budgets[0].master_categories[0]
    window.add_subcategory(master_category.database_id, "Groceries")
    groceries = master_category.subcategories[0]
    window.add_account("Checking")
    transaction = budget_model.Transaction(
        date=window.budgets[0].month_date.isoformat(),
        payee="Grocery Store",
        category="Groceries",
        notes="",
        outgoing=Decimal("42.50"),
        category_database_id=groceries.database_id,
    )
    window.save_transaction(window.accounts[0], transaction)
    groceries.spent = Decimal("99.00")

    window.load_budget_spending(window.budgets[0])

    assert groceries.spent == Decimal("42.50")


def test_budget_navigation_refreshes_transaction_spending():
    window = MainWindow(":memory:")
    window.add_master_category("Everyday Expenses")
    master_category = window.budgets[0].master_categories[0]
    window.add_subcategory(master_category.database_id, "Groceries")
    groceries = master_category.subcategories[0]
    window.add_account("Checking")
    transaction = budget_model.Transaction(
        date=window.budgets[0].month_date.isoformat(),
        payee="Grocery Store",
        category="Groceries",
        notes="",
        outgoing=Decimal("42.50"),
        category_database_id=groceries.database_id,
    )
    groceries_row = window.budget_page.rows.index(
        ("Everyday Expenses", "Groceries")
    ) + 2

    window.save_transaction(window.accounts[0], transaction)
    assert groceries.spent == Decimal("42.50")
    assert window.budget_page.table.item(groceries_row, 2).text() == "$0.00"

    window.show_navigation_page(0)
    assert window.budget_page.table.item(groceries_row, 2).text() == "-$42.50"

    transaction.outgoing = Decimal("58.99")
    window.save_transaction(window.accounts[0], transaction)
    assert groceries.spent == Decimal("58.99")
    assert window.budget_page.table.item(groceries_row, 2).text() == "-$42.50"

    window.show_navigation_page(0)
    assert window.budget_page.table.item(groceries_row, 2).text() == "-$58.99"


def test_report_navigation_refreshes_transaction_spending():
    window = MainWindow(":memory:")
    window.add_master_category("Everyday Expenses")
    master_category = window.budgets[0].master_categories[0]
    window.add_subcategory(master_category.database_id, "Groceries")
    groceries = master_category.subcategories[0]
    window.add_account("Checking")
    transaction = budget_model.Transaction(
        date=window.budgets[0].month_date.isoformat(),
        payee="Grocery Store",
        category="Groceries",
        notes="",
        outgoing=Decimal("42.50"),
        category_database_id=groceries.database_id,
    )

    window.accounts[0].transactions.append(transaction)
    window.save_transaction(window.accounts[0], transaction)
    assert window.reports_page.table.item(0, 3).text() == "$0.00"
    assert window.reports_page.transaction_data.empty is True

    window.show_navigation_page(1)

    assert window.reports_page.table.item(0, 3).text() == "$42.50"
    assert window.reports_page.accounts is window.accounts
    assert window.reports_page.transaction_data["amount_cents"].tolist() == [-4250]


def test_budget_navigation_displays_refreshed_income():
    window = MainWindow(":memory:")
    window.add_account("Checking")
    budget = window.budgets[0]
    transaction = budget_model.Transaction(
        date=budget.month_date.isoformat(),
        payee="Employer",
        category="Income for this month",
        notes="",
        incoming=Decimal("2000.00"),
        category_database_id=window.income_category_id,
        income_month_date=budget.month_date.isoformat(),
    )

    window.save_transaction(window.accounts[0], transaction)

    # Hidden Budget table keeps prior header until navigation requests repaint
    stale_header = window.budget_page.table.item(0, 1).text()
    assert "Income: $0.00" in stale_header

    window.show_navigation_page(0)

    refreshed_header = window.budget_page.table.item(0, 1).text()
    assert "Income: $2,000.00" in refreshed_header
    assert "Available: $2,000.00" in refreshed_header


def test_grid_transaction_is_saved_and_reloaded(tmp_path, qapp):
    db_path = tmp_path / "budget.db"
    con = database.connect(db_path)
    database.initialize_database(con)
    master_category = categories.add_master_category(con, "Everyday Expenses")
    category = categories.add_budget_category(con, master_category["id"], "Groceries")
    con.close()

    window = MainWindow(db_path)
    window.add_account("Checking")
    page = window.transaction_pages[0]
    current_year = date.today().year
    stored_date = f"{current_year}-07-21"
    display_date = f"07/21/{current_year}"

    # Short date creates partial transaction with normalized storage value
    date_input = page.table.cellWidget(0, 0)
    date_input.setText("7/21")
    date_input.editingFinished.emit()
    transaction = window.accounts[0].transactions[0]
    assert transaction.database_id is None
    assert transaction.date == stored_date
    assert page.table.cellWidget(0, 0).text() == display_date

    # Remaining required editors complete transaction; Enter triggers persistence
    payee_input = page.table.cellWidget(0, 1)
    payee_input.setText("Grocery Store")
    payee_input.editingFinished.emit()
    category_input = page.table.cellWidget(0, 2)
    category_input.setCurrentIndex(category_input.findText("Groceries"))
    outgoing_input = page.table.cellWidget(0, 4)
    outgoing_input.setText("42.50")
    outgoing_input.returnPressed.emit()
    outgoing_input.editingFinished.emit()
    qapp.processEvents()

    saved_database_id = transaction.database_id
    assert saved_database_id is not None
    saved_row = transactions.list_transactions(
        window.con,
        window.accounts[0].database_id,
    )[0]
    assert saved_row["transaction_date"] == stored_date

    # Post-save checkbox change must update existing database row
    cleared_container = page.table.cellWidget(0, 6)
    cleared_input = cleared_container.findChild(QCheckBox)
    cleared_input.setChecked(True)
    assert transaction.cleared is True

    window.close()
    window.con.close()

    # Fresh window must rebuild same transaction and account balance from SQLite
    reopened_window = MainWindow(db_path)
    reloaded_transaction = reopened_window.accounts[0].transactions[0]

    assert reloaded_transaction.database_id == saved_database_id
    assert reloaded_transaction.date == stored_date
    reopened_date_input = reopened_window.transaction_pages[0].table.cellWidget(
        0,
        0,
    )
    assert reopened_date_input.text() == display_date
    assert reloaded_transaction.payee == "Grocery Store"
    assert reloaded_transaction.category_database_id == category["id"]
    assert reloaded_transaction.outgoing == Decimal("42.50")
    assert reloaded_transaction.cleared is True
    assert reopened_window.accounts[0].working_balance == Decimal("-42.50")
    assert reopened_window.accounts[0].cleared_balance == Decimal("-42.50")


def test_saved_new_payee_refreshes_transaction_autocomplete(tmp_path):
    db_path = tmp_path / "budget.db"
    con = database.connect(db_path)
    database.initialize_database(con)
    master_category = categories.add_master_category(con, "Everyday Expenses")
    categories.add_budget_category(con, master_category["id"], "Groceries")
    con.close()

    window = MainWindow(db_path)
    window.add_account("Checking")
    page = window.transaction_pages[0]
    page.create_transaction(
        date="2026-07-21",
        payee="Grocery Store",
        category="Groceries",
        outgoing=Decimal("42.50"),
        category_database_id=categories.list_transaction_categories(
            window.con
        )[0]["id"],
    )
    payee_input = page.table.cellWidget(0, 1)
    model = payee_input.completer().model()

    assert [
        model.index(row, 0).data()
        for row in range(model.rowCount())
    ] == ["Grocery Store"]


def test_grid_income_without_payee_updates_budget_and_survives_restart(tmp_path, qapp):
    db_path = tmp_path / "budget.db"
    window = MainWindow(db_path)
    window.add_account("Checking")
    page = window.transaction_pages[0]
    current_date = date.today()
    short_date = f"{current_date.month}/21"
    stored_date = date(
        current_date.year,
        current_date.month,
        21,
    ).isoformat()

    date_input = page.table.cellWidget(0, 0)
    date_input.setText(short_date)
    date_input.editingFinished.emit()
    transaction = window.accounts[0].transactions[0]

    category_input = page.table.cellWidget(0, 2)
    category_input.setCurrentText("Income for this month")
    assert transaction.payee == "Not needed for income"

    incoming_input = page.table.cellWidget(0, 5)
    incoming_input.setText("2000")
    incoming_input.returnPressed.emit()
    incoming_input.editingFinished.emit()
    qapp.processEvents()

    saved_row = transactions.list_transactions(
        window.con,
        window.accounts[0].database_id,
    )[0]
    assert transaction.database_id == saved_row["id"]
    assert saved_row["transaction_date"] == stored_date
    assert saved_row["payee_name"] == "Not needed for income"
    assert saved_row["amount"] == 200000
    assert window.budgets[0].monthly_income == Decimal("2000.00")

    window.show_navigation_page(0)
    budget_header = window.budget_page.table.item(0, 1).text()
    assert "Income: $2,000.00" in budget_header

    window.close()
    window.con.close()

    reopened_window = MainWindow(db_path)
    reopened_transaction = reopened_window.accounts[0].transactions[0]
    reopened_header = reopened_window.budget_page.table.item(0, 1).text()

    assert reopened_transaction.payee == "Not needed for income"
    assert reopened_transaction.incoming == Decimal("2000.00")
    assert reopened_window.budgets[0].monthly_income == Decimal("2000.00")
    assert "Income: $2,000.00" in reopened_header


def test_assigned_income_survives_restart(tmp_path):
    db_path = tmp_path / "budget.db"
    window = MainWindow(db_path)
    window.add_account("Checking")
    budget = window.budgets[0]
    month_date = budget.month_date.isoformat()
    transaction = budget_model.Transaction(
        date=month_date,
        payee="Employer",
        category="Income for this month",
        notes="",
        incoming=Decimal("2000.00"),
        category_database_id=window.income_category_id,
        income_month_date=month_date,
    )
    window.save_transaction(window.accounts[0], transaction)
    saved_database_id = transaction.database_id

    window.close()
    window.con.close()

    # Fresh window rebuilds assigned income and transaction target from SQLite
    reopened_window = MainWindow(db_path)
    reopened_budget = reopened_window.budgets[0]
    reloaded_transaction = reopened_window.accounts[0].transactions[0]

    assert reopened_budget.monthly_income == Decimal("2000.00")
    assert reopened_budget.available_to_budget == Decimal("2000.00")
    assert reloaded_transaction.database_id == saved_database_id
    assert reloaded_transaction.income_month_date == month_date


def test_next_month_assigned_income_survives_restart(tmp_path):
    db_path = tmp_path / "budget.db"
    window = MainWindow(db_path)
    window.add_account("Checking")
    current_budget = window.budgets[0]
    next_budget = window.budgets[1]
    transaction = budget_model.Transaction(
        date=current_budget.month_date.isoformat(),
        payee="Employer",
        category="Income for next month",
        notes="",
        incoming=Decimal("2000.00"),
        category_database_id=window.income_category_id,
        income_month_date=next_budget.month_date.isoformat(),
    )
    window.save_transaction(window.accounts[0], transaction)

    window.close()
    window.con.close()

    # Startup-generated next month reloads its assigned total instead of copying
    reopened_window = MainWindow(db_path)

    assert reopened_window.budgets[0].monthly_income == Decimal("0.00")
    assert reopened_window.budgets[1].monthly_income == Decimal("2000.00")


def test_next_month_spending_survives_restart(tmp_path):
    db_path = tmp_path / "budget.db"
    window = MainWindow(db_path)
    window.add_master_category("Everyday Expenses")
    master_category_id = window.budgets[0].master_categories[0].database_id
    window.add_subcategory(master_category_id, "Groceries")
    window.add_account("Checking")
    next_budget = window.budgets[1]
    next_groceries = next_budget.master_categories[0].subcategories[0]
    transaction = budget_model.Transaction(
        date=next_budget.month_date.isoformat(),
        payee="Grocery Store",
        category="Groceries",
        notes="",
        outgoing=Decimal("42.50"),
        category_database_id=next_groceries.database_id,
    )
    window.save_transaction(window.accounts[0], transaction)

    window.close()
    window.con.close()

    # Startup-generated next month rebuilds spending from saved transactions
    reopened_window = MainWindow(db_path)
    reopened_current_groceries = (
        reopened_window.budgets[0].master_categories[0].subcategories[0]
    )
    reopened_next_groceries = (
        reopened_window.budgets[1].master_categories[0].subcategories[0]
    )

    assert reopened_current_groceries.spent == Decimal("0.00")
    assert reopened_next_groceries.spent == Decimal("42.50")


def test_new_window_loads_closed_accounts_separately(tmp_path):
    db_path = tmp_path / "budget.db"
    con = database.connect(db_path)
    database.initialize_database(con)
    closed_account = accounts.create_account(con, "Old Checking", on_budget=False)
    grocery_store = payees.add_payee(con, "Grocery Store")
    master_category = categories.add_master_category(
        con,
        "Everyday Expenses",
    )
    groceries = categories.add_budget_category(
        con,
        master_category["id"],
        "Groceries",
    )
    saved_transaction = transactions.add_transaction(
        con,
        closed_account["id"],
        grocery_store["id"],
        groceries["id"],
        "2026-07-21",
        -4250,
    )
    con.execute(
        "UPDATE accounts SET closed = TRUE WHERE id = ?",
        (closed_account["id"],),
    )
    con.commit()
    con.close()

    window = MainWindow(db_path)
    loaded_account = window.closed_accounts[0]

    assert window.accounts == []
    assert loaded_account.name == "Old Checking"
    assert loaded_account.database_id == closed_account["id"]
    assert loaded_account.on_budget is False
    assert loaded_account.closed is True
    assert loaded_account.transactions[0].database_id == saved_transaction["id"]
    assert loaded_account.transactions[0].outgoing == Decimal("42.50")
    assert window.closed_accounts_button.text() == "▼ Closed"
    assert window.closed_account_items[0].text() == "Old Checking"
    assert window.closed_account_items[0].isHidden() is False

    window.closed_accounts_button.click()

    assert window.closed_accounts_button.text() == "▶ Closed"
    assert window.closed_account_items[0].isHidden() is True


def test_empty_account_database_shows_account_header():
    window = MainWindow(":memory:")

    assert window.nav_names() == [
        "Budget",
        "Reports",
        "Accounts",
        "On Budget",
        "Off Budget",
        "Closed",
    ]
    assert window.accounts_header_item.text() == "Accounts"
    assert window.accounts_header_item.font().pixelSize() == 12
    assert window.accounts_header_item.sizeHint().height() == 36
    assert not window.accounts_header_item.flags() & Qt.ItemFlag.ItemIsSelectable
    assert window.accounts_header_item.data(Qt.ItemDataRole.UserRole) is None
    assert window.on_budget_header_item.text() == "On Budget"
    assert window.on_budget_header_item.font().pixelSize() == 11
    assert window.on_budget_header_item.font().bold() is True
    assert window.on_budget_header_item.sizeHint().height() == 36
    assert window.off_budget_header_item.text() == "Off Budget"
    assert window.off_budget_header_item.font().pixelSize() == 11
    assert window.off_budget_header_item.font().bold() is True
    assert window.off_budget_header_item.sizeHint().height() == 36
    assert window.closed_accounts_button.text() == "▼ Closed"
    assert window.closed_accounts_button.font().pixelSize() == 11
    assert window.closed_accounts_button.font().bold() is True
    assert window.closed_accounts_header_item.sizeHint().height() == 42
    assert not window.on_budget_header_item.flags() & Qt.ItemFlag.ItemIsSelectable
    assert not window.off_budget_header_item.flags() & Qt.ItemFlag.ItemIsSelectable


def test_closed_accounts_expansion_state_survives_restart(tmp_path):
    db_path = tmp_path / "budget.db"
    window = MainWindow(db_path)
    assert window.closed_accounts_button.text() == "▼ Closed"

    window.closed_accounts_button.click()
    assert window.closed_accounts_button.text() == "▶ Closed"
    window.close()
    window.con.close()

    reopened_window = MainWindow(db_path)
    assert reopened_window.closed_accounts_button.text() == "▶ Closed"

    reopened_window.closed_accounts_button.click()
    reopened_window.close()
    reopened_window.con.close()

    final_window = MainWindow(db_path)
    assert final_window.closed_accounts_button.text() == "▼ Closed"


def test_add_account_persists_and_updates_loaded_accounts():
    window = MainWindow(":memory:")

    window.add_account("Checking")

    saved_account = accounts.get_account_by_name(window.con, "Checking")
    loaded_account = window.accounts[0]
    assert saved_account["name"] == "Checking"
    assert loaded_account.name == "Checking"
    assert loaded_account.database_id == saved_account["id"]
    assert loaded_account.on_budget is True
    assert loaded_account.closed is False


def test_add_account_preserves_off_budget_state():
    window = MainWindow(":memory:")

    window.add_account("House Value", on_budget=False)

    saved_account = accounts.get_account_by_name(window.con, "House Value")
    assert saved_account["on_budget"] == False
    assert window.accounts[0].on_budget is False


def test_add_account_persists_opening_balance_transaction(tmp_path):
    db_path = tmp_path / "budget.db"
    window = MainWindow(db_path)

    window.add_account(
        "Checking",
        opening_balance=Decimal("1234.56"),
    )

    account = window.accounts[0]
    opening_transaction = account.transactions[0]
    saved_rows = transactions.list_transactions(
        window.con,
        account.database_id,
    )
    assert opening_transaction.payee == "Opening Balance"
    assert opening_transaction.incoming == Decimal("1234.56")
    assert opening_transaction.cleared is True
    assert saved_rows[0]["amount"] == 123456
    assert window.budgets[0].monthly_income == Decimal("1234.56")

    window.close()
    window.con.close()

    reopened_window = MainWindow(db_path)

    reopened_transaction = reopened_window.accounts[0].transactions[0]
    assert reopened_transaction.payee == "Opening Balance"
    assert reopened_transaction.incoming == Decimal("1234.56")
    assert reopened_window.budgets[0].monthly_income == Decimal("1234.56")


def test_negative_opening_balance_stays_out_of_budget_income():
    window = MainWindow(":memory:")

    window.add_account(
        "Credit Card",
        opening_balance=Decimal("-425.75"),
    )

    account = window.accounts[0]
    opening_transaction = account.transactions[0]
    saved_rows = transactions.list_transactions(
        window.con,
        account.database_id,
    )
    assert opening_transaction.outgoing == Decimal("425.75")
    assert opening_transaction.incoming == Decimal("0.00")
    assert account.working_balance == Decimal("-425.75")
    assert account.cleared_balance == Decimal("-425.75")
    assert saved_rows[0]["amount"] == -42575
    # Debt affects account balance without being treated as earned income
    assert window.budgets[0].monthly_income == Decimal("0.00")


def test_off_budget_opening_balance_stays_out_of_budget_income(tmp_path):
    db_path = tmp_path / "budget.db"
    window = MainWindow(db_path)

    window.add_account(
        "House Value",
        on_budget=False,
        opening_balance=Decimal("250000.00"),
    )

    account = window.accounts[0]
    assert account.working_balance == Decimal("250000.00")
    assert window.budgets[0].monthly_income == Decimal("0.00")

    window.close()
    window.con.close()

    reopened_window = MainWindow(db_path)

    assert reopened_window.accounts[0].on_budget is False
    assert (
        reopened_window.accounts[0].working_balance
        == Decimal("250000.00")
    )
    # Tracking accounts never contribute funds to Budget page
    assert reopened_window.budgets[0].monthly_income == Decimal("0.00")


def test_set_account_closed_updates_model_and_database():
    window = MainWindow(":memory:")
    window.add_account("Checking")
    account = window.accounts[0]
    account_page = window.transaction_pages[0]
    checking_row = next(
        row
        for row in range(window.nav.count())
        if window.nav.item(row).text() == "Checking"
    )
    window.nav.setCurrentRow(checking_row)
    assert window.stack.currentWidget() is account_page

    closed = window.set_account_closed(account, True)
    closed_row = accounts.get_account_by_name(window.con, "Checking")

    assert closed is True
    assert account.closed is True
    assert closed_row["closed"] == True
    assert window.accounts == []
    assert window.closed_accounts == [account]
    assert window.transaction_pages == []
    assert window.stack.indexOf(account_page) == -1
    assert window.stack.currentWidget() is window.budget_page
    assert window.closed_account_items[0].text() == "Checking"

    reopened = window.set_account_closed(account, False)
    reopened_row = accounts.get_account_by_name(window.con, "Checking")

    assert reopened is True
    assert account.closed is False
    assert reopened_row["closed"] == False
    assert window.accounts == [account]
    assert window.closed_accounts == []
    assert window.transaction_pages[0].account is account
    assert window.stack.indexOf(window.transaction_pages[0]) == 2
    assert window.closed_account_items == []
    assert any(
        window.nav.item(row).text() == "Checking"
        for row in range(window.nav.count())
    )


def test_confirmed_close_account_survives_restart(tmp_path, monkeypatch):
    db_path = tmp_path / "budget.db"
    window = MainWindow(db_path)
    window.add_account("Checking")
    account_page = window.transaction_pages[0]
    checking_row = next(
        row
        for row in range(window.nav.count())
        if window.nav.item(row).text() == "Checking"
    )
    window.nav.setCurrentRow(checking_row)
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args: QMessageBox.StandardButton.Yes,
    )

    account_page.close_account_button.click()

    closed_row = accounts.get_account_by_name(window.con, "Checking")
    assert closed_row["closed"] == True
    assert window.accounts == []
    assert window.closed_accounts[0].name == "Checking"
    assert window.closed_account_items[0].text() == "Checking"
    assert window.stack.currentWidget() is window.budget_page

    window.close()
    window.con.close()

    reopened_window = MainWindow(db_path)

    assert reopened_window.accounts == []
    assert reopened_window.closed_accounts[0].name == "Checking"


def test_reopen_account_control_survives_restart(tmp_path):
    db_path = tmp_path / "budget.db"
    window = MainWindow(db_path)
    window.add_account("Checking")
    account = window.accounts[0]
    window.close_account(account)
    closed_page = window.closed_transaction_pages[0]
    assert closed_page.reopen_account_button.text() == "Reopen"

    closed_page.reopen_account_button.click()

    reopened_row = accounts.get_account_by_name(window.con, "Checking")
    assert reopened_row["closed"] == False
    assert window.closed_accounts == []
    assert window.accounts == [account]
    assert window.transaction_pages[0].account is account
    assert any(
        window.nav.item(row).text() == "Checking"
        for row in range(window.nav.count())
    )

    window.close()
    window.con.close()

    reopened_window = MainWindow(db_path)

    assert reopened_window.closed_accounts == []
    assert reopened_window.accounts[0].name == "Checking"


def test_closed_account_history_page_survives_restart(tmp_path):
    db_path = tmp_path / "budget.db"
    window = MainWindow(db_path)
    window.add_master_category("Everyday Expenses")
    master_category = window.budgets[0].master_categories[0]
    window.add_subcategory(master_category.database_id, "Groceries")
    groceries = master_category.subcategories[0]
    window.add_account("Checking")
    account = window.accounts[0]
    transaction = budget_model.Transaction(
        date="2026-07-21",
        payee="Grocery Store",
        category="Groceries",
        notes="",
        outgoing=Decimal("42.50"),
        category_database_id=groceries.database_id,
    )
    account.transactions.append(transaction)
    window.save_transaction(account, transaction)
    window.close_account(account)
    window.close()
    window.con.close()

    reopened_window = MainWindow(db_path)
    closed_page = reopened_window.closed_transaction_pages[0]

    closed_row = next(
        row
        for row in range(reopened_window.nav.count())
        if reopened_window.nav.item(row).text() == "Checking"
    )
    reopened_window.nav.setCurrentRow(closed_row)

    assert reopened_window.stack.currentWidget() is closed_page
    assert closed_page.table.rowCount() == 1
    assert closed_page.table.cellWidget(0, 1).text() == "Grocery Store"
    assert closed_page.allow_new_transactions is False

    closed_page.reopen_account_button.click()

    assert reopened_window.closed_transaction_pages == []
    assert reopened_window.transaction_pages[0].account.name == "Checking"
    assert reopened_window.transaction_pages[0].allow_new_transactions is True


def test_closed_account_navigation_row_opens_history_page(tmp_path):
    db_path = tmp_path / "budget.db"
    window = MainWindow(db_path)
    window.add_account("Checking")
    account = window.accounts[0]
    window.close_account(account)
    closed_page = window.closed_transaction_pages[0]
    closed_row = next(
        row
        for row in range(window.nav.count())
        if window.nav.item(row).text() == "Checking"
    )

    window.nav.setCurrentRow(closed_row)

    assert window.stack.currentWidget() is closed_page
    assert closed_page.allow_new_transactions is False


def test_confirmed_delete_empty_account_survives_restart(
    tmp_path,
    monkeypatch,
):
    db_path = tmp_path / "budget.db"
    window = MainWindow(db_path)
    window.add_account("Checking")
    account_page = window.transaction_pages[0]
    checking_row = next(
        row
        for row in range(window.nav.count())
        if window.nav.item(row).text() == "Checking"
    )
    window.nav.setCurrentRow(checking_row)
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args: QMessageBox.StandardButton.Yes,
    )

    account_page.delete_account_button.click()

    assert accounts.get_account_by_name(window.con, "Checking") is None
    assert window.accounts == []
    assert window.transaction_pages == []
    assert window.stack.indexOf(account_page) == -1
    assert window.stack.currentWidget() is window.budget_page

    window.close()
    window.con.close()

    reopened_window = MainWindow(db_path)

    assert reopened_window.accounts == []
    assert reopened_window.closed_accounts == []


def test_delete_account_with_transactions_offers_close_instead(
    tmp_path,
    monkeypatch,
):
    db_path = tmp_path / "budget.db"
    window = MainWindow(db_path)
    window.add_master_category("Everyday Expenses")
    master_category = window.budgets[0].master_categories[0]
    window.add_subcategory(master_category.database_id, "Groceries")
    groceries = master_category.subcategories[0]
    window.add_account("Checking")
    account = window.accounts[0]
    transaction = budget_model.Transaction(
        date="2026-07-21",
        payee="Grocery Store",
        category="Groceries",
        notes="",
        outgoing=Decimal("42.50"),
        category_database_id=groceries.database_id,
    )
    account.transactions.append(transaction)
    window.save_transaction(account, transaction)
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args: QMessageBox.StandardButton.Yes,
    )

    window.transaction_pages[0].delete_account_button.click()

    saved_account = accounts.get_account_by_name(window.con, "Checking")
    saved_transactions = transactions.list_transactions(
        window.con,
        account.database_id,
    )
    assert saved_account["closed"] == True
    assert len(saved_transactions) == 1
    assert window.accounts == []
    assert window.closed_accounts == [account]

    window.close()
    window.con.close()

    reopened_window = MainWindow(db_path)

    assert reopened_window.accounts == []
    assert reopened_window.closed_accounts[0].name == "Checking"
    assert len(reopened_window.closed_accounts[0].transactions) == 1


def test_new_account_page_receives_hidden_income_category_id():
    window = MainWindow(":memory:")

    # Runtime page receives controller-owned system category relationship
    window.add_account("Checking")

    assert window.transaction_pages[0].income_category_id == window.income_category_id
    assert (
        window.transaction_pages[0].on_transaction_delete_requested
        == window.delete_transaction
    )
    assert (
        window.transaction_pages[0].on_account_close_requested
        == window.close_account
    )
    assert (
        window.transaction_pages[0].on_account_delete_requested
        == window.delete_account
    )


def test_add_account_rejects_duplicate_name():
    window = MainWindow(":memory:")
    window.add_account("Checking")

    with pytest.raises(ValueError, match="Account already exists"):
        window.add_account("cHeCkInG")

    account_rows = accounts.list_accounts(window.con)
    assert [account["name"] for account in account_rows] == ["Checking"]
    assert [account.name for account in window.accounts] == ["Checking"]


def test_add_first_account_keeps_account_header():
    window = MainWindow(":memory:")

    window.add_account("Checking")

    nav_names = navigation_text_rows(window)
    assert nav_names == [
        "Budget",
        "Reports",
        "Accounts",
        "On Budget",
        "Checking",
        "Off Budget",
        "Closed",
    ]
    checking_item = window.nav.item(nav_names.index("Checking"))
    assert checking_item.icon().isNull() is False
    assert checking_item.font().pixelSize() == 11
    assert checking_item.sizeHint().height() == 32
    assert window.stack.widget(2) is window.transaction_pages[0]
    assert window.transaction_pages[0].account is window.accounts[0]
    assert (
        window.transaction_pages[0].on_transaction_changed
        == window.save_transaction
    )


def test_add_later_account_keeps_reports_before_account_pages():
    window = MainWindow(":memory:")
    window.add_account("Checking")

    window.add_account("Savings")

    nav_names = navigation_text_rows(window)
    assert nav_names == [
        "Budget",
        "Reports",
        "Accounts",
        "On Budget",
        "Checking",
        "Savings",
        "Off Budget",
        "Closed",
    ]
    assert window.stack.widget(1) is window.reports_page
    assert window.stack.widget(3) is window.transaction_pages[1]


def test_budget_account_is_inserted_before_off_budget_account():
    window = MainWindow(":memory:")
    window.add_account("House Value", on_budget=False)

    window.add_account("Checking")

    nav_names = navigation_text_rows(window)
    assert [account.name for account in window.accounts] == [
        "Checking",
        "House Value",
    ]
    assert nav_names == [
        "Budget",
        "Reports",
        "Accounts",
        "On Budget",
        "Checking",
        "Off Budget",
        "House Value",
        "Closed",
    ]
    assert window.transaction_pages[0].account.name == "Checking"
    assert window.transaction_pages[1].account.name == "House Value"

    house_value_row = nav_names.index("House Value")
    window.nav.setCurrentRow(house_value_row)

    assert window.stack.currentWidget().account.name == "House Value"


def test_add_account_button_follows_account_entries(qapp):
    window = MainWindow(":memory:")
    window.add_account("Checking")
    window.show()
    qapp.processEvents()

    button_item = None
    for row in range(window.nav.count()):
        item = window.nav.item(row)
        if window.nav.itemWidget(item) is window.add_account_button:
            button_item = item
            break

    assert button_item is not None
    assert window.nav.itemWidget(button_item) is window.add_account_button
    assert window.add_account_button.text() == "+ Add Account"
    assert window.add_account_button.height() == 36
    assert window.add_account_button.width() <= window.nav.width()
    assert not button_item.flags() & Qt.ItemFlag.ItemIsSelectable


def test_payees_and_settings_buttons_are_pinned_below_account_list():
    window = MainWindow(":memory:")

    action_panel = window.navigation_sidebar.layout().itemAt(1).widget()
    action_layout = action_panel.layout()

    assert window.navigation_sidebar.layout().itemAt(0).widget() is window.nav
    assert action_panel.objectName() == "navigationActions"
    assert action_layout.itemAt(0).widget() is window.payees_button
    assert action_layout.itemAt(1).widget() is window.settings_button
    assert window.payees_button.text() == ""
    assert window.payees_button.toolTip() == "Payees"
    assert window.payees_button.size() == QSize(44, 44)
    assert window.payees_button.icon().isNull() is False
    assert window.payees_button.iconSize() == QSize(18, 18)
    assert window.settings_button.text() == ""
    assert window.settings_button.toolTip() == "Settings coming later"
    assert window.settings_button.size() == QSize(44, 44)
    assert window.settings_button.icon().isNull() is False
    assert window.settings_button.iconSize() == QSize(18, 18)
    assert window.settings_button.isEnabled() is True


def test_budget_and_reports_nav_items_show_icons():
    window = MainWindow(":memory:")

    assert window.nav.iconSize() == QSize(18, 18)
    assert window.nav.item(0).text() == "Budget"
    assert window.nav.item(0).icon().isNull() is False
    assert window.nav.item(1).text() == "Reports"
    assert window.nav.item(1).icon().isNull() is False


def test_account_navigation_only_scrolls_vertically():
    window = MainWindow(":memory:")

    assert (
        window.nav.horizontalScrollBarPolicy()
        == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    )
    assert window.closed_accounts_button.height() == 36


def test_payees_button_opens_payees_dialog(monkeypatch):
    window = MainWindow(":memory:")
    opened_dialogs = []

    class FakePayeesDialog:
        def __init__(self, con, parent=None):
            opened_dialogs.append((con, parent))

        def exec(self):
            opened_dialogs.append("exec")

    monkeypatch.setattr(payees_dialog, "PayeesDialog", FakePayeesDialog)

    window.payees_button.click()

    assert opened_dialogs == [(window.con, window), "exec"]


def test_payees_dialog_refreshes_transaction_autocomplete(monkeypatch):
    window = MainWindow(":memory:")
    window.add_account("Checking")

    class FakePayeesDialog:
        def __init__(self, con, parent=None):
            self.con = con

        def exec(self):
            payees.add_payee(self.con, "Safeway")

    monkeypatch.setattr(payees_dialog, "PayeesDialog", FakePayeesDialog)

    window.open_payees_dialog()

    payee_input = window.transaction_pages[0].table.cellWidget(0, 1)
    model = payee_input.completer().model()
    assert [
        model.index(row, 0).data()
        for row in range(model.rowCount())
    ] == ["Safeway"]


def test_payees_dialog_refreshes_open_transaction_payee_names(monkeypatch):
    window = MainWindow(":memory:")
    master_category = categories.add_master_category(
        window.con,
        "Everyday Expenses",
    )
    category = categories.add_budget_category(
        window.con,
        master_category["id"],
        "Groceries",
    )
    window.add_account("Checking")
    page = window.transaction_pages[0]
    page.create_transaction(
        date="2026-07-21",
        payee="food 4 less",
        category="Groceries",
        outgoing=Decimal("42.50"),
        category_database_id=category["id"],
    )

    class FakePayeesDialog:
        def __init__(self, con, parent=None):
            self.con = con

        def exec(self):
            payee = payees.get_payee_by_name(self.con, "food 4 less")
            payees.rename_payee(self.con, payee["id"], "Food 4 Less")

    monkeypatch.setattr(payees_dialog, "PayeesDialog", FakePayeesDialog)

    window.open_payees_dialog()

    payee_input = page.table.cellWidget(0, 1)
    model = payee_input.completer().model()
    assert page.account.transactions[0].payee == "Food 4 Less"
    assert payee_input.text() == "Food 4 Less"
    assert [
        model.index(row, 0).data()
        for row in range(model.rowCount())
    ] == ["Food 4 Less"]


def test_navigation_ignores_rows_without_a_page():
    window = MainWindow(":memory:")
    window.stack.setCurrentIndex(1)
    button_row = window.nav.count() - 1

    window.show_navigation_page(button_row)

    assert window.stack.currentIndex() == 1


def test_submit_account_name_trims_and_creates_account():
    window = MainWindow(":memory:")

    window.submit_account_name(" Checking ")

    assert window.accounts[0].name == "Checking"


def test_submit_account_name_preserves_off_budget_choice():
    window = MainWindow(":memory:")

    window.submit_account_name("House Value", on_budget=False)

    assert window.accounts[0].name == "House Value"
    assert window.accounts[0].on_budget is False


def test_account_dialog_shows_name_and_account_type_together():
    dialog = AccountDialog()

    assert dialog.isAncestorOf(dialog.name_input)
    assert dialog.isAncestorOf(dialog.opening_balance_input)
    assert dialog.isAncestorOf(dialog.budget_radio)
    assert dialog.isAncestorOf(dialog.off_budget_radio)
    assert dialog.budget_radio.isChecked()
    assert dialog.opening_balance() == Decimal("0.00")

    dialog.off_budget_radio.setChecked(True)
    dialog.opening_balance_input.setText("$1,234.56")

    assert dialog.budget_radio.isChecked() is False
    assert dialog.off_budget_radio.isChecked()
    assert dialog.opening_balance() == Decimal("1234.56")


def test_account_dialog_rejects_invalid_opening_balance():
    dialog = AccountDialog()
    dialog.opening_balance_input.setText("not money")

    with pytest.raises(ValueError, match="valid number"):
        dialog.opening_balance()


def test_new_window_starts_without_sample_budget_values():
    window = MainWindow(":memory:")

    assert window.budgets[0].monthly_income == Decimal("0.00")
    assert window.budgets[0].master_categories == []
    assert window.budgets[0].total_budgeted == Decimal("0.00")
    assert window.budgets[0].total_spent == Decimal("0.00")


def test_new_window_loads_assigned_transaction_income(tmp_path):
    db_path = tmp_path / "budget.db"
    con = database.connect(db_path)
    database.initialize_database(con)
    month_date = date.today().replace(day=1).isoformat()
    budgets.add_budget_month(con, month_date)
    checking = accounts.create_account(con, "Checking")
    employer = payees.add_payee(con, "Employer")
    income_category = categories.get_or_create_income_category(con)
    transactions.add_transaction(
        con,
        checking["id"],
        employer["id"],
        income_category["id"],
        month_date,
        520000,
        income_month_date=month_date,
    )
    con.close()

    window = MainWindow(db_path)

    assert window.budgets[0].monthly_income == Decimal("5200.00")


def test_new_window_loads_saved_category_allocation(tmp_path):
    db_path = tmp_path / "budget.db"
    con = database.connect(db_path)
    database.initialize_database(con)
    budget_month = budgets.add_budget_month(
        con,
        date.today().replace(day=1).isoformat(),
    )
    master_category = categories.add_master_category(con, "Monthly Bills")
    rent = categories.add_budget_category(
        con,
        master_category["id"],
        "Rent",
    )
    budgets.add_budget_allocation(
        con,
        budget_month["id"],
        rent["id"],
        185000,
    )
    con.close()

    window = MainWindow(db_path)
    loaded_rent = window.budgets[0].master_categories[0].subcategories[0]

    assert loaded_rent.database_id == rent["id"]
    assert loaded_rent.budgeted == Decimal("1850.00")


def test_budget_allocation_changed_saves_category_amount():
    window = MainWindow(":memory:")
    window.add_master_category("Monthly Bills")
    master_category_id = window.budgets[0].master_categories[0].database_id
    window.add_subcategory(master_category_id, "Rent")
    budget = window.budgets[0]
    rent = budget.master_categories[0].subcategories[0]
    rent.budgeted = Decimal("1850.00")

    window.budget_allocation_changed(budget, rent)

    budget_month = budgets.get_budget_month_by_date(
        window.con,
        budget.month_date.isoformat(),
    )
    saved_allocation = budgets.list_budget_allocations(
        window.con,
        budget_month["id"],
    )[0]
    assert saved_allocation["budget_category_id"] == rent.database_id
    assert saved_allocation["amount"] == 185000


def test_budgeted_cell_edit_survives_restart(tmp_path):
    db_path = tmp_path / "budget.db"
    window = MainWindow(db_path)
    window.add_master_category("Monthly Bills")
    master_category_id = window.budgets[0].master_categories[0].database_id
    window.add_subcategory(master_category_id, "Rent")

    # UI edit exercises callback and persistence path
    row = window.budget_page.rows.index(("Monthly Bills", "Rent")) + 2
    budgeted_input = window.budget_page.table.cellWidget(row, 1)
    budgeted_input.setText("1850.00")
    budgeted_input.editingFinished.emit()
    window.close()
    window.con.close()

    # Fresh window rebuilds allocation from same SQLite file
    reopened_window = MainWindow(db_path)
    reloaded_rent = reopened_window.budgets[0].master_categories[0].subcategories[0]

    assert reloaded_rent.budgeted == Decimal("1850.00")


def test_next_month_budgeted_cell_edit_survives_restart(tmp_path):
    db_path = tmp_path / "budget.db"
    window = MainWindow(db_path)
    window.add_master_category("Monthly Bills")
    master_category_id = window.budgets[0].master_categories[0].database_id
    window.add_subcategory(master_category_id, "Rent")
    next_budget = window.budgets[1]
    next_rent = next_budget.master_categories[0].subcategories[0]
    next_rent.budgeted = Decimal("1900.00")
    window.budget_allocation_changed(next_budget, next_rent)

    window.close()
    window.con.close()

    # Startup-generated next month reloads allocation saved for its date
    reopened_window = MainWindow(db_path)
    reopened_current_rent = (
        reopened_window.budgets[0].master_categories[0].subcategories[0]
    )
    reopened_next_rent = (
        reopened_window.budgets[1].master_categories[0].subcategories[0]
    )

    assert reopened_current_rent.budgeted == Decimal("0.00")
    assert reopened_next_rent.budgeted == Decimal("1900.00")


def test_budget_navigation_loads_saved_future_month_allocation():
    window = MainWindow(":memory:")
    window.add_master_category("Monthly Bills")
    master_category_id = window.budgets[0].master_categories[0].database_id
    window.add_subcategory(master_category_id, "Rent")
    initial_month_count = len(window.budgets)
    future_month_date = budget_model.next_month(
        window.budgets[-1].month_date
    )
    future_budget_month = budgets.get_or_create_budget_month(
        window.con,
        future_month_date.isoformat(),
    )
    rent_id = window.budgets[0].master_categories[0].subcategories[0].database_id
    budgets.set_budget_allocation(
        window.con,
        future_budget_month["id"],
        rent_id,
        195000,
    )

    # Moving existing window edge forward generates and reloads later months
    window.budget_page.set_active_month(initial_month_count - 1)

    future_budget = window.budgets[initial_month_count]
    future_rent = future_budget.master_categories[0].subcategories[0]
    assert future_budget.month_date == future_month_date
    assert future_rent.budgeted == Decimal("1950.00")


def test_new_window_loads_saved_master_categories(tmp_path):
    db_path = tmp_path / "budget.db"
    con = database.connect(db_path)
    database.initialize_database(con)
    master_category = categories.add_master_category(con, "Monthly Bills")
    con.close()

    window = MainWindow(db_path)
    loaded_master = window.budgets[0].master_categories[0]

    assert loaded_master.name == "Monthly Bills"
    assert loaded_master.database_id == master_category["id"]


def test_new_window_loads_saved_budget_categories_under_their_master(tmp_path):
    db_path = tmp_path / "budget.db"
    con = database.connect(db_path)
    database.initialize_database(con)
    master_category = categories.add_master_category(con, "Everyday Expenses")
    budget_category = categories.add_budget_category(
        con,
        master_category["id"],
        "Groceries",
    )
    con.close()

    window = MainWindow(db_path)
    loaded_master = window.budgets[0].master_categories[0]
    loaded_subcategory = loaded_master.subcategories[0]

    assert loaded_subcategory.name == "Groceries"
    assert loaded_subcategory.database_id == budget_category["id"]


def test_add_master_category_persists_and_updates_loaded_budgets():
    window = MainWindow(":memory:")

    window.add_master_category("Savings")

    saved_category = categories.get_master_category_by_name(window.con, "Savings")
    loaded_names = [budget.master_categories[0].name for budget in window.budgets]
    loaded_ids = [budget.master_categories[0].database_id for budget in window.budgets]
    assert saved_category["name"] == "Savings"
    assert loaded_names == ["Savings"] * len(window.budgets)
    assert loaded_ids == [saved_category["id"]] * len(window.budgets)


def test_add_master_category_rejects_duplicate_name():
    window = MainWindow(":memory:")
    window.add_master_category("Savings")

    with pytest.raises(ValueError, match="Master category already exists"):
        window.add_master_category("sAvInGs")

    category_rows = categories.list_master_categories(window.con)
    assert [category["name"] for category in category_rows] == ["Savings"]


def test_rename_master_category_updates_loaded_budgets_and_account_pages():
    window = MainWindow(":memory:")
    window.add_account("Checking")
    window.add_master_category("Everyday Expenses")
    master_category_id = window.budgets[0].master_categories[0].database_id
    window.add_subcategory(master_category_id, "Groceries")

    renamed = window.rename_master_category(
        master_category_id,
        "Weekly Spending",
    )

    saved_category = categories.get_master_category_by_name(
        window.con,
        "Weekly Spending",
    )
    assert renamed is True
    assert saved_category["id"] == master_category_id
    assert [
        budget.master_categories[0].name
        for budget in window.budgets
    ] == ["Weekly Spending"] * len(window.budgets)
    assert (
        window.transaction_pages[0].category_rows[0][
            "master_category_name"
        ]
        == "Weekly Spending"
    )


def test_reorder_master_categories_updates_loaded_budgets_and_account_pages():
    window = MainWindow(":memory:")
    window.add_account("Checking")
    window.add_master_category("Monthly Bills")
    window.add_master_category("Everyday Expenses")
    window.add_master_category("Savings")
    for master_category in window.budgets[0].master_categories:
        window.add_subcategory(master_category.database_id, "Placeholder")
    master_category_ids = [
        category.database_id
        for category in window.budgets[0].master_categories
    ]

    window.reorder_master_categories(
        [
            master_category_ids[2],
            master_category_ids[0],
            master_category_ids[1],
        ]
    )

    saved_names = [
        category["name"]
        for category in categories.list_master_categories(window.con)
    ]
    loaded_names = [
        category.name
        for category in window.budgets[0].master_categories
    ]
    category_input = window.transaction_pages[0].table.cellWidget(0, 2)

    assert saved_names == ["Savings", "Monthly Bills", "Everyday Expenses"]
    assert loaded_names == ["Savings", "Monthly Bills", "Everyday Expenses"]
    assert [category_input.itemText(index) for index in range(category_input.count())] == [
        "Placeholder (Savings)",
        "Placeholder (Monthly Bills)",
        "Placeholder (Everyday Expenses)",
    ]


def test_budget_page_reorder_callbacks_are_wired_to_main_window():
    window = MainWindow(":memory:")

    assert (
        window.budget_page.on_master_categories_reordered
        == window.reorder_master_categories
    )
    assert (
        window.budget_page.on_subcategories_reordered
        == window.reorder_subcategories
    )


def test_rename_master_category_rejects_duplicate_name():
    window = MainWindow(":memory:")
    window.add_master_category("Monthly Bills")
    window.add_master_category("Everyday Expenses")
    master_category_id = window.budgets[0].master_categories[0].database_id

    with pytest.raises(ValueError, match="Master category already exists"):
        window.rename_master_category(
            master_category_id,
            "everyday expenses",
        )

    assert window.budgets[0].master_categories[0].name == "Monthly Bills"


def test_master_category_rename_button_opens_prefilled_dialog(monkeypatch):
    window = MainWindow(":memory:")
    window.add_master_category("Everyday Expenses")
    master_category = window.budgets[0].master_categories[0]
    dialog_requests = []

    def rename_dialog(*args):
        dialog_requests.append(args)
        return "Weekly Spending", True

    monkeypatch.setattr(QInputDialog, "getText", rename_dialog)
    rename_button = next(
        button
        for button in window.budget_page.findChildren(
            QPushButton,
            "renameMasterCategoryButton",
        )
        if button.property("master_category_id")
        == master_category.database_id
    )

    rename_button.click()

    assert dialog_requests[0][4] == "Everyday Expenses"
    assert master_category.name == "Weekly Spending"
    assert (
        categories.get_master_category_by_name(
            window.con,
            "Weekly Spending",
        )["id"]
        == master_category.database_id
    )
    assert window.budget_page.feedback.text() == (
        'Renamed master category to "Weekly Spending".'
    )


def test_add_subcategory_persists_and_updates_loaded_budgets():
    window = MainWindow(":memory:")
    # Account-first setup verifies its existing page receives the later category
    window.add_account("Checking")
    window.add_master_category("Everyday Expenses")
    master_category_id = window.budgets[0].master_categories[0].database_id

    window.add_subcategory(master_category_id, "Groceries")

    saved_subcategory = categories.list_budget_categories(window.con, master_category_id)[0]
    loaded_names = [
        budget.master_categories[0].subcategories[0].name
        for budget in window.budgets
    ]
    loaded_ids = [
        budget.master_categories[0].subcategories[0].database_id
        for budget in window.budgets
    ]
    assert saved_subcategory["name"] == "Groceries"
    assert loaded_names == ["Groceries"] * len(window.budgets)
    assert loaded_ids == [saved_subcategory["id"]] * len(window.budgets)
    category_input = window.transaction_pages[0].table.cellWidget(0, 2)
    assert [category_input.itemText(index) for index in range(category_input.count())] == [
        "Groceries",
    ]


def test_transaction_category_add_does_not_rebuild_active_page():
    window = MainWindow(":memory:")
    window.add_account("Checking")
    window.add_master_category("Eating Out")
    page = window.transaction_pages[0]
    category_input = page.table.cellWidget(0, 2)
    master_category_id = window.budgets[0].master_categories[0].database_id

    category_row = window.add_transaction_subcategory(
        master_category_id,
        "Fast Food",
    )

    assert page.table.cellWidget(0, 2) is category_input
    assert category_row["category_name"] == "Fast Food"
    assert category_row["master_category_name"] == "Eating Out"
    assert categories.get_budget_category_by_name(
        window.con,
        master_category_id,
        "Fast Food",
    )["id"] == category_row["id"]


def test_rename_subcategory_updates_loaded_budgets_and_transactions():
    window = MainWindow(":memory:")
    window.add_master_category("Everyday Expenses")
    master_category_id = window.budgets[0].master_categories[0].database_id
    window.add_subcategory(master_category_id, "Groceries")
    subcategory_id = (
        window.budgets[0].master_categories[0].subcategories[0].database_id
    )
    window.add_account("Checking")
    window.add_account("Old Checking")
    for account in window.accounts:
        account.transactions.append(
            budget_model.Transaction(
                date="2026-07-21",
                payee="Grocery Store",
                category="Groceries",
                notes="",
                outgoing=Decimal("42.50"),
                category_database_id=subcategory_id,
            )
        )
    window.close_account(window.accounts[1])

    renamed = window.rename_subcategory(
        master_category_id,
        subcategory_id,
        "Food",
    )

    assert renamed is True
    assert [
        budget.master_categories[0].subcategories[0].name
        for budget in window.budgets
    ] == ["Food"] * len(window.budgets)
    assert window.accounts[0].transactions[0].category == "Food"
    assert window.closed_accounts[0].transactions[0].category == "Food"
    assert window.transaction_pages[0].category_rows[0]["category_name"] == "Food"
    assert (
        window.closed_transaction_pages[0].category_rows[0]["category_name"]
        == "Food"
    )


def test_rename_subcategory_rejects_duplicate_name_within_master():
    window = MainWindow(":memory:")
    window.add_master_category("Everyday Expenses")
    master_category_id = window.budgets[0].master_categories[0].database_id
    window.add_subcategory(master_category_id, "Groceries")
    window.add_subcategory(master_category_id, "Dining Out")
    subcategory_id = (
        window.budgets[0].master_categories[0].subcategories[0].database_id
    )

    with pytest.raises(ValueError, match="Subcategory already exists"):
        window.rename_subcategory(
            master_category_id,
            subcategory_id,
            "dining out",
        )

    assert (
        window.budgets[0].master_categories[0].subcategories[0].name
        == "Groceries"
    )


def test_reorder_subcategories_updates_loaded_budgets_and_account_pages():
    window = MainWindow(":memory:")
    window.add_account("Checking")
    window.add_master_category("Everyday Expenses")
    master_category_id = window.budgets[0].master_categories[0].database_id
    window.add_subcategory(master_category_id, "Groceries")
    window.add_subcategory(master_category_id, "Gas")
    window.add_subcategory(master_category_id, "Dining Out")
    subcategory_ids = [
        subcategory.database_id
        for subcategory in window.budgets[0].master_categories[0].subcategories
    ]

    window.reorder_subcategories(
        master_category_id,
        [subcategory_ids[2], subcategory_ids[0], subcategory_ids[1]],
    )

    saved_names = [
        category["name"]
        for category in categories.list_budget_categories(
            window.con,
            master_category_id,
        )
    ]
    loaded_names = [
        subcategory.name
        for subcategory in window.budgets[0].master_categories[0].subcategories
    ]
    category_input = window.transaction_pages[0].table.cellWidget(0, 2)

    assert saved_names == ["Dining Out", "Groceries", "Gas"]
    assert loaded_names == ["Dining Out", "Groceries", "Gas"]
    assert [category_input.itemText(index) for index in range(category_input.count())] == [
        "Dining Out",
        "Groceries",
        "Gas",
    ]


def test_subcategory_rename_button_opens_prefilled_dialog(monkeypatch):
    window = MainWindow(":memory:")
    window.add_master_category("Everyday Expenses")
    master_category = window.budgets[0].master_categories[0]
    window.add_subcategory(master_category.database_id, "Groceries")
    subcategory = master_category.subcategories[0]
    dialog_requests = []

    def rename_dialog(*args):
        dialog_requests.append(args)
        return "Food", True

    monkeypatch.setattr(QInputDialog, "getText", rename_dialog)
    rename_button = next(
        button
        for button in window.budget_page.findChildren(
            QPushButton,
            "renameSubcategoryButton",
        )
        if button.property("budget_category_id")
        == subcategory.database_id
    )

    rename_button.click()

    assert dialog_requests[0][4] == "Groceries"
    assert subcategory.name == "Food"
    assert (
        categories.get_budget_category_by_name(
            window.con,
            master_category.database_id,
            "Food",
        )["id"]
        == subcategory.database_id
    )
    assert window.budget_page.feedback.text() == (
        'Renamed subcategory to "Food".'
    )


def test_master_category_delete_button_removes_unused_group(monkeypatch):
    window = MainWindow(":memory:")
    window.add_master_category("Everyday Expenses")
    master_category = window.budgets[0].master_categories[0]
    window.add_subcategory(master_category.database_id, "Groceries")
    window.add_account("Checking")
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args: QMessageBox.StandardButton.Yes,
    )
    delete_button = next(
        button
        for button in window.budget_page.findChildren(
            QPushButton,
            "deleteMasterCategoryButton",
        )
        if button.property("master_category_id")
        == master_category.database_id
    )

    delete_button.click()

    assert categories.get_master_category_by_name(
        window.con,
        "Everyday Expenses",
    ) is None
    assert all(
        all(
            category.database_id != master_category.database_id
            for category in budget.master_categories
        )
        for budget in window.budgets
    )
    assert window.transaction_pages[0].category_rows == []
    assert window.budget_page.feedback.text() == (
        'Deleted master category "Everyday Expenses".'
    )


def test_master_category_delete_button_hides_group_with_transactions(
    monkeypatch,
):
    window = MainWindow(":memory:")
    window.add_master_category("Everyday Expenses")
    master_category = window.budgets[0].master_categories[0]
    window.add_subcategory(master_category.database_id, "Groceries")
    subcategory = master_category.subcategories[0]
    subcategory.budgeted = Decimal("1000.00")
    window.budget_allocation_changed(window.budgets[0], subcategory)
    window.add_account("Checking")
    transaction = budget_model.Transaction(
        date=window.budgets[0].month_date.isoformat(),
        payee="Grocery Store",
        category="Groceries",
        notes="",
        outgoing=Decimal("1000.00"),
        category_database_id=subcategory.database_id,
    )
    window.accounts[0].transactions.append(transaction)
    window.save_transaction(window.accounts[0], transaction)
    questions = []

    def confirm_hide(*args):
        questions.append(args)
        return QMessageBox.StandardButton.Yes

    monkeypatch.setattr(QMessageBox, "question", confirm_hide)
    delete_button = next(
        button
        for button in window.budget_page.findChildren(
            QPushButton,
            "deleteMasterCategoryButton",
        )
        if button.property("master_category_id")
        == master_category.database_id
    )

    delete_button.click()

    assert "cannot be deleted" in questions[0][2]
    assert all(
        all(
            category.database_id != master_category.database_id
            for category in budget.master_categories
        )
        for budget in window.budgets
    )
    assert [
        row["id"] for row in window.hidden_master_category_rows
    ] == [master_category.database_id]
    assert window.budget_page.hidden_master_category_rows == (
        window.hidden_master_category_rows
    )
    assert transactions.list_transactions(
        window.con,
        window.accounts[0].database_id,
    )[0]["budget_category_id"] == subcategory.database_id
    assert window.budgets[0].hidden_budgeted == Decimal("1000.00")
    assert window.budgets[0].hidden_spent == Decimal("1000.00")
    assert window.budgets[0].total_budgeted == Decimal("1000.00")
    assert window.budgets[0].total_spent == Decimal("1000.00")
    assert window.transaction_pages[0].category_rows == []
    assert window.budget_page.feedback.text() == (
        'Hidden master category "Everyday Expenses".'
    )


def test_subcategory_delete_button_removes_unused_category(monkeypatch):
    window = MainWindow(":memory:")
    window.add_master_category("Everyday Expenses")
    master_category = window.budgets[0].master_categories[0]
    window.add_subcategory(master_category.database_id, "Groceries")
    subcategory = master_category.subcategories[0]
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args: QMessageBox.StandardButton.Yes,
    )
    delete_button = next(
        button
        for button in window.budget_page.findChildren(
            QPushButton,
            "deleteSubcategoryButton",
        )
        if button.property("budget_category_id")
        == subcategory.database_id
    )

    delete_button.click()

    assert categories.list_budget_categories(
        window.con,
        master_category.database_id,
    ) == []
    assert master_category.subcategories == []
    assert window.budget_page.feedback.text() == (
        'Deleted subcategory "Groceries".'
    )


def test_subcategory_delete_button_hides_category_with_transactions(
    qapp,
    monkeypatch,
):
    window = MainWindow(":memory:")
    window.add_master_category("Everyday Expenses")
    master_category = window.budgets[0].master_categories[0]
    window.add_subcategory(master_category.database_id, "Groceries")
    subcategory = master_category.subcategories[0]
    subcategory.budgeted = Decimal("1000.00")
    window.budget_allocation_changed(window.budgets[0], subcategory)
    window.add_account("Checking")
    transaction = budget_model.Transaction(
        date=window.budgets[0].month_date.isoformat(),
        payee="Grocery Store",
        category="Groceries",
        notes="",
        outgoing=Decimal("1000.00"),
        category_database_id=subcategory.database_id,
    )
    window.accounts[0].transactions.append(transaction)
    window.save_transaction(window.accounts[0], transaction)
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args: QMessageBox.StandardButton.Yes,
    )
    delete_button = next(
        button
        for button in window.budget_page.findChildren(
            QPushButton,
            "deleteSubcategoryButton",
        )
        if button.property("budget_category_id")
        == subcategory.database_id
    )

    delete_button.click()
    qapp.processEvents()

    assert master_category.subcategories == []
    assert [
        row["id"] for row in window.hidden_subcategory_rows
    ] == [subcategory.database_id]
    assert window.budget_page.hidden_subcategory_rows == (
        window.hidden_subcategory_rows
    )
    assert transactions.list_transactions(
        window.con,
        window.accounts[0].database_id,
    )[0]["budget_category_id"] == subcategory.database_id
    assert window.budgets[0].hidden_budgeted == Decimal("1000.00")
    assert window.budgets[0].hidden_spent == Decimal("1000.00")
    assert window.budgets[0].total_budgeted == Decimal("1000.00")
    assert window.budgets[0].total_spent == Decimal("1000.00")
    assert window.budget_page.feedback.text() == (
        'Hidden subcategory "Groceries".'
    )
    assert window.budget_page.feedback.text() == (
        'Hidden subcategory "Groceries".'
    )
    assert window.budget_page.feedback.property("feedbackKind") == "success"

    restore_button = window.budget_page.findChild(
        QPushButton,
        "restoreSubcategoryButton",
    )
    assert restore_button is not None


def test_add_subcategory_rejects_duplicate_name_within_master():
    window = MainWindow(":memory:")
    window.add_master_category("Everyday Expenses")
    master_category_id = window.budgets[0].master_categories[0].database_id
    window.add_subcategory(master_category_id, "Groceries")

    with pytest.raises(ValueError, match="Subcategory already exists"):
        window.add_subcategory(master_category_id, "gRoCeRiEs")

    category_rows = categories.list_budget_categories(window.con, master_category_id)
    loaded_subcategories = window.budgets[0].master_categories[0].subcategories
    assert [category["name"] for category in category_rows] == ["Groceries"]
    assert [subcategory.name for subcategory in loaded_subcategories] == ["Groceries"]
