import os

import pytest


# Offscreen rendering lets Qt widgets run in automated tests without a display
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    # One application instance is shared because Qt permits only one per process
    return QApplication.instance() or QApplication([])
