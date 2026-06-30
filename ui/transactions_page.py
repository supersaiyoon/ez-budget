from functools import partial

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from budget_model import Transaction, format_money, parse_money


TRANSACTION_COLUMNS = ["Date", "Payee", "Category", "Notes", "Outgoing", "Incoming", "Cleared"]


class TransactionsPage(QWidget):
    def __init__(self, account, category_names):
        super().__init__()
        # Shared account object so edits update the main window's sample state
        self.account = account
        # Budget-derived categories keep transaction choices aligned with budget rows
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

        # Spreadsheet layout fits repeated transaction entry better than form pages
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

        # Fixed feedback line keeps validation messages from resizing the page
        self.status = QLabel("Edit transaction cells directly. Use Outgoing for payments and Incoming for refunds or income.")
        self.status.setObjectName("statusText")
        self.status.setFixedHeight(20)
        layout.addWidget(self.status)

        self.refresh()

    def refresh(self):
        # Balances recalculated from transactions so edited rows need no manual syncing
        self.summary.setText(
            f"Working balance: {format_money(self.account.working_balance)}    "
            f"Cleared balance: {format_money(self.account.cleared_balance)}"
        )
        # Extra row stays available for quick entry without an add button
        self.table.setRowCount(len(self.account.transactions) + 1)

        for row, transaction in enumerate(self.account.transactions):
            self._set_transaction_row(row, transaction)
        self._set_blank_row(len(self.account.transactions))

    def _set_transaction_row(self, row, transaction):
        # Editors bind directly to transaction fields for immediate lightweight edits
        self._set_text_input(row, 0, transaction.date, lambda value: setattr(transaction, "date", value))
        self._set_text_input(row, 1, transaction.payee, lambda value: setattr(transaction, "payee", value))
        self._set_category_input(row, transaction)
        self._set_text_input(row, 3, transaction.notes, lambda value: setattr(transaction, "notes", value))
        self._set_money_input(row, 4, transaction.outgoing, lambda value: setattr(transaction, "outgoing", value))
        self._set_money_input(row, 5, transaction.incoming, lambda value: setattr(transaction, "incoming", value))
        self._set_cleared_input(row, transaction)
        self.table.setRowHeight(row, 36)

    def _set_blank_row(self, row):
        # Blank row creates a transaction from whichever field user starts with
        self._set_new_transaction_input(row, 0)
        self._set_new_transaction_input(row, 1)

        category = QComboBox()
        category.setEditable(True)
        category.addItems(["", *self.category_names])
        # Category alone can be useful for starting an incomplete transaction
        category.currentTextChanged.connect(lambda value: self.create_transaction(category=value.strip()))
        self.table.setCellWidget(row, 2, category)

        self._set_new_transaction_input(row, 3)
        self._set_new_transaction_input(row, 4, money_column="outgoing")
        self._set_new_transaction_input(row, 5, money_column="incoming")

        checkbox = QCheckBox()
        # Cleared checkbox starts a row because reconciliation may happen before details
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
        # Partial keeps the source editor available after Qt emits no useful value
        input_field.editingFinished.connect(partial(self.create_transaction_from_input, column, input_field, money_column))
        self.table.setCellWidget(row, column, input_field)

    def create_transaction_from_input(self, column, input_field, money_column):
        value = input_field.text().strip()
        if not value:
            # Empty blur should not create placeholder transactions
            return

        if money_column:
            try:
                amount = parse_money(value)
            except ValueError as exc:
                # Bad money value left in place so user can correct it
                self.status.setText(str(exc))
                return
            self.create_transaction(**{money_column: amount})
            return

        fields = {
            0: "date",
            1: "payee",
            3: "notes",
        }
        # Column map keeps generic editor code from knowing transaction names
        self.create_transaction(**{fields[column]: value})

    def create_transaction(self, **values):
        if not any(value not in ("", None, False, 0) for value in values.values()):
            # Default-only edits ignored so checkbox setup cannot add empty rows
            return

        # Missing fields allowed so quick entry can start from any column
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
        # Full refresh replaces the blank row and updates balances together
        self.refresh()

    def _set_text_input(self, row, column, value, apply_value):
        input_field = QLineEdit(value)
        # Stored values trimmed to avoid accidental spaces in reports and filters
        input_field.editingFinished.connect(lambda: apply_value(input_field.text().strip()))
        self.table.setCellWidget(row, column, input_field)

    def _set_category_input(self, row, transaction):
        category = QComboBox()
        category.setEditable(True)
        # Editable combo allows new categories without blocking sample workflows
        category.addItems(self.category_names)
        category.setCurrentText(transaction.category)
        category.currentTextChanged.connect(lambda value: setattr(transaction, "category", value.strip()))
        self.table.setCellWidget(row, 2, category)

    def _set_money_input(self, row, column, value, apply_value):
        # Zero shown blank so empty money cells stay quick to scan
        input_field = QLineEdit("" if value == 0 else format(value, ".2f"))
        input_field.setFixedWidth(96)
        input_field.editingFinished.connect(partial(self.apply_money_value, input_field, apply_value))
        self.table.setCellWidget(row, column, input_field)

    def apply_money_value(self, input_field, apply_value):
        raw_value = input_field.text().strip()
        if not raw_value:
            # Clearing a money field means reset to zero
            apply_value(parse_money("0"))
            self.refresh()
            return

        try:
            amount = parse_money(raw_value)
        except ValueError as exc:
            # Keep invalid text visible so correction is direct
            self.status.setText(str(exc))
            return

        apply_value(amount)
        # Refresh needed because balances depend on both money columns
        self.refresh()

    def _set_cleared_input(self, row, transaction):
        checkbox = QCheckBox()
        checkbox.setChecked(transaction.cleared)
        checkbox.stateChanged.connect(lambda state: self.update_cleared(transaction, state))
        # Container centers checkbox inside table cell without custom delegate
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(checkbox)
        self.table.setCellWidget(row, 6, container)

    def update_cleared(self, transaction, state):
        # Qt state converted once so model stays plain Python bool
        transaction.cleared = state == Qt.CheckState.Checked.value
        self.refresh()
