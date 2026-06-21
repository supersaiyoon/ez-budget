from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QTableWidgetItem

from budget_model import format_money


def get_category(budget, category_name):
    for category in budget.master_categories:
        if category.name == category_name:
            return category
    raise KeyError(category_name)


def money_item(amount, bold=False):
    item = QTableWidgetItem(format_money(amount))
    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    if bold:
        item.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
    return item
