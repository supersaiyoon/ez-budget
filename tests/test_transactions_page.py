import pytest

from budget_model import Account
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
