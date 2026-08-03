from datetime import date
from functools import partial
from pathlib import Path

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QColor, QIcon, QPalette
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QCompleter,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from budget_model import (
    Transaction,
    format_money,
    format_transaction_date,
    income_target_month_dates,
    parse_money,
    parse_transaction_date,
)
from ui.helpers import numeric_font


TRANSACTION_COLUMNS = [
    "Date",
    "Payee",
    "Category",
    "Notes",
    "Outgoing",
    "Incoming",
    "Cleared",
    "",  # Icon-only delete column
]
INCOME_PAYEE_PLACEHOLDER = "Not needed for income"
DELETE_ICON_PATH = (
    Path(__file__).parent / "assets" / "icons" / "delete.svg"
)
TRANSACTION_DATE_COLUMN_WIDTH = 104
TRANSACTION_CATEGORY_COLUMN_WIDTH = 148
TRANSACTION_MONEY_COLUMN_WIDTH = 88
TRANSACTION_CLEARED_COLUMN_WIDTH = 68
TRANSACTION_DELETE_COLUMN_WIDTH = 40


class TransactionsPage(QWidget):
    def __init__(
        self,
        account,
        category_rows,
        on_transaction_changed=None,
        income_category_id=None,
        on_transaction_delete_requested=None,
        income_reference_date=None,
        on_account_close_requested=None,
        on_account_reopen_requested=None,
        on_account_delete_requested=None,
        allow_new_transactions=True,
        payee_names=None,
    ):
        super().__init__()

        # Shared account object so edits update the main window's sample state
        self.account = account

        # Joined rows retain category ids and their parent display groups
        self.category_rows = category_rows

        # Optional callback keeps persistence outside this UI-only page
        self.on_transaction_changed = on_transaction_changed

        # Hidden category ID backs virtual income choices
        self.income_category_id = income_category_id

        # Controller owns persistence and decides whether deletion succeeded
        self.on_transaction_delete_requested = on_transaction_delete_requested

        # Current planning month keeps income labels stable across transaction dates
        self.income_reference_date = (
            income_reference_date or date.today().replace(day=1).isoformat()
        )

        # Controller owns account collection and navigation changes
        self.on_account_close_requested = on_account_close_requested

        # Closed pages expose the reverse account lifecycle action
        self.on_account_reopen_requested = on_account_reopen_requested

        # Controller checks history before allowing permanent account deletion
        self.on_account_delete_requested = on_account_delete_requested

        # Closed account pages keep history visible without blank entry row
        self.allow_new_transactions = allow_new_transactions

        # Payee suggestions stay optional so tests and UI-only pages can stay simple
        self.payee_names = payee_names or []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        heading_layout = QHBoxLayout()
        heading = QLabel(account.name)
        heading.setObjectName("pageTitle")
        heading_layout.addWidget(heading)
        self.reopen_account_button = QPushButton("Reopen")
        self.reopen_account_button.setObjectName("reopenAccountButton")
        self.reopen_account_button.clicked.connect(self.request_account_reopen)
        self.reopen_account_button.setVisible(not self.allow_new_transactions)
        heading_layout.addWidget(self.reopen_account_button)
        heading_layout.addStretch()
        layout.addLayout(heading_layout)

        # Account action stays separate from transaction-row actions
        account_actions = QHBoxLayout()
        account_actions.addStretch()
        self.close_account_button = QPushButton("Close Account")
        self.close_account_button.setObjectName("closeAccountButton")
        self.close_account_button.clicked.connect(self.request_account_close)
        account_actions.addWidget(self.close_account_button)
        self.delete_account_button = QPushButton("Delete Account")
        self.delete_account_button.setObjectName("deleteAccountButton")
        self.delete_account_button.clicked.connect(self.request_account_delete)
        account_actions.addWidget(self.delete_account_button)

        # Closed history pages omit actions that only apply while active
        self.close_account_button.setVisible(self.allow_new_transactions)
        self.delete_account_button.setVisible(self.allow_new_transactions)
        layout.addLayout(account_actions)

        self.summary = QLabel()
        self.summary.setObjectName("statusText")
        layout.addWidget(self.summary)

        # Spreadsheet layout fits repeated transaction entry better than form pages
        self.table = QTableWidget()
        self.table.setColumnCount(len(TRANSACTION_COLUMNS))
        self.table.setHorizontalHeaderLabels(TRANSACTION_COLUMNS)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, TRANSACTION_DATE_COLUMN_WIDTH)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(2, TRANSACTION_CATEGORY_COLUMN_WIDTH)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(4, TRANSACTION_MONEY_COLUMN_WIDTH)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(5, TRANSACTION_MONEY_COLUMN_WIDTH)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(6, TRANSACTION_CLEARED_COLUMN_WIDTH)
        self.table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(7, TRANSACTION_DELETE_COLUMN_WIDTH)
        layout.addWidget(self.table, 1)

        # Fixed feedback line keeps validation messages from resizing the page
        self.status = QLabel("Edit transaction cells directly. Use Outgoing for payments and Incoming for refunds or income.")
        self.status.setObjectName("statusText")
        self.status.setFixedHeight(20)
        layout.addWidget(self.status)

        self.refresh()

    def set_payee_names(self, payee_names):
        # Existing editors rebuild so suggestions reflect latest saved payees
        self.payee_names = payee_names
        self.refresh()

    def refresh(self):
        # Balances recalculated from transactions so edited rows need no manual syncing
        self.summary.setText(
            f"Working balance: {format_money(self.account.working_balance)}    "
            f"Cleared balance: {format_money(self.account.cleared_balance)}"
        )
        # Active pages reserve one extra row for quick transaction entry
        extra_row_count = 1 if self.allow_new_transactions else 0
        self.table.setRowCount(
            len(self.account.transactions) + extra_row_count
        )

        for row, transaction in enumerate(self.account.transactions):
            self._set_transaction_row(row, transaction)
        if self.allow_new_transactions:
            self._set_blank_row(len(self.account.transactions))

    def set_category_rows(self, category_rows):
        # Rebuild dropdowns when persistent category choices change at runtime
        self.category_rows = category_rows
        self.refresh()

    def income_category_options(self, transaction_date):
        # Missing system ID or usable date leaves special choices unavailable
        if self.income_category_id is None or not transaction_date:
            return []
        try:
            date.fromisoformat(transaction_date)
            this_month, following_month = income_target_month_dates(
                self.income_reference_date
            )
        except ValueError:
            return []

        # Friendly labels retain concrete month assignments in option data
        return [
            {
                "database_id": self.income_category_id,
                "name": "Income for this month",
                "income_month_date": this_month,
            },
            {
                "database_id": self.income_category_id,
                "name": "Income for next month",
                "income_month_date": following_month,
            },
        ]

    def _set_transaction_row(self, row, transaction):
        # Editors bind directly to transaction fields for immediate lightweight edits
        self._set_date_input(row, transaction)
        payee_input = self._set_text_input(
            row,
            1,
            transaction.payee,
            lambda value: self._update_transaction_field(transaction, "payee", value),
        )
        if transaction.payee == INCOME_PAYEE_PLACEHOLDER:
            # Muted italic treatment distinguishes automatic value from real payee
            placeholder_font = payee_input.font()
            placeholder_font.setItalic(True)
            payee_input.setFont(placeholder_font)
            placeholder_palette = payee_input.palette()
            placeholder_palette.setColor(
                QPalette.ColorRole.Text,
                QColor("#7a8794"),
            )
            payee_input.setPalette(placeholder_palette)
        self._set_category_input(row, transaction)
        self._set_text_input(
            row,
            3,
            transaction.notes,
            lambda value: self._update_transaction_field(transaction, "notes", value),
        )
        self._set_money_input(
            row,
            4,
            transaction.outgoing,
            lambda value: self._update_transaction_field(transaction, "outgoing", value),
        )
        self._set_money_input(
            row,
            5,
            transaction.incoming,
            lambda value: self._update_transaction_field(transaction, "incoming", value),
        )
        self._set_cleared_input(row, transaction)
        self._set_delete_button(row, transaction)
        self.table.setRowHeight(row, 36)

    def _set_blank_row(self, row):
        # Blank row creates a transaction from whichever field user starts with
        self._set_new_transaction_input(row, 0)
        self._set_new_transaction_input(row, 1)

        category = QComboBox()
        self._populate_category_input(category)

        # Category alone can be useful for starting an incomplete transaction
        category.currentIndexChanged.connect(
            lambda: self.create_transaction_from_category(category)
        )
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
        if column == 1:
            self._add_payee_completer(input_field)
        if column == 0:
            input_field.setAlignment(Qt.AlignmentFlag.AlignCenter)
            input_field.setFont(numeric_font())
        if money_column is not None:
            input_field.setAlignment(Qt.AlignmentFlag.AlignRight)
            input_field.setFont(numeric_font())

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

        if column == 0:
            try:
                value = parse_transaction_date(value)
            except ValueError as exc:
                # Invalid date stays visible in blank row for direct correction
                self.status.setText(str(exc))
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
            date=values.get("date", ""),
            payee=values.get("payee", ""),
            category=values.get("category", ""),
            notes=values.get("notes", ""),
            outgoing=values.get("outgoing", parse_money("0")),
            incoming=values.get("incoming", parse_money("0")),
            cleared=values.get("cleared", False),
            category_database_id=values.get("category_database_id"),
        )
        self.account.transactions.append(transaction)
        self._notify_transaction_changed(transaction)
        # Full refresh replaces the blank row and updates balances together
        self.refresh()

    def _update_transaction_field(self, transaction, field, value):
        # Central update path ensures every editor reports the same model change
        setattr(transaction, field, value)
        self._notify_transaction_changed(transaction)

    def _notify_transaction_changed(self, transaction):
        # Tests and MainWindow can react without TransactionsPage knowing why
        if self.on_transaction_changed is None:
            return

        saved = self.on_transaction_changed(self.account, transaction)
        if saved:
            self.status.setText("Transaction saved.")
            return

        # Partial row remains editable while status makes pending state explicit
        self.status.setText(
            "Not saved yet: enter date, payee, category, and one amount."
        )

    def _set_text_input(self, row, column, value, apply_value):
        input_field = QLineEdit(value)
        if column == 1:
            self._add_payee_completer(input_field)
        # Stored values trimmed to avoid accidental spaces in reports and filters
        input_field.editingFinished.connect(lambda: apply_value(input_field.text().strip()))
        self.table.setCellWidget(row, column, input_field)
        return input_field

    def _add_payee_completer(self, input_field):
        completer = QCompleter(self.payee_names, input_field)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        input_field.setCompleter(completer)

    def _set_date_input(self, row, transaction):
        try:
            display_date = format_transaction_date(transaction.date)
        except ValueError:
            # Legacy non-ISO values remain editable instead of blocking page load
            display_date = transaction.date

        input_field = QLineEdit(display_date)
        input_field.setAlignment(Qt.AlignmentFlag.AlignCenter)
        input_field.setFont(numeric_font())
        input_field.editingFinished.connect(
            lambda: self.apply_transaction_date(input_field, transaction)
        )
        self.table.setCellWidget(row, 0, input_field)

    def apply_transaction_date(self, input_field, transaction):
        try:
            stored_date = parse_transaction_date(input_field.text())
        except ValueError as exc:
            # Invalid edit stays visible without replacing last valid model value
            self.status.setText(str(exc))
            return

        self._update_transaction_field(transaction, "date", stored_date)
        # Refresh shows normalized date and rebuilds date-based category choices
        self.refresh()

    def _set_category_input(self, row, transaction):
        category = QComboBox()
        self._populate_category_input(category, transaction.date)
        # Stable id and target month distinguish both virtual Income choices
        for index in range(category.count()):
            category_option = category.itemData(index)
            if category_option is None:
                continue
            if category_option["database_id"] != transaction.category_database_id:
                continue
            if category_option.get("income_month_date") != transaction.income_month_date:
                continue
            category.setCurrentIndex(index)
            break
        category.currentIndexChanged.connect(
            lambda: self.update_transaction_category(transaction, category)
        )
        self.table.setCellWidget(row, 2, category)

    def _populate_category_input(self, category, transaction_date=None):
        # Build one grouped list shared by saved rows and the blank entry row
        # Blank row supports incomplete entry before a category is selected
        category.addItem("", None)
        # Dated rows receive virtual choices before normal Budget categories
        for income_option in self.income_category_options(transaction_date):
            category.addItem(income_option["name"], income_option)

        current_master_name = None
        for category_row in self.category_rows:
            master_name = category_row["master_category_name"]
            if master_name != current_master_name:
                # Disabled bold rows visually group choices without being selectable
                category.addItem(master_name, None)
                header_item = category.model().item(category.count() - 1)
                header_item.setEnabled(False)
                header_font = header_item.font()
                header_font.setBold(True)
                header_item.setFont(header_font)
                current_master_name = master_name

            category.addItem(
                category_row["category_name"],
                {
                    "database_id": category_row["id"],
                    "name": category_row["category_name"],
                },
            )

    def create_transaction_from_category(self, category_input):
        # A blank-row selection starts a partial transaction with a stable category id
        category_option = category_input.currentData()
        if category_option is None:
            return
        self.create_transaction(
            category=category_option["name"],
            category_database_id=category_option["database_id"],
        )

    def update_transaction_category(self, transaction, category_input):
        # Keep the display name and database relationship synchronized after selection
        category_option = category_input.currentData()
        if category_option is None:
            transaction.category = ""
            transaction.category_database_id = None
            transaction.income_month_date = None
            if transaction.payee == INCOME_PAYEE_PLACEHOLDER:
                transaction.payee = ""
            self._notify_transaction_changed(transaction)
            self.refresh()
            return

        transaction.category = category_option["name"]
        transaction.category_database_id = category_option["database_id"]
        transaction.income_month_date = category_option.get("income_month_date")
        if transaction.income_month_date is not None:
            # Blank income payee receives schema-compatible placeholder
            if not transaction.payee.strip():
                transaction.payee = INCOME_PAYEE_PLACEHOLDER
        elif transaction.payee == INCOME_PAYEE_PLACEHOLDER:
            # Automatic value should not follow transaction back to spending
            transaction.payee = ""
        self._notify_transaction_changed(transaction)
        self.refresh()

    def _set_money_input(self, row, column, value, apply_value):
        # Zero shown blank so empty money cells stay quick to scan
        input_field = QLineEdit("" if value == 0 else format(value, ".2f"))
        input_field.setAlignment(Qt.AlignmentFlag.AlignRight)
        input_field.setFont(numeric_font())

        # Default expanding policy fills same column width as blank entry fields
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
        self._notify_transaction_changed(transaction)
        self.refresh()

    def _set_delete_button(self, row, transaction):
        delete_button = QPushButton()
        delete_button.setObjectName("deleteTransactionButton")
        delete_button.setToolTip("Delete transaction")
        delete_button.setIcon(QIcon(str(DELETE_ICON_PATH)))
        delete_button.setIconSize(QSize(12, 12))
        delete_button.setFixedSize(24, 24)
        delete_button.clicked.connect(
            lambda: self.request_transaction_deletion(transaction)
        )

        # Center icon-only action inside its compact column
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(delete_button)
        self.table.setCellWidget(row, 7, container)

    def request_transaction_deletion(self, transaction):
        if self.on_transaction_delete_requested is None:
            return

        # Destructive row action requires explicit confirmation
        choice = QMessageBox.question(
            self,
            "Delete Transaction",
            "Delete this transaction?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if choice != QMessageBox.StandardButton.Yes:
            return

        deleted = self.on_transaction_delete_requested(
            self.account,
            transaction,
        )
        if deleted:
            # Rebuild rows and balances after controller removes transaction
            self.refresh()

    def request_account_close(self):
        if self.on_account_close_requested is None:
            return

        # Closing preserves history but still removes account from active workflow
        choice = QMessageBox.question(
            self,
            "Close Account",
            "Close this account? Transaction history will be preserved.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if choice != QMessageBox.StandardButton.Yes:
            return

        self.on_account_close_requested(self.account)

    def request_account_reopen(self):
        if self.on_account_reopen_requested is not None:
            self.on_account_reopen_requested(self.account)

    def request_account_delete(self):
        if self.on_account_delete_requested is None:
            return

        # Controller decides whether account can be deleted or should be closed
        self.on_account_delete_requested(self.account)
