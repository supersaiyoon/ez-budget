import sys

from PyQt6.QtWidgets import QApplication, QInputDialog, QMessageBox

import budget_files
from ui.helpers import install_button_hand_cursor
from ui.main_window import MainWindow


def prompt_for_new_budget_path(directory=None):
    while True:
        budget_name, accepted = QInputDialog.getText(
            None,
            "Create Budget",
            "Enter budget name:",
        )
        if not accepted:
            return None

        try:
            db_path = budget_files.budget_path_from_name(
                budget_name,
                directory,
            )
        except ValueError as exc:
            QMessageBox.warning(None, "Create Budget", str(exc))
            continue

        if db_path.exists():
            QMessageBox.warning(
                None,
                "Create Budget",
                "A budget with that name already exists.",
            )
            continue
        return db_path


def startup_budget_path(settings=None, directory=None):
    existing_path = budget_files.existing_startup_budget(settings)
    if existing_path is not None:
        return existing_path
    return prompt_for_new_budget_path(directory)


def create_startup_window(settings=None, directory=None):
    if settings is None:
        settings = budget_files.application_settings()
    db_path = startup_budget_path(settings, directory)
    if db_path is None:
        return None

    window = MainWindow(db_path, global_settings=settings)
    budget_files.remember_budget_path(db_path, settings)
    return window


def main():
    # One QApplication instance for prompts and main window
    app = QApplication(sys.argv)
    install_button_hand_cursor(app)
    settings = budget_files.application_settings()
    window = create_startup_window(settings)
    if window is None:
        return 0

    app.active_budget_window = window
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
