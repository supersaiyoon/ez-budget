import pytest

from datetime import date
from decimal import Decimal

from PyQt6.QtWidgets import QMessageBox

from budget_model import Account, Transaction
from ui.transactions_page import TransactionsPage


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
        "Not saved yet: enter date, payee, category, and one amount."
    )

    payee_input = page.table.cellWidget(0, 1)
    payee_input.setText("Grocery Store")
    payee_input.editingFinished.emit()

    assert page.status.text() == "Transaction saved."


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


def test_short_date_input_stores_iso_and_displays_full_year():
    account = Account("Checking")
    page = TransactionsPage(account, category_rows=[])
    current_year = date.today().year
    date_input = page.table.cellWidget(0, 0)

    date_input.setText("7/21")
    date_input.editingFinished.emit()

    assert account.transactions[0].date == f"{current_year}-07-21"
    assert page.table.cellWidget(0, 0).text() == f"7/21/{current_year}"


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

    assert date_input.text() == "7/21/2026"

    date_input.setText("8/5/2027")
    date_input.editingFinished.emit()

    assert transaction.date == "2027-08-05"
    assert page.table.cellWidget(0, 0).text() == "8/5/2027"


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

    page.table.cellWidget(0, 7).click()

    assert deletion_requests == [(account, transaction)]
    assert page.table.rowCount() == 1


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

    page.table.cellWidget(0, 7).click()

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
