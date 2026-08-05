from PyQt6.QtCore import QEvent, QObject, Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import QPushButton, QTableWidgetItem

from budget_model import format_money


def get_category(budget, category_name):
    # Shared lookup keeps table pages from duplicating category search behavior
    for category in budget.master_categories:
        if category.name == category_name:
            return category
    raise KeyError(category_name)


def numeric_font(bold=False):
    # Monospace digits keep date and money columns easy to scan
    weight = QFont.Weight.DemiBold if bold else QFont.Weight.Normal
    return QFont("Consolas", 10, weight)


class ButtonCursorFilter(QObject):
    def eventFilter(self, watched, event):
        if (
            isinstance(watched, QPushButton)
            and event.type() == QEvent.Type.Enter
        ):
            if watched.isEnabled():
                watched.setCursor(Qt.CursorShape.PointingHandCursor)
            else:
                watched.unsetCursor()
        return super().eventFilter(watched, event)


def install_button_hand_cursor(app):
    cursor_filter = ButtonCursorFilter(app)
    app.installEventFilter(cursor_filter)
    app.ez_budget_button_cursor_filter = cursor_filter


def money_item(amount, bold=False, negative_is_warning=False):
    # Centralized money cells keep alignment and formatting consistent across tables
    item = QTableWidgetItem(format_money(amount))
    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    item.setFont(numeric_font(bold))
    if negative_is_warning and amount < 0:
        item.setForeground(QColor("#c62828"))
    return item
