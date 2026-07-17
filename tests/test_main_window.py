import os
from decimal import Decimal

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from db import accounts, categories, database
from ui.main_window import MainWindow


def test_new_window_leaves_account_table_empty():
    # Qt requires QApplication instance to create widgets
    _app = QApplication.instance() or QApplication([])
    window = MainWindow(":memory:")

    assert accounts.has_accounts(window.con) == False


def test_empty_account_database_shows_empty_state():
    # Qt requires QApplication instance to create widgets
    _app = QApplication.instance() or QApplication([])
    window = MainWindow(":memory:")

    assert window.nav_names() == ["Budget", "Accounts", "Reports"]
    assert window.empty_accounts_page.text() == "No accounts yet."


def test_new_window_starts_without_sample_budget_values():
    # Qt requires QApplication instance to create widgets
    _app = QApplication.instance() or QApplication([])
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
    # Qt requires QApplication instance to create widgets
    _app = QApplication.instance() or QApplication([])

    window = MainWindow(db_path)
    loaded_master = window.budgets[0].master_categories[0]

    assert loaded_master.name == "Monthly Bills"
    assert loaded_master.database_id == master_category["id"]


def test_new_window_loads_saved_budget_categories_under_their_master(tmp_path):
    db_path = tmp_path / "budget.db"
    con = database.connect(db_path)
    database.initialize_database(con)
    master_category = categories.add_master_category(con, "Everyday Expenses")
    categories.add_budget_category(con, master_category["id"], "Groceries")
    con.close()
    # Qt requires QApplication instance to create widgets
    _app = QApplication.instance() or QApplication([])

    window = MainWindow(db_path)
    loaded_master = window.budgets[0].master_categories[0]
    subcategory_names = [subcategory.name for subcategory in loaded_master.subcategories]

    assert subcategory_names == ["Groceries"]
