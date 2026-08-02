from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from db import payees


class PayeesDialog(QDialog):
    def __init__(self, con, parent=None):
        super().__init__(parent)
        self.con = con
        self.setWindowTitle("Payees")

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Payees"))

        # Simple list keeps payee management readable for first UI pass
        self.payee_list = QListWidget()
        self.payee_list.setObjectName("payeeList")
        layout.addWidget(self.payee_list)

        actions = QHBoxLayout()
        self.add_button = QPushButton("Add")
        self.add_button.setObjectName("addPayeeButton")
        self.add_button.clicked.connect(self.add_payee)
        actions.addWidget(self.add_button)

        self.rename_button = QPushButton("Rename")
        self.rename_button.setObjectName("renamePayeeButton")
        self.rename_button.clicked.connect(self.rename_selected_payee)
        actions.addWidget(self.rename_button)

        self.delete_button = QPushButton("Delete")
        self.delete_button.setObjectName("deletePayeeButton")
        self.delete_button.clicked.connect(self.delete_selected_payee)
        actions.addWidget(self.delete_button)
        layout.addLayout(actions)

        self.refresh_payees()

    def refresh_payees(self):
        # Current DB rows are the source of truth after every action
        self.payee_list.clear()
        for payee in payees.list_payees(self.con):
            item = QListWidgetItem(payee["name"])
            item.setData(1, payee["id"])
            self.payee_list.addItem(item)

    def selected_payee_id(self):
        # No selection means action buttons do nothing
        item = self.payee_list.currentItem()
        if item is None:
            return None
        return item.data(1)

    def add_payee(self):
        name, accepted = QInputDialog.getText(
            self,
            "Add Payee",
            "Payee name:",
        )
        if not accepted:
            return
        if not name.strip():
            QMessageBox.warning(self, "Add Payee", "Enter a payee name.")
            return
        if payees.get_payee_by_name(self.con, name.strip()) is not None:
            QMessageBox.warning(self, "Add Payee", "Payee already exists.")
            return

        payees.add_payee(self.con, name.strip())
        self.refresh_payees()

    def rename_selected_payee(self):
        payee_id = self.selected_payee_id()
        if payee_id is None:
            return

        current_name = self.payee_list.currentItem().text()
        name, accepted = QInputDialog.getText(
            self,
            "Rename Payee",
            "Payee name:",
            text=current_name,
        )
        if not accepted:
            return
        renamed_payee = payees.rename_payee(self.con, payee_id, name)
        if renamed_payee is None:
            QMessageBox.warning(
                self,
                "Rename Payee",
                "Enter a unique payee name.",
            )
            return

        self.refresh_payees()

    def delete_selected_payee(self):
        payee_id = self.selected_payee_id()
        if payee_id is None:
            return

        if payees.count_transactions_for_payee(self.con, payee_id) == 0:
            payees.delete_unused_payee(self.con, payee_id)
            self.refresh_payees()
            return

        replacement_name, accepted = QInputDialog.getText(
            self,
            "Reassign Payee",
            "Replacement payee:",
        )
        if not accepted:
            return

        deleted_payee = payees.reassign_transactions_and_delete_payee(
            self.con,
            payee_id,
            replacement_name,
        )
        if deleted_payee is None:
            QMessageBox.warning(
                self,
                "Delete Payee",
                "Choose a different replacement payee.",
            )
            return

        self.refresh_payees()
