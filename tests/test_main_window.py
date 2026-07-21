from decimal import Decimal

import pytest

from PyQt6.QtCore import Qt

import budget_model
from db import accounts, categories, database, payees, transactions
from ui.main_window import AccountDialog, MainWindow


# Every test in this module creates Qt widgets and requires the shared application
pytestmark = pytest.mark.usefixtures("qapp")


def test_new_window_leaves_account_table_empty():
    window = MainWindow(":memory:")

    assert accounts.has_accounts(window.con) == False


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
        == window.save_new_transaction
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
    assert [category_input.itemText(index) for index in range(category_input.count())] == [
        "",
        "Everyday Expenses",
        "Groceries",
        "Savings",
        "Vacation",
    ]
    # Master rows group the list but cannot become a transaction category
    assert category_input.model().item(1).isEnabled() is False
    assert category_input.model().item(3).isEnabled() is False
    assert category_input.currentText() == "Groceries"
    assert category_input.currentData()["database_id"] == category["id"]


def test_save_new_transaction_inserts_once_and_retains_database_id():
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

    first_save = window.save_new_transaction(window.accounts[0], transaction)
    second_save = window.save_new_transaction(window.accounts[0], transaction)
    saved_rows = transactions.list_transactions(
        window.con,
        window.accounts[0].database_id,
    )

    assert first_save is True
    assert second_save is False
    assert transaction.database_id == saved_rows[0]["id"]
    assert saved_rows[0]["payee_name"] == "Grocery Store"
    assert saved_rows[0]["amount"] == -4250
    assert len(saved_rows) == 1


def test_save_new_transaction_waits_for_required_fields():
    window = MainWindow(":memory:")
    window.add_account("Checking")
    transaction = budget_model.Transaction(
        date="2026-07-21",
        payee="Grocery Store",
        category="",
        notes="",
        outgoing=Decimal("42.50"),
    )

    saved = window.save_new_transaction(window.accounts[0], transaction)

    assert saved is False
    assert transaction.database_id is None
    assert transactions.has_transactions(window.con) is False


def test_new_window_loads_closed_accounts_separately(tmp_path):
    db_path = tmp_path / "budget.db"
    con = database.connect(db_path)
    database.initialize_database(con)
    closed_account = accounts.create_account(con, "Old Checking", on_budget=False)
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


def test_empty_account_database_shows_account_header():
    window = MainWindow(":memory:")

    assert window.nav_names() == [
        "Budget",
        "Reports",
        "Accounts",
        "On Budget",
        "Off Budget",
    ]
    assert window.accounts_header_item.text() == "Accounts"
    assert window.accounts_header_item.font().pixelSize() == 12
    assert not window.accounts_header_item.flags() & Qt.ItemFlag.ItemIsSelectable
    assert window.accounts_header_item.data(Qt.ItemDataRole.UserRole) is None
    assert window.on_budget_header_item.text() == "On Budget"
    assert window.off_budget_header_item.text() == "Off Budget"
    assert not window.on_budget_header_item.flags() & Qt.ItemFlag.ItemIsSelectable
    assert not window.off_budget_header_item.flags() & Qt.ItemFlag.ItemIsSelectable


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

    nav_names = [
        window.nav.item(row).text()
        for row in range(window.nav.count() - 1)
    ]
    assert nav_names == [
        "Budget",
        "Reports",
        "Accounts",
        "On Budget",
        "Checking",
        "Off Budget",
    ]
    assert window.stack.widget(2) is window.transaction_pages[0]
    assert window.transaction_pages[0].account is window.accounts[0]
    assert (
        window.transaction_pages[0].on_transaction_changed
        == window.save_new_transaction
    )


def test_add_later_account_keeps_reports_before_account_pages():
    window = MainWindow(":memory:")
    window.add_account("Checking")

    window.add_account("Savings")

    nav_names = [
        window.nav.item(row).text()
        for row in range(window.nav.count() - 1)
    ]
    assert nav_names == [
        "Budget",
        "Reports",
        "Accounts",
        "On Budget",
        "Checking",
        "Savings",
        "Off Budget",
    ]
    assert window.stack.widget(1) is window.reports_page
    assert window.stack.widget(3) is window.transaction_pages[1]


def test_budget_account_is_inserted_before_off_budget_account():
    window = MainWindow(":memory:")
    window.add_account("House Value", on_budget=False)

    window.add_account("Checking")

    nav_names = [
        window.nav.item(row).text()
        for row in range(window.nav.count() - 1)
    ]
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

    button_item = window.nav.item(window.nav.count() - 1)

    assert window.nav.itemWidget(button_item) is window.add_account_button
    assert window.add_account_button.text() == "+ Add Account"
    assert window.add_account_button.height() > 0
    assert not button_item.flags() & Qt.ItemFlag.ItemIsSelectable


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
    assert dialog.isAncestorOf(dialog.budget_radio)
    assert dialog.isAncestorOf(dialog.off_budget_radio)
    assert dialog.budget_radio.isChecked()

    dialog.off_budget_radio.setChecked(True)

    assert dialog.budget_radio.isChecked() is False
    assert dialog.off_budget_radio.isChecked()


def test_new_window_starts_without_sample_budget_values():
    window = MainWindow(":memory:")

    assert window.budgets[0].monthly_income == Decimal("0.00")
    assert window.budgets[0].master_categories == []
    assert window.budgets[0].total_budgeted == Decimal("0.00")
    assert window.budgets[0].total_spent == Decimal("0.00")


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
        "",
        "Everyday Expenses",
        "Groceries",
    ]


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
