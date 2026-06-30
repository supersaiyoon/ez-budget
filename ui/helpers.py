from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QTableWidgetItem

from budget_model import format_money


def get_category(budget, category_name):
    # Shared lookup keeps table pages from duplicating category search behavior
    for category in budget.master_categories:
        if category.name == category_name:
            return category
    raise KeyError(category_name)


def money_item(amount, bold=False):
    # Centralized money cells keep alignment and formatting consistent across tables
    item = QTableWidgetItem(format_money(amount))
    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    if bold:
        # Bold option reserved for subtotal rows that need stronger scan weight
        item.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
    return item
