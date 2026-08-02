import pytest

from PyQt6.QtWidgets import QInputDialog, QMessageBox

from db import accounts, categories, payees, transactions
from ui.payees_dialog import PayeesDialog


# PayeesDialog creates Qt widgets and requires the shared application fixture
pytestmark = pytest.mark.usefixtures("qapp")


def _create_transaction(con, payee):
    # Minimal related rows for payee reassignment tests
    account = accounts.create_account(con, "Checking")
    master_category = categories.add_master_category(con, "Everyday Expenses")
    category = categories.add_budget_category(con, master_category["id"], "Groceries")
    return transactions.add_transaction(
        con,
        account["id"],
        payee["id"],
        category["id"],
        "2026-07-13",
        -4250,
    )


def payee_names(dialog):
    return [
        dialog.payee_list.item(row).text()
        for row in range(dialog.payee_list.count())
    ]


def test_payees_dialog_lists_saved_payees(con):
    payees.add_payee(con, "Grocery Store")
    payees.add_payee(con, "Fuel Stop")

    dialog = PayeesDialog(con)

    assert payee_names(dialog) == ["Fuel Stop", "Grocery Store"]


def test_payees_dialog_adds_payee(monkeypatch, con):
    dialog = PayeesDialog(con)
    monkeypatch.setattr(
        QInputDialog,
        "getText",
        lambda *args, **kwargs: ("Grocery Store", True),
    )

    dialog.add_button.click()

    assert payee_names(dialog) == ["Grocery Store"]
    assert payees.get_payee_by_name(con, "Grocery Store") is not None


def test_payees_dialog_rejects_duplicate_add(monkeypatch, con):
    payees.add_payee(con, "Grocery Store")
    warnings = []
    dialog = PayeesDialog(con)
    monkeypatch.setattr(
        QInputDialog,
        "getText",
        lambda *args, **kwargs: ("grocery store", True),
    )
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args: warnings.append(args),
    )

    dialog.add_button.click()

    assert warnings != []
    assert payee_names(dialog) == ["Grocery Store"]


def test_payees_dialog_renames_selected_payee(monkeypatch, con):
    payees.add_payee(con, "Grocery Store")
    dialog = PayeesDialog(con)
    dialog.payee_list.setCurrentRow(0)
    monkeypatch.setattr(
        QInputDialog,
        "getText",
        lambda *args, **kwargs: ("Grocery Market", True),
    )

    dialog.rename_button.click()

    assert payee_names(dialog) == ["Grocery Market"]
    assert payees.get_payee_by_name(con, "Grocery Market") is not None


def test_payees_dialog_rename_rejects_duplicate(monkeypatch, con):
    payees.add_payee(con, "Grocery Store")
    payees.add_payee(con, "Fuel Stop")
    warnings = []
    dialog = PayeesDialog(con)
    dialog.payee_list.setCurrentRow(0)
    monkeypatch.setattr(
        QInputDialog,
        "getText",
        lambda *args, **kwargs: ("grocery store", True),
    )
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args: warnings.append(args),
    )

    dialog.rename_button.click()

    assert warnings != []
    assert payee_names(dialog) == ["Fuel Stop", "Grocery Store"]


def test_payees_dialog_deletes_unused_payee(con):
    payees.add_payee(con, "Grocery Store")
    dialog = PayeesDialog(con)
    dialog.payee_list.setCurrentRow(0)

    dialog.delete_button.click()

    assert payee_names(dialog) == []
    assert payees.get_payee_by_name(con, "Grocery Store") is None


def test_payees_dialog_reassigns_transactions_before_delete(monkeypatch, con):
    old_payee = payees.add_payee(con, "Grocery Store")
    new_payee = payees.add_payee(con, "Grocery Market")
    _create_transaction(con, old_payee)
    dialog = PayeesDialog(con)
    dialog.payee_list.setCurrentRow(1)
    monkeypatch.setattr(
        QInputDialog,
        "getText",
        lambda *args, **kwargs: ("Grocery Market", True),
    )

    dialog.delete_button.click()

    assert payee_names(dialog) == ["Grocery Market"]
    assert payees.count_transactions_for_payee(con, new_payee["id"]) == 1
    assert payees.get_payee_by_name(con, "Grocery Store") is None


def test_payees_dialog_can_reassign_to_new_payee(monkeypatch, con):
    old_payee = payees.add_payee(con, "Grocery Store")
    _create_transaction(con, old_payee)
    dialog = PayeesDialog(con)
    dialog.payee_list.setCurrentRow(0)
    monkeypatch.setattr(
        QInputDialog,
        "getText",
        lambda *args, **kwargs: ("Grocery Market", True),
    )

    dialog.delete_button.click()

    assert payee_names(dialog) == ["Grocery Market"]
    assert payees.get_payee_by_name(con, "Grocery Store") is None
