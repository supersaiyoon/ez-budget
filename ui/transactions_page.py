from datetime import date
from functools import partial
from pathlib import Path

from PyQt6.QtCore import QDate, QEvent, QStringListModel, QTimer, QSize, Qt
from PyQt6.QtGui import QColor, QIcon, QKeyEvent, QPalette
from PyQt6.QtWidgets import (
    QApplication,
    QCalendarWidget,
    QCheckBox,
    QCompleter,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
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
TRANSACTION_PAYEE_COLUMN_WIDTH = 220
TRANSACTION_CATEGORY_COLUMN_WIDTH = 148
TRANSACTION_NOTES_COLUMN_WIDTH = 260
TRANSACTION_MONEY_COLUMN_WIDTH = 88
TRANSACTION_CLEARED_COLUMN_WIDTH = 68
TRANSACTION_DELETE_COLUMN_WIDTH = 40
FEEDBACK_KIND_PROPERTY = "feedbackKind"
EMPTY_FEEDBACK_KIND = "empty"
SUCCESS_FEEDBACK_TIMEOUT_MS = 5000
CATEGORY_PLACEHOLDER_TEXT = "Select budget category"
ADD_CATEGORY_SUFFIX = "..."
CATEGORY_INLINE_COMPLETE_MINIMUM = 2
PAYEE_INLINE_COMPLETE_MINIMUM = 2


class TransactionAmountInput(QLineEdit):
    def focusInEvent(self, event):
        try:
            amount = parse_money(self.text())
        except ValueError:
            pass
        else:
            self.setText(format(amount, ".2f"))
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        try:
            amount = parse_money(self.text())
        except ValueError:
            pass
        else:
            self.setText(format_money(amount))
        super().focusOutEvent(event)


class DateInput(QLineEdit):
    def __init__(self, text="", on_calendar_date_selected=None):
        super().__init__(text)
        self.on_calendar_date_selected = on_calendar_date_selected
        self.calendar_popup = QCalendarWidget(self)
        self.calendar_popup.setWindowFlags(Qt.WindowType.Popup)
        self.calendar_popup.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.calendar_popup.setMinimumDate(QDate(1, 1, 1))
        self.calendar_popup.setMaximumDate(QDate(9999, 12, 31))
        self.calendar_popup.clicked.connect(self.apply_calendar_date)
        self.calendar_popup.installEventFilter(self)

    def eventFilter(self, watched, event):
        if (
            watched is self.calendar_popup
            and event.type() == QEvent.Type.KeyPress
        ):
            forwarded_event = QKeyEvent(
                event.type(),
                event.key(),
                event.modifiers(),
                event.text(),
                event.isAutoRepeat(),
                event.count(),
            )
            QApplication.sendEvent(self, forwarded_event)
            return True
        return super().eventFilter(watched, event)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            self.show_calendar()

    def show_calendar(self):
        # Current text seeds the popup while invalid/blank values fall back to today
        selected_date = QDate.currentDate()
        try:
            parsed_date = date.fromisoformat(parse_transaction_date(self.text()))
            selected_date = QDate(
                parsed_date.year,
                parsed_date.month,
                parsed_date.day,
            )
        except ValueError:
            pass

        self.calendar_popup.setSelectedDate(selected_date)
        self.calendar_popup.move(self.mapToGlobal(self.rect().bottomLeft()))
        self.calendar_popup.show()
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        self.selectAll()

    def apply_calendar_date(self, selected_date):
        self.setText(
            f"{selected_date.month():02}/{selected_date.day():02}/"
            f"{selected_date.year():04}"
        )
        self.calendar_popup.hide()
        if self.on_calendar_date_selected is not None:
            self.on_calendar_date_selected()


class AddIncomeDialog(QDialog):
    def __init__(self, income_reference_date, parent=None, current_date=None):
        super().__init__(parent)
        self.setWindowTitle("Add Income")
        self.income_reference_date = income_reference_date

        layout = QFormLayout(self)
        default_date = current_date or date.today()
        self.date_input = DateInput(format_transaction_date(default_date.isoformat()))
        layout.addRow("Transaction date:", self.date_input)

        self.amount_input = TransactionAmountInput()
        self.amount_input.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.amount_input.setFont(numeric_font())
        self.amount_input.setPlaceholderText("0.00")
        layout.addRow("Amount:", self.amount_input)

        this_month, next_month = income_target_month_dates(income_reference_date)
        self.target_month_input = QComboBox()
        self.target_month_input.addItem("This month", this_month)
        self.target_month_input.addItem("Next month", next_month)
        layout.addRow("Add income to:", self.target_month_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def validate_and_accept(self):
        try:
            self.parsed_date = parse_transaction_date(self.date_input.text())
            self.parsed_amount = parse_money(self.amount_input.text())
        except ValueError as exc:
            QMessageBox.warning(self, "Add Income", str(exc))
            return
        if self.parsed_amount <= 0:
            QMessageBox.warning(
                self,
                "Add Income",
                "Enter an amount greater than zero.",
            )
            return
        self.accept()

    def transaction_date(self):
        return self.parsed_date

    def amount(self):
        return self.parsed_amount

    def income_month_date(self):
        return self.target_month_input.currentData()

    def category_name(self):
        if self.target_month_input.currentIndex() == 0:
            return "Income for this month"
        return "Income for next month"


class AddTransactionCategoryDialog(QDialog):
    def __init__(self, master_category_rows, category_name="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Category")
        self.master_category_rows = master_category_rows

        layout = QFormLayout(self)
        self.master_category_input = QComboBox()
        for row in master_category_rows:
            self.master_category_input.addItem(row["name"], row["id"])
        layout.addRow("Master category:", self.master_category_input)

        self.category_name_input = QLineEdit(category_name)
        layout.addRow("Subcategory name:", self.category_name_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def selected_master_category_id(self):
        return self.master_category_input.currentData()

    def category_name(self):
        return self.category_name_input.text().strip()


class PayeeInput(QLineEdit):
    def __init__(self, payee_names, text=""):
        super().__init__(text)
        self.payee_names = payee_names
        self.completer_model = QStringListModel(payee_names)
        completer = QCompleter(self.completer_model, self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setCompleter(completer)
        self.textEdited.connect(self.complete_best_match)

    def complete_best_match(self, text):
        if len(text.strip()) < PAYEE_INLINE_COMPLETE_MINIMUM:
            return

        match = self.first_matching_payee(text)
        if match is None or text.casefold() == match.casefold():
            return

        self.setText(match)
        self.setSelection(len(text), len(match) - len(text))

    def first_matching_payee(self, text):
        if not text:
            return None

        normalized_text = text.casefold()
        for payee_name in self.payee_names:
            if payee_name.casefold().startswith(normalized_text):
                return payee_name
        return None


class CategoryInput(QLineEdit):
    def __init__(
        self,
        category_options,
        apply_category,
        add_category,
        transaction_date=None,
        text="",
    ):
        super().__init__(text)
        self.category_options = category_options
        self.apply_category = apply_category
        self.add_category = add_category
        self.transaction_date = transaction_date
        self.option_by_display_name = {
            option["display_name"].casefold(): option
            for option in category_options
        }
        self.adding_category = False
        self.completer_model = QStringListModel(self.suggestion_names())
        self.completer = QCompleter(self.completer_model, self)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.completer.activated[str].connect(self.apply_suggestion)
        self.setCompleter(self.completer)
        self.setPlaceholderText(CATEGORY_PLACEHOLDER_TEXT)
        self.textEdited.connect(self.update_suggestions_for_text)
        self.editingFinished.connect(self.apply_typed_category)

    def suggestion_names(self):
        return [option["display_name"] for option in self.category_options]

    def update_suggestions_for_text(self, text):
        suggestions = self.suggestion_names()
        typed_prefix = text
        add_name = text.strip()
        match = self.first_matching_option(typed_prefix)
        if (
            len(typed_prefix.strip()) >= CATEGORY_INLINE_COMPLETE_MINIMUM
            and match is not None
            and typed_prefix.casefold() != match["display_name"].casefold()
        ):
            self.setText(match["display_name"])
            self.setSelection(
                len(typed_prefix),
                len(match["display_name"]) - len(typed_prefix),
            )
            self.completer_model.setStringList(suggestions)
            return

        if add_name and match is None:
            suggestions.append(self.add_category_display_name(add_name))
        self.completer_model.setStringList(suggestions)

    def first_matching_option(self, text):
        if not text:
            return None
        normalized_text = text.casefold()
        for option in self.category_options:
            if option["display_name"].casefold().startswith(normalized_text):
                return option
        return None

    def add_category_display_name(self, name):
        return f'Add "{name}"{ADD_CATEGORY_SUFFIX}'

    def add_category_name_from_display(self, display_name):
        prefix = 'Add "'
        if not display_name.startswith(prefix) or not display_name.endswith(
            ADD_CATEGORY_SUFFIX
        ):
            return None
        return display_name[len(prefix) : -len('"' + ADD_CATEGORY_SUFFIX)]

    def apply_suggestion(self, display_name):
        category_name = self.add_category_name_from_display(display_name)
        if category_name is not None:
            self.adding_category = True
            try:
                self.add_category(self, category_name)
            finally:
                self.adding_category = False
            return

        option = self.option_by_display_name.get(display_name.casefold())
        if option is None:
            return
        self.setText(option["display_name"])
        self.apply_category(option)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Tab and self.add_suggestion_text() is not None:
            self.setText(self.add_suggestion_text())
            event.accept()
            return
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            add_suggestion = self.add_category_name_from_display(
                self.text().strip()
            )
            if add_suggestion is not None:
                self.apply_suggestion(self.text().strip())
                event.accept()
                return
        super().keyPressEvent(event)

    def add_suggestion_text(self):
        for suggestion in self.completer_model.stringList():
            if self.add_category_name_from_display(suggestion) is not None:
                return suggestion
        return None

    def apply_typed_category(self):
        if self.adding_category:
            return

        typed_name = self.text().strip()
        if not typed_name:
            self.apply_category(None)
            return

        category_name = self.add_category_name_from_display(typed_name)
        if category_name is not None:
            self.apply_suggestion(typed_name)
            return

        option = self.option_by_display_name.get(typed_name.casefold())
        if option is None:
            self.apply_category(None)
            return

        self.setText(option["display_name"])
        self.apply_category(option)

    def count(self):
        return self.completer_model.rowCount()

    def itemText(self, index):
        return self.completer_model.stringList()[index]

    def currentText(self):
        return self.text()

    def setCurrentText(self, text):
        self.setText(text)
        self.apply_typed_category()

    def findText(self, text):
        try:
            return self.completer_model.stringList().index(text)
        except ValueError:
            return -1

    def setCurrentIndex(self, index):
        if index < 0:
            return
        self.setCurrentText(self.itemText(index))

    def currentData(self):
        return self.option_by_display_name.get(self.text().strip().casefold())


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
        on_payee_category_requested=None,
        on_category_added=None,
        master_category_rows=None,
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
        self.on_payee_category_requested = on_payee_category_requested
        self.on_category_added = on_category_added
        self.master_category_rows = master_category_rows or []
        self.focus_blank_payee_after_refresh = False
        self.focus_blank_payee_when_shown = allow_new_transactions
        self.date_sort_order = None

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
        self.add_income_button = QPushButton("Add Income")
        self.add_income_button.setObjectName("addIncomeButton")
        self.add_income_button.clicked.connect(self.prompt_for_income)
        self.add_income_button.setVisible(
            self.allow_new_transactions
            and self.account.on_budget
            and self.income_category_id is not None
        )
        account_actions.addWidget(self.add_income_button)
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

        self.feedback = QLabel()
        self.feedback.setObjectName("feedbackMessage")
        self.feedback.setWordWrap(True)
        self.feedback.setFixedHeight(30)
        self.feedback_generation = 0
        self.clear_feedback()
        layout.addWidget(self.feedback)

        # Spreadsheet layout fits repeated transaction entry better than form pages
        self.table = QTableWidget()
        self.table.setColumnCount(len(TRANSACTION_COLUMNS))
        self.table.setHorizontalHeaderLabels(TRANSACTION_COLUMNS)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        header = self.table.horizontalHeader()
        header.setSectionsClickable(True)
        header.sectionClicked.connect(self.sort_by_date_column)
        header.setSortIndicatorShown(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, TRANSACTION_DATE_COLUMN_WIDTH)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(1, TRANSACTION_PAYEE_COLUMN_WIDTH)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(2, TRANSACTION_CATEGORY_COLUMN_WIDTH)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(3, TRANSACTION_NOTES_COLUMN_WIDTH)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(4, TRANSACTION_MONEY_COLUMN_WIDTH)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(5, TRANSACTION_MONEY_COLUMN_WIDTH)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(6, TRANSACTION_CLEARED_COLUMN_WIDTH)
        self.table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(7, TRANSACTION_DELETE_COLUMN_WIDTH)
        layout.addWidget(self.table, 1)

        # Instruction line stays separate from transient save feedback
        if self.account.on_budget and self.allow_new_transactions:
            instruction = (
                "Edit transaction cells directly. Use Add Income for income and "
                "Incoming for refunds."
            )
        else:
            instruction = (
                "Edit transaction cells directly. Use Outgoing for payments and "
                "Incoming for deposits or refunds."
            )
        self.status = QLabel(instruction)
        self.status.setObjectName("statusText")
        self.status.setFixedHeight(20)
        layout.addWidget(self.status)

        self.refresh()

    def showEvent(self, event):
        super().showEvent(event)
        if not self.focus_blank_payee_when_shown:
            return

        self.focus_blank_payee_when_shown = False
        QTimer.singleShot(0, self.focus_blank_payee)

    def show_feedback(self, message, kind="info"):
        self.feedback_generation += 1
        self.feedback.setText(message)
        self.feedback.setProperty(FEEDBACK_KIND_PROPERTY, kind)
        self.feedback.style().unpolish(self.feedback)
        self.feedback.style().polish(self.feedback)
        if kind == "success":
            generation = self.feedback_generation
            QTimer.singleShot(
                SUCCESS_FEEDBACK_TIMEOUT_MS,
                lambda: self.clear_success_feedback(generation),
            )

    def clear_success_feedback(self, generation):
        if generation == self.feedback_generation:
            self.clear_feedback()

    def clear_feedback(self):
        self.feedback.setText("")
        self.feedback.setProperty(FEEDBACK_KIND_PROPERTY, EMPTY_FEEDBACK_KIND)
        self.feedback.style().unpolish(self.feedback)
        self.feedback.style().polish(self.feedback)

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

        for row, transaction in enumerate(self.display_transactions()):
            self._set_transaction_row(row, transaction)
        if self.allow_new_transactions:
            self._set_blank_row(len(self.account.transactions))
        if self.focus_blank_payee_after_refresh:
            self.focus_blank_payee_after_refresh = False
            QTimer.singleShot(0, self.focus_blank_payee)

    def display_transactions(self):
        if self.date_sort_order is None:
            return self.account.transactions

        return sorted(
            self.account.transactions,
            key=lambda transaction: transaction.date,
            reverse=self.date_sort_order == Qt.SortOrder.DescendingOrder,
        )

    def sort_by_date_column(self, column):
        if column != 0:
            return

        if self.date_sort_order == Qt.SortOrder.AscendingOrder:
            self.date_sort_order = Qt.SortOrder.DescendingOrder
        else:
            self.date_sort_order = Qt.SortOrder.AscendingOrder

        header = self.table.horizontalHeader()
        header.setSortIndicator(0, self.date_sort_order)
        header.setSortIndicatorShown(True)
        self.refresh()

    def default_transaction_date(self):
        return date.today().isoformat()

    def default_transaction_date_display(self):
        return format_transaction_date(self.default_transaction_date())

    def focus_blank_payee(self):
        if not self.allow_new_transactions or self.table.rowCount() == 0:
            return

        row = self.table.rowCount() - 1
        payee_input = self.table.cellWidget(row, 1)
        if payee_input is None:
            return

        self.table.setCurrentCell(row, 1)
        payee_input.setFocus(Qt.FocusReason.OtherFocusReason)
        payee_input.setCursorPosition(len(payee_input.text()))

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
        payee_input.setProperty(
            "normal_text_color",
            payee_input.palette().color(QPalette.ColorRole.Text),
        )
        self.style_transaction_payee_input(payee_input, transaction.payee)
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
        for column in range(6):
            input_field = self.table.cellWidget(row, column)
            if isinstance(input_field, QLineEdit):
                input_field.returnPressed.connect(
                    partial(self.save_edited_transaction, transaction)
                )
        self._set_cleared_input(row, transaction)
        self._set_delete_button(row, transaction)
        if transaction.income_month_date is not None:
            self.style_income_transaction_row(row)
        self.table.setRowHeight(row, 36)

    def style_income_transaction_row(self, row):
        for column in range(self.table.columnCount()):
            cell_widget = self.table.cellWidget(row, column)
            if cell_widget is None:
                continue
            cell_widget.setProperty("incomeTransaction", True)
            cell_widget.style().unpolish(cell_widget)
            cell_widget.style().polish(cell_widget)

    def _set_blank_row(self, row):
        # Blank row creates a transaction from whichever field user starts with
        self._set_new_transaction_input(
            row,
            0,
            text=self.default_transaction_date_display(),
        )
        self._set_new_transaction_input(row, 1)

        self._set_blank_category_input(row)

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

    def _set_blank_category_input(self, row):
        category_input = CategoryInput(
            self.category_options(),
            lambda option: self.create_transaction_from_category_option(option),
            self.add_category_from_input,
        )
        self.table.setCellWidget(row, 2, category_input)

    def _set_new_transaction_input(self, row, column, money_column=None, text=""):
        if column == 0:
            input_field = DateInput(
                text,
                on_calendar_date_selected=lambda: self.create_transaction_from_input(
                    column,
                    input_field,
                    money_column,
                )
            )
        elif column == 1:
            input_field = PayeeInput(self.payee_names)
        elif money_column is not None:
            input_field = TransactionAmountInput()
        else:
            input_field = QLineEdit()

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
                self.show_feedback(str(exc), "warning")
                return
            self.create_transaction(**{money_column: amount})
            return

        if column == 0:
            try:
                value = parse_transaction_date(value)
            except ValueError as exc:
                # Invalid date stays visible in blank row for direct correction
                self.show_feedback(str(exc), "warning")
                return

        fields = {
            0: "date",
            1: "payee",
            3: "notes",
        }
        if column == 1:
            self.create_transaction(
                payee=value,
                **self.latest_category_values_for_payee(value),
            )
            return

        # Column map keeps generic editor code from knowing transaction names
        self.create_transaction(**{fields[column]: value})

    def create_transaction(self, **values):
        if not any(value not in ("", None, False, 0) for value in values.values()):
            # Default-only edits ignored so checkbox setup cannot add empty rows
            return

        # Missing fields allowed so quick entry can start from any column
        transaction = Transaction(
            date=values.get("date", self.default_transaction_date()),
            payee=values.get("payee", ""),
            category=values.get("category", ""),
            notes=values.get("notes", ""),
            outgoing=values.get("outgoing", parse_money("0")),
            incoming=values.get("incoming", parse_money("0")),
            cleared=values.get("cleared", False),
            category_database_id=values.get("category_database_id"),
            income_month_date=values.get("income_month_date"),
        )
        self.account.transactions.append(transaction)
        self._notify_transaction_changed(transaction)
        # Full refresh replaces the blank row and updates balances together
        self.refresh()

    def prompt_for_income(self):
        dialog = AddIncomeDialog(self.income_reference_date, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.add_income(
            dialog.transaction_date(),
            dialog.amount(),
            dialog.income_month_date(),
            dialog.category_name(),
        )

    def add_income(
        self,
        transaction_date,
        amount,
        income_month_date,
        category_name,
    ):
        self.create_transaction(
            date=transaction_date,
            payee=INCOME_PAYEE_PLACEHOLDER,
            category=category_name,
            notes="",
            incoming=amount,
            category_database_id=self.income_category_id,
            income_month_date=income_month_date,
        )

    def _update_transaction_field(self, transaction, field, value):
        # Row edits stay local until Enter
        setattr(transaction, field, value)

    def save_edited_transaction(self, transaction):
        # Run after editingFinished applies the active cell
        QTimer.singleShot(0, partial(self.finish_edited_transaction, transaction))

    def finish_edited_transaction(self, transaction):
        self._notify_transaction_changed(transaction)
        self.refresh()

    def _notify_transaction_changed(self, transaction):
        # Tests and MainWindow can react without TransactionsPage knowing why
        if self.on_transaction_changed is None:
            return False

        saved = self.on_transaction_changed(self.account, transaction)
        if saved:
            self.show_feedback("Transaction saved.", "success")
            self.focus_blank_payee_after_refresh = True
            return True

        # Partial row remains editable while status makes pending state explicit
        self.show_feedback(self.incomplete_transaction_message(transaction), "warning")
        return False

    def incomplete_transaction_message(self, transaction):
        missing = []
        if not transaction.date.strip():
            missing.append("date")
        if not transaction.payee.strip():
            missing.append("payee")
        if transaction.category_database_id is None:
            missing.append("category")

        has_outgoing = transaction.outgoing != 0
        has_incoming = transaction.incoming != 0
        if has_outgoing and has_incoming:
            return "Not saved yet: use either Outgoing or Incoming, not both."
        if not has_outgoing and not has_incoming:
            missing.append("one amount")

        if not missing:
            return "Not saved yet: check the transaction fields."

        if len(missing) == 1:
            missing_text = missing[0]
        else:
            missing_text = ", ".join(missing[:-1]) + f", and {missing[-1]}"
        return f"Not saved yet: enter {missing_text}."

    def _set_text_input(self, row, column, value, apply_value):
        input_field = (
            PayeeInput(self.payee_names, value)
            if column == 1
            else QLineEdit(value)
        )
        input_field.setProperty("transaction_row", row)
        # Stored values trimmed to avoid accidental spaces in reports and filters
        input_field.editingFinished.connect(
            lambda: self.apply_text_value(column, input_field, apply_value)
        )
        self.table.setCellWidget(row, column, input_field)
        return input_field

    def apply_text_value(self, column, input_field, apply_value):
        value = input_field.text().strip()
        apply_value(value)
        if column == 1:
            row = input_field.property("transaction_row")
            if row is None or row >= len(self.account.transactions):
                return
            transaction = self.account.transactions[row]
            if transaction.category_database_id is None:
                self.apply_latest_category_for_payee(transaction, value)

    def _set_date_input(self, row, transaction):
        try:
            display_date = format_transaction_date(transaction.date)
        except ValueError:
            # Legacy non-ISO values remain editable instead of blocking page load
            display_date = transaction.date

        input_field = DateInput(
            display_date,
            on_calendar_date_selected=(
                lambda: self.apply_transaction_date(input_field, transaction)
            ),
        )
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
            self.show_feedback(str(exc), "warning")
            return

        self._update_transaction_field(transaction, "date", stored_date)
        input_field.setText(format_transaction_date(stored_date))

    def _set_category_input(self, row, transaction):
        category_input = CategoryInput(
            self.category_options(transaction.date),
            lambda option: self.update_transaction_category(transaction, option),
            self.add_category_from_input,
            transaction.date,
            self.category_text_for_transaction(transaction),
        )
        self.table.setCellWidget(row, 2, category_input)

    def category_text_for_transaction(self, transaction):
        for option in self.category_options(transaction.date):
            if option["database_id"] != transaction.category_database_id:
                continue
            if option.get("income_month_date") != transaction.income_month_date:
                continue
            return option["display_name"]
        return transaction.category

    def category_options(self, transaction_date=None):
        # Build one suggestion list shared by saved rows and the blank entry row
        options = []
        for income_option in self.income_category_options(transaction_date):
            options.append(
                {
                    **income_option,
                    "display_name": income_option["name"],
                }
            )
        for category_row in self.category_rows:
            master_category_id = self.category_row_value(
                category_row,
                "master_budget_category_id",
            )
            options.append(
                {
                    "database_id": category_row["id"],
                    "name": category_row["category_name"],
                    "display_name": self.category_display_name(category_row),
                    "master_category_name": category_row["master_category_name"],
                    "master_budget_category_id": master_category_id,
                },
            )
        return options

    def category_row_value(self, category_row, key):
        try:
            return category_row[key]
        except (KeyError, IndexError):
            return None

    def create_transaction_from_category_option(self, category_option):
        # A blank-row selection starts a partial transaction with a stable category id
        if category_option is None:
            self.show_feedback(
                "Choose a category from the suggestions or add a new category.",
                "warning",
            )
            return
        self.create_transaction(
            category=category_option["name"],
            category_database_id=category_option["database_id"],
            income_month_date=category_option.get("income_month_date"),
        )

    def update_transaction_category(self, transaction, category_option):
        # Keep the display name and database relationship synchronized after selection
        if category_option is None:
            transaction.category = ""
            transaction.category_database_id = None
            transaction.income_month_date = None
            if transaction.payee == INCOME_PAYEE_PLACEHOLDER:
                transaction.payee = ""
            self.sync_transaction_payee_input(transaction)
            self.show_feedback(
                "Choose a category from the suggestions or add a new category.",
                "warning",
            )
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
        self.sync_transaction_payee_input(transaction)

    def sync_transaction_payee_input(self, transaction):
        for row, existing_transaction in enumerate(self.account.transactions):
            if existing_transaction is transaction:
                payee_input = self.table.cellWidget(row, 1)
                if isinstance(payee_input, QLineEdit):
                    payee_input.setText(transaction.payee)
                    self.style_transaction_payee_input(
                        payee_input,
                        transaction.payee,
                    )
                return

    def style_transaction_payee_input(self, payee_input, payee_name):
        automatic_payee = payee_name == INCOME_PAYEE_PLACEHOLDER
        payee_font = payee_input.font()
        payee_font.setItalic(automatic_payee)
        payee_input.setFont(payee_font)

        normal_text_color = payee_input.property("normal_text_color")
        if normal_text_color is None:
            normal_text_color = payee_input.palette().color(QPalette.ColorRole.Text)
            payee_input.setProperty("normal_text_color", normal_text_color)
        payee_palette = payee_input.palette()
        payee_palette.setColor(
            QPalette.ColorRole.Text,
            QColor("#7a8794") if automatic_payee else normal_text_color,
        )
        payee_input.setPalette(payee_palette)

    def latest_category_values_for_payee(self, payee_name):
        category_option = self.latest_category_option_for_payee(payee_name)
        if category_option is None:
            return {}
        return {
            "category": category_option["name"],
            "category_database_id": category_option["database_id"],
        }

    def latest_category_option_for_payee(self, payee_name):
        if self.on_payee_category_requested is None:
            return None
        category_row = self.on_payee_category_requested(payee_name)
        if category_row is None:
            return None
        for option in self.category_options():
            if option["database_id"] == category_row["id"]:
                return option
        return None

    def apply_latest_category_for_payee(self, transaction, payee_name):
        category_option = self.latest_category_option_for_payee(payee_name)
        if category_option is None:
            return
        transaction.category = category_option["name"]
        transaction.category_database_id = category_option["database_id"]
        transaction.income_month_date = None
        for row, existing_transaction in enumerate(self.account.transactions):
            if existing_transaction is transaction:
                category_input = self.table.cellWidget(row, 2)
                if isinstance(category_input, CategoryInput):
                    category_input.setText(category_option["display_name"])
                return

    def add_category_from_input(self, category_input, category_name):
        apply_category = category_input.apply_category
        if self.on_category_added is None:
            self.show_feedback(
                "Choose a category from the suggestions or add a new category.",
                "warning",
            )
            return

        master_rows = self.master_category_rows
        if not master_rows:
            self.show_feedback("Add a master category before adding a subcategory.", "warning")
            return

        dialog = AddTransactionCategoryDialog(master_rows, category_name, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            apply_category(None)
            return

        try:
            category_row = self.on_category_added(
                dialog.selected_master_category_id(),
                dialog.category_name(),
            )
        except ValueError as exc:
            self.show_feedback(str(exc), "warning")
            apply_category(None)
            return

        if category_row is None:
            apply_category(None)
            return

        category_row = self.normalized_category_row(
            category_row,
            dialog.selected_master_category_id(),
        )
        if category_row is None:
            apply_category(None)
            return

        self.add_category_row_to_suggestions(category_row)
        option = {
            "database_id": category_row["id"],
            "name": category_row["category_name"],
            "display_name": self.category_display_name(category_row),
            "master_category_name": category_row["master_category_name"],
            "master_budget_category_id": category_row[
                "master_budget_category_id"
            ],
        }
        apply_category(option)

    def add_category_row_to_suggestions(self, category_row):
        if any(row["id"] == category_row["id"] for row in self.category_rows):
            return
        self.category_rows = list(self.category_rows) + [category_row]

    def normalized_category_row(self, category_row, master_category_id):
        master_category_name = next(
            (
                row["name"]
                for row in self.master_category_rows
                if row["id"] == master_category_id
            ),
            None,
        )
        category_name = self.category_row_value(category_row, "category_name")
        if category_name is None:
            category_name = self.category_row_value(category_row, "name")
        if master_category_name is None or category_name is None:
            return None
        return {
            "id": category_row["id"],
            "master_budget_category_id": master_category_id,
            "master_category_name": master_category_name,
            "category_name": category_name,
            "name": category_name,
        }

    def set_master_category_rows(self, master_category_rows):
        self.master_category_rows = master_category_rows
        self.refresh()

    def _set_money_input(self, row, column, value, apply_value):
        # Zero shown blank so empty money cells stay quick to scan
        input_field = TransactionAmountInput(
            "" if value == 0 else format_money(value)
        )
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
            return

        try:
            amount = parse_money(raw_value)
        except ValueError as exc:
            # Keep invalid text visible so correction is direct
            self.show_feedback(str(exc), "warning")
            return

        apply_value(amount)

    def category_display_name(self, category_row):
        category_name = category_row["category_name"]
        duplicate_count = sum(
            1
            for existing_row in self.category_rows
            if existing_row["category_name"].casefold() == category_name.casefold()
        )
        if duplicate_count <= 1:
            return category_name
        return (
            f"{category_name} "
            f'({category_row["master_category_name"]})'
        )

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
