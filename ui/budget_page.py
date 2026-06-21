from functools import partial

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QHeaderView,
    QLabel,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from budget_model import create_next_month_budget, format_money
from ui.helpers import get_category, money_item
from ui.widgets import MonthScroller, VISIBLE_MONTHS


class BudgetPage(QWidget):
    def __init__(self, budgets, on_budget_changed):
        super().__init__()
        self.budgets = budgets
        self.on_budget_changed = on_budget_changed
        self.start_index = 0
        self.rows = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 8)
        layout.setSpacing(3)

        self.month_scroller = MonthScroller(self.budgets, self.set_start_month)
        layout.addWidget(self.month_scroller, 0, Qt.AlignmentFlag.AlignTop)

        self.table = QTableWidget()
        self.table.setColumnCount(1 + (VISIBLE_MONTHS * 3))
        self.table.horizontalHeader().setVisible(False)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, self.table.columnCount()):
            self.table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table, 1)

        self.status = QLabel("Enter a positive or negative amount, then press Enter or leave the field.")
        self.status.setObjectName("statusText")
        self.status.setFixedHeight(20)
        layout.addWidget(self.status)

        self.refresh()

    def visible_budgets(self):
        return self.budgets[self.start_index : self.start_index + VISIBLE_MONTHS]

    def set_start_month(self, index):
        index = max(index, 0)
        created_future_month = False
        while index + VISIBLE_MONTHS > len(self.budgets):
            self.budgets.append(create_next_month_budget(self.budgets[-1]))
            created_future_month = True

        self.month_scroller.sync_buttons()
        self.start_index = index
        self.refresh()
        if created_future_month:
            self.on_budget_changed()

    def refresh(self):
        budgets = self.visible_budgets()
        self.month_scroller.set_active_months(self.start_index)
        self._refresh_budget_table(budgets)

    def _refresh_budget_table(self, budgets):
        self.rows = []
        for category in budgets[0].master_categories:
            self.rows.append((category.name, None))
            for subcategory in category.subcategories:
                self.rows.append((category.name, subcategory.name))

        self.table.clearSpans()
        self.table.setRowCount(len(self.rows) + 2)
        self._set_table_headers(budgets)
        for row, (category_name, subcategory_name) in enumerate(self.rows, start=2):
            if subcategory_name is None:
                self._set_master_row(row, category_name, budgets)
            else:
                self._set_subcategory_row(row, category_name, subcategory_name, budgets)

    def _set_table_headers(self, budgets):
        self.table.setItem(0, 0, QTableWidgetItem(""))

        category = QTableWidgetItem("Category")
        category.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        category.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(1, 0, category)

        for month_index, budget in enumerate(budgets):
            column = 1 + (month_index * 3)
            month = QTableWidgetItem(
                f"{budget.month_name}\n"
                f"Income: {format_money(budget.monthly_income)}\n"
                f"Available: {format_money(budget.available_to_budget)}\n"
                f"Budgeted: {format_money(budget.total_budgeted)}\n"
                f"Spent: {format_money(budget.total_spent)}"
            )
            month.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
            month.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(0, column, month)
            self.table.setSpan(0, column, 1, 3)

            for offset, label in enumerate(["Budgeted", "Spent", "Remaining"]):
                item = QTableWidgetItem(label)
                item.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(1, column + offset, item)

        self.table.setRowHeight(0, 98)
        self.table.setRowHeight(1, 30)

    def _set_master_row(self, row, category_name, budgets):
        title = QTableWidgetItem(category_name)
        title.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        title.setBackground(Qt.GlobalColor.lightGray)
        self.table.setItem(row, 0, title)

        for month_index, budget in enumerate(budgets):
            category = get_category(budget, category_name)
            column = 1 + (month_index * 3)
            self.table.setItem(row, column, QTableWidgetItem(""))
            self.table.setItem(row, column + 1, money_item(category.spent, bold=True))
            self.table.setItem(row, column + 2, money_item(category.remaining, bold=True))
        self.table.setRowHeight(row, 34)

    def _set_subcategory_row(self, row, category_name, subcategory_name, budgets):
        self.table.setItem(row, 0, QTableWidgetItem(f"   {subcategory_name}"))

        for month_index, budget in enumerate(budgets):
            subcategory = budget.get_subcategory(category_name, subcategory_name)
            column = 1 + (month_index * 3)
            input_field = QLineEdit()
            input_field.setPlaceholderText("+100 or -25")
            input_field.setFixedWidth(116)
            input_field.editingFinished.connect(
                partial(self.apply_adjustment, budget, category_name, subcategory_name, input_field)
            )

            self.table.setCellWidget(row, column, input_field)
            self.table.setItem(row, column + 1, money_item(subcategory.spent))
            self.table.setItem(row, column + 2, money_item(subcategory.remaining))
        self.table.setRowHeight(row, 38)

    def apply_adjustment(self, budget, category_name, subcategory_name, input_field):
        raw_value = input_field.text().strip()
        if not raw_value:
            return

        try:
            amount = budget.apply_adjustment(category_name, subcategory_name, raw_value)
        except ValueError as exc:
            self.status.setText(str(exc))
            return

        input_field.clear()
        self.status.setText(
            f"{budget.month_name}: applied {format_money(amount)} to {subcategory_name}. "
            f"Available: {format_money(budget.available_to_budget)}"
        )
        self.refresh()
        self.on_budget_changed()
