import pytest

from PyQt6.QtCore import QSettings

import budget_files
import main


def test_named_budget_is_created_and_reopened_on_next_startup(
    tmp_path,
    monkeypatch,
    qapp,
):
    settings = QSettings(
        str(tmp_path / "settings.ini"),
        QSettings.Format.IniFormat,
    )
    monkeypatch.setattr(
        main.QInputDialog,
        "getText",
        lambda *args: ("Family Budget", True),
    )

    window = main.create_startup_window(settings, tmp_path)

    db_path = tmp_path / "Family Budget.db"
    assert db_path.is_file()
    assert window.db_path == db_path
    assert window.budget_name_label.text() == "Family Budget"
    window.close()
    window.con.close()

    monkeypatch.setattr(
        main.QInputDialog,
        "getText",
        lambda *args: pytest.fail("Saved budget should reopen without prompting"),
    )
    reopened_window = main.create_startup_window(settings, tmp_path)

    assert reopened_window.db_path == db_path
    reopened_window.close()
    reopened_window.con.close()
