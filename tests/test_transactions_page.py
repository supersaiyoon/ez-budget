import pytest

from datetime import date
from decimal import Decimal

from PyQt6.QtCore import QDate, QSize, Qt
from PyQt6.QtWidgets import QHeaderView, QMessageBox, QPushButton

from budget_model import Account, Transaction
from ui.transactions_page import (
    TRANSACTION_CATEGORY_COLUMN_WIDTH,
    TRANSACTION_CLEARED_COLUMN_WIDTH,
    TRANSACTION_DATE_COLUMN_WIDTH,
    TRANSACTION_DELETE_COLUMN_WIDTH,
    TRANSACTION_MONEY_COLUMN_WIDTH,
    DateInput,
    TransactionsPage,
)


# TransactionsPage creates Qt editors and requires the shared application fixture
pytestmark = pytest.mark.usefixtures("qapp")


def test_transaction_editors_report_new_and_changed_transactions():
    account = Account("Checking")
    reported_changes = []
    page = TransactionsPage(
        account,
        category_rows=[],
        on_transaction_changed=lambda changed_account, transaction: reported_changes.append(
            (changed_account, transaction)
        ),
    )

    # Finishing the blank date editor creates and reports one partial transaction
    date_input = page.table.cellWidget(0, 0)
    date_input.setText("2026-07-21")
    date_input.editingFinished.emit()
    transaction = account.transactions[0]

    # Editing its rebuilt payee row reports the same transaction again
    payee_input = page.table.cellWidget(0, 1)
    payee_input.setText("Grocery Store")
    payee_input.editingFinished.emit()

    assert reported_changes == [
        (account, transaction),
        (account, transaction),
    ]
    assert transaction.date == "2026-07-21"
    assert transaction.payee == "Grocery Store"


def test_transaction_page_reports_pending_and_saved_states():
    account = Account("Checking")
    save_results = iter([False, True])
    page = TransactionsPage(
        account,
        category_rows=[],
        on_transaction_changed=lambda *args: next(save_results),
    )

    date_input = page.table.cellWidget(0, 0)
    date_input.setText("2026-07-21")
    date_input.editingFinished.emit()

    assert page.status.text() == (
        "Not saved yet: enter payee, category, and one amount."
    )
    assert page.feedback.text() == page.status.text()
    assert page.feedback.property("feedbackKind") == "warning"
    assert page.feedback.isHidden() is False

    payee_input = page.table.cellWidget(0, 1)
    payee_input.setText("Grocery Store")
    payee_input.editingFinished.emit()

    assert page.status.text() == "Transaction saved."
    assert page.feedback.text() == "Transaction saved."
    assert page.feedback.property("feedbackKind") == "success"


def test_payee_input_autocompletes_saved_payees():
    page = TransactionsPage(
        Account("Checking"),
        category_rows=[],
        payee_names=["Grocery Store", "Fuel Stop"],
    )
    payee_input = page.table.cellWidget(0, 1)

    model = payee_input.completer().model()

    assert [
        model.index(row, 0).data()
        for row in range(model.rowCount())
    ] == ["Grocery Store", "Fuel Stop"]
    assert (
        payee_input.completer().caseSensitivity()
        == Qt.CaseSensitivity.CaseInsensitive
    )


def test_payee_autocomplete_refreshes_open_editors():
    page = TransactionsPage(
        Account("Checking"),
        category_rows=[],
        payee_names=["Grocery Store"],
    )

    page.set_payee_names(["Grocery Store", "Fuel Stop"])
    payee_input = page.table.cellWidget(0, 1)
    model = payee_input.completer().model()

    assert [
        model.index(row, 0).data()
        for row in range(model.rowCount())
    ] == ["Grocery Store", "Fuel Stop"]


def test_closed_account_page_omits_blank_transaction_row():
    transaction = Transaction(
        date="2026-07-21",
        payee="Grocery Store",
        category="Groceries",
        notes="",
        outgoing=Decimal("42.50"),
    )
    account = Account(
        "Checking",
        transactions=[transaction],
        closed=True,
    )

    page = TransactionsPage(
        account,
        category_rows=[],
        allow_new_transactions=False,
    )

    assert page.table.rowCount() == 1
    assert page.table.cellWidget(0, 1).text() == "Grocery Store"
    assert page.close_account_button.isHidden()
    assert page.delete_account_button.isHidden()
    assert page.reopen_account_button.isHidden() is False


def test_short_date_input_stores_iso_and_displays_full_year():
    account = Account("Checking")
    page = TransactionsPage(account, category_rows=[])
    current_year = date.today().year
    date_input = page.table.cellWidget(0, 0)
    assert date_input.alignment() == Qt.AlignmentFlag.AlignCenter
    assert date_input.font().family() == "Consolas"

    date_input.setText("7/21")
    date_input.editingFinished.emit()

    assert account.transactions[0].date == f"{current_year}-07-21"
    assert page.table.cellWidget(0, 0).text() == f"07/21/{current_year}"
    assert (
        page.table.cellWidget(0, 0).alignment()
        == Qt.AlignmentFlag.AlignCenter
    )


def test_calendar_popup_can_create_transaction_date():
    account = Account("Checking")
    page = TransactionsPage(account, category_rows=[])
    date_input = page.table.cellWidget(0, 0)

    assert isinstance(date_input, DateInput)
    assert date_input.calendar_popup.minimumDate() == QDate(1, 1, 1)
    assert date_input.calendar_popup.maximumDate() == QDate(9999, 12, 31)

    date_input.apply_calendar_date(QDate(2026, 7, 21))

    assert account.transactions[0].date == "2026-07-21"
    assert page.table.cellWidget(0, 0).text() == "07/21/2026"


def test_existing_transaction_date_edit_normalizes_storage_and_display():
    transaction = Transaction(
        date="2026-07-21",
        payee="Grocery Store",
        category="",
        notes="",
    )
    account = Account("Checking", transactions=[transaction])
    page = TransactionsPage(account, category_rows=[])
    date_input = page.table.cellWidget(0, 0)

    assert date_input.text() == "07/21/2026"

    date_input.setText("8/5/2027")
    date_input.editingFinished.emit()

    assert transaction.date == "2027-08-05"
    assert page.table.cellWidget(0, 0).text() == "08/05/2027"


def test_calendar_selection_updates_existing_transaction_date():
    transaction = Transaction(
        date="2026-07-21",
        payee="Grocery Store",
        category="",
        notes="",
    )
    account = Account("Checking", transactions=[transaction])
    page = TransactionsPage(account, category_rows=[])
    date_input = page.table.cellWidget(0, 0)

    date_input.apply_calendar_date(QDate(2027, 8, 5))

    assert transaction.date == "2027-08-05"
    assert page.table.cellWidget(0, 0).text() == "08/05/2027"


def test_saved_money_inputs_expand_like_blank_row_inputs():
    transaction = Transaction(
        date="2026-07-21",
        payee="Grocery Store",
        category="Groceries",
        notes="",
        outgoing=Decimal("42.50"),
    )
    page = TransactionsPage(
        Account("Checking", transactions=[transaction]),
        category_rows=[],
    )

    saved_outgoing = page.table.cellWidget(0, 4)
    saved_incoming = page.table.cellWidget(0, 5)
    blank_outgoing = page.table.cellWidget(1, 4)
    blank_incoming = page.table.cellWidget(1, 5)

    assert saved_outgoing.minimumWidth() == blank_outgoing.minimumWidth()
    assert saved_outgoing.maximumWidth() == blank_outgoing.maximumWidth()
    assert saved_incoming.minimumWidth() == blank_incoming.minimumWidth()
    assert saved_incoming.maximumWidth() == blank_incoming.maximumWidth()
    assert saved_outgoing.alignment() == Qt.AlignmentFlag.AlignRight
    assert saved_incoming.alignment() == Qt.AlignmentFlag.AlignRight
    assert blank_outgoing.alignment() == Qt.AlignmentFlag.AlignRight
    assert blank_incoming.alignment() == Qt.AlignmentFlag.AlignRight
    assert saved_outgoing.font().family() == "Consolas"
    assert blank_outgoing.font().family() == "Consolas"


def test_transaction_columns_use_stable_widths():
    page = TransactionsPage(Account("Checking"), category_rows=[])

    assert (
        page.table.horizontalHeader().sectionResizeMode(0)
        == QHeaderView.ResizeMode.Fixed
    )
    assert page.table.columnWidth(0) == TRANSACTION_DATE_COLUMN_WIDTH
    for column in (4, 5):
        assert (
            page.table.horizontalHeader().sectionResizeMode(column)
            == QHeaderView.ResizeMode.Fixed
        )
        assert page.table.columnWidth(column) == TRANSACTION_MONEY_COLUMN_WIDTH
    assert (
        page.table.horizontalHeader().sectionResizeMode(2)
        == QHeaderView.ResizeMode.Fixed
    )
    assert page.table.columnWidth(2) == TRANSACTION_CATEGORY_COLUMN_WIDTH
    assert (
        page.table.horizontalHeader().sectionResizeMode(6)
        == QHeaderView.ResizeMode.Fixed
    )
    assert page.table.columnWidth(6) == TRANSACTION_CLEARED_COLUMN_WIDTH
    assert (
        page.table.horizontalHeader().sectionResizeMode(7)
        == QHeaderView.ResizeMode.Fixed
    )
    assert page.table.columnWidth(7) == TRANSACTION_DELETE_COLUMN_WIDTH


def test_empty_and_populated_transaction_pages_use_same_column_widths():
    transaction = Transaction(
        date="2026-07-21",
        payee="Grocery Store",
        category="Groceries",
        notes="",
        outgoing=Decimal("42.50"),
    )
    empty_page = TransactionsPage(Account("Checking"), category_rows=[])
    populated_page = TransactionsPage(
        Account("Checking", transactions=[transaction]),
        category_rows=[],
    )

    assert [
        empty_page.table.columnWidth(column)
        for column in range(empty_page.table.columnCount())
    ] == [
        populated_page.table.columnWidth(column)
        for column in range(populated_page.table.columnCount())
    ]


def test_delete_transaction_column_header_is_blank():
    page = TransactionsPage(Account("Checking"), category_rows=[])

    assert page.table.horizontalHeaderItem(7).text() == ""


def test_delete_transaction_button_is_centered():
    transaction = Transaction(
        date="2026-07-21",
        payee="Grocery Store",
        category="Groceries",
        notes="",
        outgoing=Decimal("42.50"),
    )
    page = TransactionsPage(
        Account("Checking", transactions=[transaction]),
        category_rows=[],
    )
    delete_container = page.table.cellWidget(0, 7)

    assert delete_container.layout().alignment() == Qt.AlignmentFlag.AlignCenter
    assert (
        delete_container.findChild(QPushButton).objectName()
        == "deleteTransactionButton"
    )


def test_delete_button_reports_account_and_transaction(monkeypatch):
    transaction = Transaction(
        date="2026-07-21",
        payee="Grocery Store",
        category="Groceries",
        notes="",
        outgoing=Decimal("42.50"),
    )
    account = Account("Checking", transactions=[transaction])
    deletion_requests = []

    def delete_transaction(changed_account, changed_transaction):
        deletion_requests.append((changed_account, changed_transaction))
        changed_account.transactions.remove(changed_transaction)
        return True

    page = TransactionsPage(
        account,
        category_rows=[],
        on_transaction_delete_requested=delete_transaction,
    )
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args: QMessageBox.StandardButton.Yes,
    )

    page.table.cellWidget(0, 7).findChild(QPushButton).click()

    assert deletion_requests == [(account, transaction)]
    assert page.table.rowCount() == 1


def test_delete_transaction_button_uses_trash_icon():
    transaction = Transaction(
        date="2026-07-21",
        payee="Grocery Store",
        category="Groceries",
        notes="",
        outgoing=Decimal("42.50"),
    )
    account = Account("Checking", transactions=[transaction])
    page = TransactionsPage(account, category_rows=[])
    delete_button = page.table.cellWidget(0, 7).findChild(QPushButton)

    assert delete_button.text() == ""
    assert delete_button.icon().isNull() is False
    assert delete_button.iconSize() == QSize(12, 12)
    assert delete_button.size() == QSize(24, 24)


def test_delete_button_cancel_keeps_transaction(monkeypatch):
    transaction = Transaction(
        date="2026-07-21",
        payee="Grocery Store",
        category="Groceries",
        notes="",
        outgoing=Decimal("42.50"),
    )
    account = Account("Checking", transactions=[transaction])
    deletion_requests = []
    page = TransactionsPage(
        account,
        category_rows=[],
        on_transaction_delete_requested=lambda *args: deletion_requests.append(
            args
        ),
    )
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args: QMessageBox.StandardButton.No,
    )

    page.table.cellWidget(0, 7).findChild(QPushButton).click()

    assert deletion_requests == []
    assert account.transactions == [transaction]


def test_close_account_button_reports_confirmed_account(monkeypatch):
    account = Account("Checking")
    close_requests = []
    page = TransactionsPage(
        account,
        category_rows=[],
        on_account_close_requested=close_requests.append,
    )
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args: QMessageBox.StandardButton.Yes,
    )

    page.close_account_button.click()

    assert close_requests == [account]


def test_close_account_button_cancel_keeps_account_active(monkeypatch):
    account = Account("Checking")
    close_requests = []
    page = TransactionsPage(
        account,
        category_rows=[],
        on_account_close_requested=close_requests.append,
    )
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args: QMessageBox.StandardButton.No,
    )

    page.close_account_button.click()

    assert close_requests == []


def test_reopen_account_button_reports_closed_account():
    account = Account("Checking", closed=True)
    reopen_requests = []
    page = TransactionsPage(
        account,
        category_rows=[],
        on_account_reopen_requested=reopen_requests.append,
        allow_new_transactions=False,
    )

    page.reopen_account_button.click()

    assert reopen_requests == [account]


def test_delete_account_button_reports_account():
    account = Account("Checking")
    delete_requests = []
    page = TransactionsPage(
        account,
        category_rows=[],
        on_account_delete_requested=delete_requests.append,
    )

    page.delete_account_button.click()

    assert delete_requests == [account]


def test_income_category_options_use_current_planning_month():
    page = TransactionsPage(
        Account("Checking"),
        category_rows=[],
        income_category_id=42,
        income_reference_date="2026-07-01",
    )

    # June transaction still assigns against current July planning month
    options = page.income_category_options("2026-06-01")

    assert options == [
        {
            "database_id": 42,
            "name": "Income for this month",
            "income_month_date": "2026-07-01",
        },
        {
            "database_id": 42,
            "name": "Income for next month",
            "income_month_date": "2026-08-01",
        },
    ]
    assert page.income_category_options("") == []
    assert page.income_category_options("not-a-date") == []


def test_dated_transaction_row_selects_income_target_month():
    transaction = Transaction(
        date="2026-06-01",
        payee="Employer",
        category="Income",
        notes="",
        incoming=Decimal("2000.00"),
        category_database_id=42,
        income_month_date="2026-08-01",
    )
    account = Account("Checking", transactions=[transaction])
    page = TransactionsPage(
        account,
        category_rows=[
            {
                "id": 7,
                "master_category_name": "Everyday Expenses",
                "category_name": "Groceries",
            }
        ],
        income_category_id=42,
        income_reference_date="2026-07-01",
    )
    category_input = page.table.cellWidget(0, 2)

    # Saved August target restores next-month label
    assert category_input.currentText() == "Income for next month"

    category_input.setCurrentText("Income for this month")
    assert transaction.category_database_id == 42
    assert transaction.income_month_date == "2026-07-01"
    assert transaction.payee == "Employer"

    category_input = page.table.cellWidget(0, 2)
    category_input.setCurrentText("Groceries")
    assert transaction.category_database_id == 7
    assert transaction.income_month_date is None
    assert transaction.payee == "Employer"


def test_duplicate_category_names_show_master_context():
    transaction = Transaction(
        date="2026-07-25",
        payee="Grocery Store",
        category="",
        notes="",
    )
    page = TransactionsPage(
        Account("Checking", transactions=[transaction]),
        category_rows=[
            {
                "id": 7,
                "master_category_name": "Everyday Expenses",
                "category_name": "Groceries",
            },
            {
                "id": 8,
                "master_category_name": "Bulk Shopping",
                "category_name": "Groceries",
            },
        ],
    )
    category_input = page.table.cellWidget(0, 2)

    assert [category_input.itemText(index) for index in range(category_input.count())] == [
        "",
        "Everyday Expenses",
        "Groceries (Everyday Expenses)",
        "Bulk Shopping",
        "Groceries (Bulk Shopping)",
    ]

    category_input.setCurrentText("Groceries (Bulk Shopping)")

    assert transaction.category == "Groceries"
    assert transaction.category_database_id == 8


def test_income_category_autofills_and_clears_placeholder_payee():
    transaction = Transaction(
        date="2026-07-25",
        payee="",
        category="",
        notes="",
    )
    account = Account("Checking", transactions=[transaction])
    page = TransactionsPage(
        account,
        category_rows=[
            {
                "id": 7,
                "master_category_name": "Everyday Expenses",
                "category_name": "Groceries",
            }
        ],
        income_category_id=42,
        income_reference_date="2026-07-01",
    )

    category_input = page.table.cellWidget(0, 2)
    category_input.setCurrentText("Income for this month")

    assert transaction.payee == "Not needed for income"
    payee_input = page.table.cellWidget(0, 1)
    assert payee_input.text() == "Not needed for income"
    assert payee_input.font().italic() is True
    assert payee_input.palette().color(payee_input.foregroundRole()).name() == (
        "#7a8794"
    )

    category_input = page.table.cellWidget(0, 2)
    category_input.setCurrentText("Groceries")

    assert transaction.payee == ""
    payee_input = page.table.cellWidget(0, 1)
    assert payee_input.text() == ""
    assert payee_input.font().italic() is False
