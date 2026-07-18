import os
from decimal import Decimal

import pytest

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
    budget_category = categories.add_budget_category(
        con,
        master_category["id"],
        "Groceries",
    )
    con.close()
    # Qt requires QApplication instance to create widgets
    _app = QApplication.instance() or QApplication([])

    window = MainWindow(db_path)
    loaded_master = window.budgets[0].master_categories[0]
    loaded_subcategory = loaded_master.subcategories[0]

    assert loaded_subcategory.name == "Groceries"
    assert loaded_subcategory.database_id == budget_category["id"]


def test_add_master_category_persists_and_updates_loaded_budgets():
    # Qt requires QApplication instance to create widgets
    _app = QApplication.instance() or QApplication([])
    window = MainWindow(":memory:")

    window.add_master_category("Savings")

    saved_category = categories.get_master_category_by_name(window.con, "Savings")
    loaded_names = [budget.master_categories[0].name for budget in window.budgets]
    loaded_ids = [budget.master_categories[0].database_id for budget in window.budgets]
    assert saved_category["name"] == "Savings"
    assert loaded_names == ["Savings"] * len(window.budgets)
    assert loaded_ids == [saved_category["id"]] * len(window.budgets)


def test_add_master_category_rejects_duplicate_name():
    # Qt requires QApplication instance to create widgets
    _app = QApplication.instance() or QApplication([])
    window = MainWindow(":memory:")
    window.add_master_category("Savings")

    with pytest.raises(ValueError, match="Master category already exists"):
        window.add_master_category("sAvInGs")

    category_rows = categories.list_master_categories(window.con)
    assert [category["name"] for category in category_rows] == ["Savings"]


def test_add_subcategory_persists_and_updates_loaded_budgets():
    # Qt requires QApplication instance to create widgets
    _app = QApplication.instance() or QApplication([])
    window = MainWindow(":memory:")
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


def test_add_subcategory_rejects_duplicate_name_within_master():
    # Qt requires QApplication instance to create widgets
    _app = QApplication.instance() or QApplication([])
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
