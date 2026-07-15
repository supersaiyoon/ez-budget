import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from db import categories
from ui.main_window import MainWindow


def test_nav_uses_account_table_names():
    # Qt requires QApplication instance to create widgets
    _app = QApplication.instance() or QApplication([])
    window = MainWindow(":memory:")

    nav_names = []
    for row in range(window.nav.count()):
        nav_names.append(window.nav.item(row).text())

    assert nav_names == ["Budget", "Checking", "Credit Card", "Reports"]


def test_sample_accounts_are_not_duplicated():
    # Qt requires QApplication instance to create widgets
    _app = QApplication.instance() or QApplication([])
    window = MainWindow(":memory:")

    window.create_sample_account_rows()

    assert window.nav_names() == ["Budget", "Checking", "Credit Card", "Reports"]


def test_sample_budget_categories_are_created():
    # Qt requires QApplication instance to create widgets
    _app = QApplication.instance() or QApplication([])
    window = MainWindow(":memory:")

    master_category = categories.get_master_category_by_name(
        window.con,
        "Everyday Spending",
    )
    category = categories.get_budget_category_by_name(window.con, "Groceries")

    assert master_category["name"] == "Everyday Spending"
    assert category["name"] == "Groceries"
    assert category["master_budget_category_id"] == master_category["id"]
