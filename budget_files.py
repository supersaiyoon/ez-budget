import sys
from pathlib import Path

from PyQt6.QtCore import QSettings


SETTINGS_ORGANIZATION = "EZ Budget"
SETTINGS_APPLICATION = "EZ Budget"
LAST_BUDGET_PATH_KEY = "last_budget_path"
INVALID_FILENAME_CHARACTERS = '<>:"/\\|?*'
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}


def application_directory():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def application_settings():
    return QSettings(SETTINGS_ORGANIZATION, SETTINGS_APPLICATION)


def remember_budget_path(db_path, settings=None):
    if settings is None:
        settings = application_settings()
    resolved_path = str(Path(db_path).resolve())
    settings.setValue(LAST_BUDGET_PATH_KEY, resolved_path)
    settings.sync()


def existing_startup_budget(settings=None):
    if settings is None:
        settings = application_settings()
    saved_path = settings.value(LAST_BUDGET_PATH_KEY, "", type=str)
    if saved_path and Path(saved_path).is_file():
        return Path(saved_path).resolve()
    return None


def budget_path_from_name(name, directory=None):
    budget_name = name.strip()
    if budget_name.casefold().endswith(".db"):
        budget_name = budget_name[:-3].rstrip()

    if not budget_name:
        raise ValueError("Enter a budget name.")
    if any(character in budget_name for character in INVALID_FILENAME_CHARACTERS):
        raise ValueError("Budget name cannot contain file-name symbols.")
    if budget_name.endswith((".", " ")):
        raise ValueError("Budget name cannot end with a period or space.")
    if budget_name.upper() in WINDOWS_RESERVED_NAMES:
        raise ValueError("Choose a different budget name.")

    if directory is None:
        directory = application_directory()
    directory = Path(directory)
    return directory / f"{budget_name}.db"
