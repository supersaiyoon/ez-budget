import os

import pytest


# Offscreen rendering lets Qt widgets run in automated tests without a display
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from db import database


@pytest.fixture
def con():
    # Each database-helper test receives an isolated initialized connection
    connection = database.connect(":memory:")
    database.initialize_database(connection)
    yield connection
    connection.close()


@pytest.fixture(scope="session")
def qapp():
    # One application instance is shared because Qt permits only one per process
    return QApplication.instance() or QApplication([])
