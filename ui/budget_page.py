from functools import partial

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QHeaderView,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from budget_model import create_next_month_budget, format_money
from ui.helpers import get_category, money_item
from ui.widgets import MonthScroller, VISIBLE_MONTHS, VISIBLE_SCROLLER_MONTHS


class BudgetPage(QWidget):
    def __init__(self, budgets, on_budget_changed, on_master_category_added):
        super().__init__()
        # Shared list so generated months and edits stay visible to other pages
        self.budgets = budgets
        
        # Only signals changed budget data
        self.on_budget_changed = on_budget_changed
        self.on_master_category_added = on_master_category_added
        self.active_index = 0

        # For matching visual rows back to category names
        self.rows = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 8)
        layout.setSpacing(3)

        self.month_scroller = MonthScroller(self.set_active_month)
        layout.addWidget(self.month_scroller, 0, Qt.AlignmentFlag.AlignTop)

        # Side-by-side month comparison
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

        self.category_header = QWidget()
        category_header_layout = QHBoxLayout(self.category_header)
        category_header_layout.setContentsMargins(8, 0, 8, 0)
        category_label = QLabel("Category")
        category_label.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        category_header_layout.addWidget(category_label)
        category_header_layout.addStretch()
        self.add_master_category_button = QPushButton("+")
        self.add_master_category_button.setObjectName("addMasterCategoryButton")
        self.add_master_category_button.setToolTip("Add master category")
        self.add_master_category_button.setFixedWidth(28)
        self.add_master_category_button.clicked.connect(self.prompt_for_master_category)
        category_header_layout.addWidget(self.add_master_category_button)

        self.status = QLabel("Enter a positive or negative amount, then press Enter or leave the field.")
        self.status.setObjectName("statusText")
        self.status.setFixedHeight(20)
        layout.addWidget(self.status)

        self.refresh()

    def visible_budgets(self):
        # Active month plus neighbors, matching the comparison window width
        return self.budgets[self.active_index : self.active_index + VISIBLE_MONTHS]

    def visible_scroller_indexes(self):
        # Centered window when possible, easier context while stepping through months
        half_window = VISIBLE_SCROLLER_MONTHS // 2
        start_index = max(self.active_index - half_window, 0)
        return range(start_index, start_index + VISIBLE_SCROLLER_MONTHS)

    def set_active_month(self, index):
        # Clamp left edge so arrow clicks cannot ask for a negative month
        self.active_index = max(index, 0)
        created_future_month = self.ensure_visible_months()
        self.refresh()

        # Persist only when navigation forced new budget data into existence
        if created_future_month:
            self.on_budget_changed()

    def ensure_visible_months(self):
        # Scroller can look farther ahead than the table, so both ranges need backing data
        scroller_indexes = list(self.visible_scroller_indexes())
        count = max(self.active_index + VISIBLE_MONTHS, scroller_indexes[-1] + 1)
        created_future_month = False

        while count > len(self.budgets):
            # Future month starts clean while preserving category structure and income
            self.budgets.append(create_next_month_budget(self.budgets[-1]))
            created_future_month = True
        return created_future_month

    def refresh(self):
        # Regenerate from model state so edits, generated months, and summaries stay aligned
        self.ensure_visible_months()
        scroller_indexes = list(self.visible_scroller_indexes())
        budgets = self.visible_budgets()
        indexed_budgets = [(index, self.budgets[index]) for index in scroller_indexes]
        self.month_scroller.set_months(indexed_budgets, self.active_index)
        self._refresh_budget_table(budgets)

    def _refresh_budget_table(self, budgets):
        self.rows = []
        for category in budgets[0].master_categories:
            # Master rows anchor groups before subcategory rows add editable detail
            self.rows.append((category.name, None))
            for subcategory in category.subcategories:
                self.rows.append((category.name, subcategory.name))

        # Two header rows leave room for month summary plus per-month money columns
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

        # Category header separated from month headers for scan-friendly budgeting
        if self.table.cellWidget(1, 0) is None:
            self.table.setCellWidget(1, 0, self.category_header)

        for month_index, budget in enumerate(budgets):
            # Month group owns three child columns, keeping totals close to inputs
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

            # Comparing months side by side
            for offset, label in enumerate(["Budgeted", "Spent", "Remaining"]):
                item = QTableWidgetItem(label)
                item.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(1, column + offset, item)

        self.table.setRowHeight(0, 98)
        self.table.setRowHeight(1, 30)

    def prompt_for_master_category(self):
        name, accepted = QInputDialog.getText(
            self,
            "Add Master Category",
            "Master category name:",
        )
        if accepted:
            self.submit_master_category_name(name)

    def submit_master_category_name(self, name):
        name = name.strip()
        if not name:
            self.status.setText("Enter a master category name.")
            return

        try:
            self.on_master_category_added(name)
        except ValueError as exc:
            self.status.setText(str(exc))
            return

        self.status.setText(f'Added master category "{name}".')

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
            # Keep bad input in place so user can fix it without retyping
            self.status.setText(str(exc))
            return

        # Clear after success so repeated adjustments are intentional
        input_field.clear()
        self.status.setText(
            f"{budget.month_name}: applied {format_money(amount)} to {subcategory_name}. "
            f"Available: {format_money(budget.available_to_budget)}"
        )

        self.refresh()
        self.on_budget_changed()
