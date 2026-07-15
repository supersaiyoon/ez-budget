import os

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
