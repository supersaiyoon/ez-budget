import sys
from functools import partial

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QHeaderView,
    QCheckBox,
    QComboBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from budget_model import (
    Transaction,
    create_next_month_budget,
    create_sample_accounts,
    create_sample_budgets,
    format_money,
    parse_money,
)


VISIBLE_MONTHS = 2
TRANSACTION_COLUMNS = ["Date", "Payee", "Category", "Notes", "Outgoing", "Incoming", "Cleared"]


class MonthScroller(QWidget):
    def __init__(self, budgets, on_month_selected):
        super().__init__()
        self.setFixedHeight(40)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.budgets = budgets
        self.on_month_selected = on_month_selected
        self.buttons = []

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.previous_button = QPushButton("<")
        self.previous_button.setObjectName("monthArrow")
        self.previous_button.clicked.connect(partial(self.shift_months, -1))
        layout.addWidget(self.previous_button)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFixedHeight(36)

        scroll_content = QWidget()
        self.scroll_layout = QHBoxLayout(scroll_content)
        self.scroll_layout.setContentsMargins(3, 3, 3, 3)
        self.scroll_layout.setSpacing(4)
        self.sync_buttons()

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        self.next_button = QPushButton(">")
        self.next_button.setObjectName("monthArrow")
        self.next_button.clicked.connect(partial(self.shift_months, 1))
        layout.addWidget(self.next_button)

    def shift_months(self, direction):
        active_index = next((index for index, button in enumerate(self.buttons) if button.property("active")), 0)
        self.on_month_selected(active_index + direction)

    def sync_buttons(self):
        for index in range(len(self.buttons), len(self.budgets)):
            button = QPushButton(self.budgets[index].month_name)
            button.setObjectName("monthButton")
            button.clicked.connect(partial(self.on_month_selected, index))
            self.scroll_layout.addWidget(button)
            self.buttons.append(button)

    def set_active_months(self, start_index):
        for index, button in enumerate(self.buttons):
            button.setProperty("active", start_index <= index < start_index + VISIBLE_MONTHS)
            button.style().unpolish(button)
            button.style().polish(button)


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


class ReportsPage(QWidget):
    def __init__(self, budgets):
        super().__init__()
        self.budgets = budgets

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        title = QLabel("Reports")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        description = QLabel("Sample monthly report data")
        description.setObjectName("statusText")
        layout.addWidget(description)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Month", "Income", "Budgeted", "Spent", "Remaining"])
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        self.refresh()

    def refresh(self):
        self.table.setRowCount(len(self.budgets))
        for row, budget in enumerate(self.budgets):
            self.table.setItem(row, 0, QTableWidgetItem(budget.month_name))
            self.table.setItem(row, 1, money_item(budget.monthly_income))
            self.table.setItem(row, 2, money_item(budget.total_budgeted))
            self.table.setItem(row, 3, money_item(budget.total_spent))
            self.table.setItem(row, 4, money_item(budget.total_remaining))


class TransactionsPage(QWidget):
    def __init__(self, account, category_names):
        super().__init__()
        self.account = account
        self.category_names = category_names

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        heading = QLabel(account.name)
        heading.setObjectName("pageTitle")
        layout.addWidget(heading)

        self.summary = QLabel()
        self.summary.setObjectName("statusText")
        layout.addWidget(self.summary)

        self.table = QTableWidget()
        self.table.setColumnCount(len(TRANSACTION_COLUMNS))
        self.table.setHorizontalHeaderLabels(TRANSACTION_COLUMNS)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table, 1)

        self.status = QLabel("Edit transaction cells directly. Use Outgoing for payments and Incoming for refunds or income.")
        self.status.setObjectName("statusText")
        self.status.setFixedHeight(20)
        layout.addWidget(self.status)

        self.refresh()

    def refresh(self):
        self.summary.setText(
            f"Working balance: {format_money(self.account.working_balance)}    "
            f"Cleared balance: {format_money(self.account.cleared_balance)}"
        )
        self.table.setRowCount(len(self.account.transactions) + 1)

        for row, transaction in enumerate(self.account.transactions):
            self._set_transaction_row(row, transaction)
        self._set_blank_row(len(self.account.transactions))

    def _set_transaction_row(self, row, transaction):
        self._set_text_input(row, 0, transaction.date, lambda value: setattr(transaction, "date", value))
        self._set_text_input(row, 1, transaction.payee, lambda value: setattr(transaction, "payee", value))
        self._set_category_input(row, transaction)
        self._set_text_input(row, 3, transaction.notes, lambda value: setattr(transaction, "notes", value))
        self._set_money_input(row, 4, transaction.outgoing, lambda value: setattr(transaction, "outgoing", value))
        self._set_money_input(row, 5, transaction.incoming, lambda value: setattr(transaction, "incoming", value))
        self._set_cleared_input(row, transaction)
        self.table.setRowHeight(row, 36)

    def _set_blank_row(self, row):
        self._set_new_transaction_input(row, 0)
        self._set_new_transaction_input(row, 1)

        category = QComboBox()
        category.setEditable(True)
        category.addItems(["", *self.category_names])
        category.currentTextChanged.connect(lambda value: self.create_transaction(category=value.strip()))
        self.table.setCellWidget(row, 2, category)

        self._set_new_transaction_input(row, 3)
        self._set_new_transaction_input(row, 4, money_column="outgoing")
        self._set_new_transaction_input(row, 5, money_column="incoming")

        checkbox = QCheckBox()
        checkbox.stateChanged.connect(lambda state: self.create_transaction(cleared=state == Qt.CheckState.Checked.value))
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(checkbox)
        self.table.setCellWidget(row, 6, container)
        self.table.setRowHeight(row, 30)

    def _set_new_transaction_input(self, row, column, money_column=None):
        input_field = QLineEdit()
        input_field.editingFinished.connect(partial(self.create_transaction_from_input, column, input_field, money_column))
        self.table.setCellWidget(row, column, input_field)

    def create_transaction_from_input(self, column, input_field, money_column):
        value = input_field.text().strip()
        if not value:
            return

        if money_column:
            try:
                amount = parse_money(value)
            except ValueError as exc:
                self.status.setText(str(exc))
                return
            self.create_transaction(**{money_column: amount})
            return

        fields = {
            0: "date",
            1: "payee",
            3: "notes",
        }
        self.create_transaction(**{fields[column]: value})

    def create_transaction(self, **values):
        if not any(value not in ("", None, False, 0) for value in values.values()):
            return

        transaction = Transaction(
            values.get("date", ""),
            values.get("payee", ""),
            values.get("category", ""),
            values.get("notes", ""),
            values.get("outgoing", parse_money("0")),
            values.get("incoming", parse_money("0")),
            values.get("cleared", False),
        )
        self.account.transactions.append(transaction)
        self.refresh()

    def _set_text_input(self, row, column, value, apply_value):
        input_field = QLineEdit(value)
        input_field.editingFinished.connect(lambda: apply_value(input_field.text().strip()))
        self.table.setCellWidget(row, column, input_field)

    def _set_category_input(self, row, transaction):
        category = QComboBox()
        category.setEditable(True)
        category.addItems(self.category_names)
        category.setCurrentText(transaction.category)
        category.currentTextChanged.connect(lambda value: setattr(transaction, "category", value.strip()))
        self.table.setCellWidget(row, 2, category)

    def _set_money_input(self, row, column, value, apply_value):
        input_field = QLineEdit("" if value == 0 else format(value, ".2f"))
        input_field.setFixedWidth(96)
        input_field.editingFinished.connect(partial(self.apply_money_value, input_field, apply_value))
        self.table.setCellWidget(row, column, input_field)

    def apply_money_value(self, input_field, apply_value):
        raw_value = input_field.text().strip()
        if not raw_value:
            apply_value(parse_money("0"))
            self.refresh()
            return

        try:
            amount = parse_money(raw_value)
        except ValueError as exc:
            self.status.setText(str(exc))
            return

        apply_value(amount)
        self.refresh()

    def _set_cleared_input(self, row, transaction):
        checkbox = QCheckBox()
        checkbox.setChecked(transaction.cleared)
        checkbox.stateChanged.connect(lambda state: self.update_cleared(transaction, state))
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(checkbox)
        self.table.setCellWidget(row, 6, container)

    def update_cleared(self, transaction, state):
        transaction.cleared = state == Qt.CheckState.Checked.value
        self.refresh()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.budgets = create_sample_budgets()
        self.accounts = create_sample_accounts()
        self.setWindowTitle("EZ Budget Prototype")
        self.resize(1160, 720)

        shell = QWidget()
        shell_layout = QHBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)

        self.nav = QListWidget()
        self.nav.setObjectName("navList")
        self.nav.setFixedWidth(170)
        for name in ["Budget", "Checking", "Credit Card", "Reports"]:
            item = QListWidgetItem(name)
            item.setSizeHint(item.sizeHint())
            self.nav.addItem(item)
        shell_layout.addWidget(self.nav)

        self.stack = QStackedWidget()
        self.budget_page = BudgetPage(self.budgets, self.refresh_reports)
        self.checking_page = TransactionsPage(self.accounts[0], self.category_names())
        self.credit_card_page = TransactionsPage(self.accounts[1], self.category_names())
        self.reports_page = ReportsPage(self.budgets)
        self.stack.addWidget(self.budget_page)
        self.stack.addWidget(self.checking_page)
        self.stack.addWidget(self.credit_card_page)
        self.stack.addWidget(self.reports_page)
        shell_layout.addWidget(self.stack)

        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)
        self.setCentralWidget(shell)
        self.setStyleSheet(APP_STYLE)

    def refresh_reports(self):
        self.reports_page.refresh()

    def category_names(self):
        names = ["Income"]
        for category in self.budgets[0].master_categories:
            for subcategory in category.subcategories:
                names.append(subcategory.name)
        return names


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


APP_STYLE = """
QMainWindow {
    background: #f5f7f9;
}
#navList {
    background: #26323f;
    color: #f7fafc;
    border: 0;
    padding-top: 14px;
    font-size: 15px;
}
#navList::item {
    padding: 14px 18px;
}
#navList::item:selected {
    background: #3f5f7a;
}
#pageTitle {
    font-size: 28px;
    font-weight: 700;
    color: #1f2933;
}
#statusText {
    color: #4d5b6a;
}
#monthButton {
    background: #ffffff;
    color: #26323f;
    border: 1px solid #c8d1dc;
    border-radius: 4px;
    padding: 5px 12px;
}
#monthButton[active="true"] {
    background: #2f6f8f;
    color: #ffffff;
    border-color: #2f6f8f;
}
#monthArrow {
    min-width: 36px;
    max-width: 36px;
    padding: 5px 0;
}
QScrollArea {
    border: 1px solid #d8dee6;
    background: #ffffff;
}
QTableWidget {
    background: #ffffff;
    border: 1px solid #d8dee6;
    gridline-color: #e5e9ef;
    alternate-background-color: #f8fafc;
}
QHeaderView::section {
    background: #eef2f6;
    color: #1f2933;
    border: 0;
    border-right: 1px solid #d8dee6;
    padding: 8px;
    font-weight: 700;
}
QLineEdit {
    padding: 5px 7px;
    border: 1px solid #b8c2cc;
    border-radius: 4px;
}
QPushButton {
    padding: 6px 10px;
    background: #2f6f8f;
    color: white;
    border: 0;
    border-radius: 4px;
}
QPushButton:hover {
    background: #255d78;
}
"""


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
