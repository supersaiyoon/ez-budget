import os
from decimal import Decimal

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from db import accounts
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
