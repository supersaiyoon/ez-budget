import pytest

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtWidgets import QApplication, QPushButton

from ui.helpers import ButtonCursorFilter


pytestmark = pytest.mark.usefixtures("qapp")


def test_button_hover_uses_pointing_hand_cursor(qapp):
    button = QPushButton("Save")
    cursor_filter = ButtonCursorFilter(button)

    QApplication.sendEvent(button, QEvent(QEvent.Type.Enter))
    cursor_filter.eventFilter(button, QEvent(QEvent.Type.Enter))

    assert button.cursor().shape() == Qt.CursorShape.PointingHandCursor
