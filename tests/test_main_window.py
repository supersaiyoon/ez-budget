import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from ui.main_window import MainWindow


def test_nav_uses_account_table_names():
    # Qt requires QApplication instance to create widgets
    _app = QApplication.instance() or QApplication([])
    window = MainWindow()

    nav_names = []
    for row in range(window.nav.count()):
        nav_names.append(window.nav.item(row).text())

    assert nav_names == ["Budget", "Checking", "Credit Card", "Reports"]


def test_sample_accounts_are_not_duplicated():
    # Qt requires QApplication instance to create widgets
    _app = QApplication.instance() or QApplication([])
    window = MainWindow()

    window.create_sample_account_rows()

    assert window.nav_names() == ["Budget", "Checking", "Credit Card", "Reports"]
