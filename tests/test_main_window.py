import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from ui.main_window import MainWindow


def test_nav_uses_account_table_names():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    nav_names = []
    for row in range(window.nav.count()):
        nav_names.append(window.nav.item(row).text())

    assert nav_names == ["Budget", "Checking", "Credit Card", "Reports"]
