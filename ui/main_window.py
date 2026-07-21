from decimal import Decimal

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QStackedWidget,
    QWidget,
)

import budget_model
from db import accounts, categories, database, payees, transactions
from ui import budget_page, reports_page, styles, transactions_page


class AccountDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Account")

        layout = QFormLayout(self)
        self.name_input = QLineEdit()
        layout.addRow("Account name:", self.name_input)

        account_type_layout = QHBoxLayout()
        self.budget_radio = QRadioButton("Budget")
        self.off_budget_radio = QRadioButton("Off-Budget")
        self.budget_radio.setChecked(True)
        account_type_layout.addWidget(self.budget_radio)
        account_type_layout.addWidget(self.off_budget_radio)
        layout.addRow("Account type:", account_type_layout)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)


class MainWindow(QMainWindow):
    def __init__(self, db_path="ez_budget.db"):
        super().__init__()
        # One month keeps navigation valid without showing sample data
        self.budgets = [budget_model.create_empty_budget()]
        self.con = database.connect(db_path)
        database.initialize_database(self.con)

        # Load master categories from db into budget
        for category_row in categories.list_master_categories(self.con):
            category = budget_model.MasterCategory(
                category_row["name"],
                database_id=category_row["id"],
            )
            for subcategory_row in categories.list_budget_categories(self.con, category_row["id"]):
                subcategory = budget_model.Subcategory(
                    subcategory_row["name"],
                    Decimal("0.00"),
                    Decimal("0.00"),
                    database_id=subcategory_row["id"],
                )
                category.subcategories.append(subcategory)
            self.budgets[0].master_categories.append(category)

        self.accounts = []
        for account_row in accounts.list_accounts(self.con):
            account = budget_model.Account(
                account_row["name"],
                database_id=account_row["id"],
                on_budget=bool(account_row["on_budget"]),
                closed=bool(account_row["closed"]),
            )
            for transaction_row in transactions.list_transactions(self.con, account.database_id):
                account.transactions.append(
                    budget_model.transaction_from_database_row(transaction_row)
                )
            self.accounts.append(account)
        self.accounts.sort(key=lambda account: not account.on_budget)

        self.closed_accounts = []
        for account_row in accounts.list_closed_accounts(self.con):
            account = budget_model.Account(
                account_row["name"],
                database_id=account_row["id"],
                on_budget=bool(account_row["on_budget"]),
                closed=bool(account_row["closed"]),
            )
            self.closed_accounts.append(account)

        self.setWindowTitle("EZ Budget")
        self.resize(1160, 720)

        shell = QWidget()
        shell_layout = QHBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)

        # Left rail kept fixed so page switching stays predictable
        self.nav = QListWidget()
        self.nav.setObjectName("navList")
        self.nav.setFixedWidth(170)
        for page_index, name in enumerate(["Budget", "Reports"]):
            item = QListWidgetItem(name)
            item.setSizeHint(item.sizeHint())
            item.setData(Qt.ItemDataRole.UserRole, page_index)
            self.nav.addItem(item)

        self.accounts_header_item = self._add_navigation_header("Accounts", 12)
        self.on_budget_header_item = self._add_navigation_header("On Budget", 11)

        for account_position, account in enumerate(self.accounts):
            if not account.on_budget:
                continue
            item = QListWidgetItem(account.name)
            item.setSizeHint(item.sizeHint())
            item.setData(
                Qt.ItemDataRole.UserRole,
                account_position + 2,
            )
            self.nav.addItem(item)

        self.off_budget_header_item = self._add_navigation_header("Off Budget", 11)
        for account_position, account in enumerate(self.accounts):
            if account.on_budget:
                continue
            item = QListWidgetItem(account.name)
            item.setSizeHint(item.sizeHint())
            item.setData(
                Qt.ItemDataRole.UserRole,
                account_position + 2,
            )
            self.nav.addItem(item)

        self.add_account_button = QPushButton("+ Add Account")
        self.add_account_button.setObjectName("addAccountButton")
        self.add_account_button.clicked.connect(self.prompt_for_account)
        add_account_item = QListWidgetItem()
        # Extra height offsets nav item padding around embedded button
        add_account_item.setSizeHint(
            QSize(
                self.nav.width(),
                self.add_account_button.sizeHint().height() + 28,
            )
        )
        add_account_item.setFlags(
            add_account_item.flags() & ~Qt.ItemFlag.ItemIsSelectable
        )
        self.nav.addItem(add_account_item)
        self.nav.setItemWidget(add_account_item, self.add_account_button)
        shell_layout.addWidget(self.nav)

        # Stack lets navigation swap full workflows without rebuilding windows
        self.stack = QStackedWidget()
        self.budget_page = budget_page.BudgetPage(
            self.budgets,
            self.refresh_reports,
            self.add_master_category,
            self.add_subcategory,
        )
        self.reports_page = reports_page.ReportsPage(self.budgets)
        self.stack.addWidget(self.budget_page)
        self.stack.addWidget(self.reports_page)

        self.transaction_pages = []
        for account in self.accounts:
            # Account pages report edits so controller can persist complete rows
            page = transactions_page.TransactionsPage(
                account,
                categories.list_transaction_categories(self.con),
                self.save_new_transaction,
            )
            self.transaction_pages.append(page)
            self.stack.addWidget(page)

        shell_layout.addWidget(self.stack)

        self.nav.currentRowChanged.connect(self.show_navigation_page)
        self.nav.setCurrentRow(0)
        self.setCentralWidget(shell)
        self.setStyleSheet(styles.APP_STYLE)

    def nav_names(self):
        on_budget_names = []
        off_budget_names = []
        for account in self.accounts:
            if account.on_budget:
                on_budget_names.append(account.name)
            else:
                off_budget_names.append(account.name)

        return (
            ["Budget", "Reports", "Accounts", "On Budget"]
            + on_budget_names
            + ["Off Budget"]
            + off_budget_names
        )

    def _add_navigation_header(self, text, pixel_size):
        item = QListWidgetItem(text)
        header_font = item.font()
        header_font.setPixelSize(pixel_size)
        header_font.setBold(True)
        item.setFont(header_font)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
        self.nav.addItem(item)
        return item

    def show_navigation_page(self, row):
        item = self.nav.item(row)
        if item is None:
            return

        page_index = item.data(Qt.ItemDataRole.UserRole)
        if page_index is not None:
            self.stack.setCurrentIndex(page_index)

    def refresh_reports(self):
        # Budget edits need report totals recalculated on demand
        self.reports_page.refresh()

    def prompt_for_account(self):
        dialog = AccountDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.submit_account_name(
                dialog.name_input.text(),
                dialog.budget_radio.isChecked(),
            )

    def submit_account_name(self, name, on_budget=True):
        name = name.strip()
        if not name:
            QMessageBox.warning(self, "Add Account", "Enter an account name.")
            return

        try:
            self.add_account(name, on_budget)
        except ValueError as exc:
            QMessageBox.warning(self, "Add Account", str(exc))

    def add_account(self, name, on_budget=True):
        if accounts.get_account_by_name(self.con, name) is not None:
            raise ValueError("Account already exists.")

        account_row = accounts.create_account(self.con, name, on_budget)
        account = budget_model.Account(
            account_row["name"],
            database_id=account_row["id"],
            on_budget=bool(account_row["on_budget"]),
            closed=bool(account_row["closed"]),
        )
        if account.on_budget:
            account_position = sum(
                existing_account.on_budget
                for existing_account in self.accounts
            )
        else:
            account_position = len(self.accounts)
        self.accounts.insert(account_position, account)

        page_index = account_position + 2
        # Runtime-created pages use same persistence callback as startup pages
        page = transactions_page.TransactionsPage(
            account,
            categories.list_transaction_categories(self.con),
            self.save_new_transaction,
        )
        self.transaction_pages.insert(account_position, page)
        self.stack.insertWidget(page_index, page)

        nav_item = QListWidgetItem(account.name)
        nav_item.setSizeHint(nav_item.sizeHint())
        nav_row = account_position + 4
        if not account.on_budget:
            nav_row += 1
        self.nav.blockSignals(True)
        self.nav.insertItem(nav_row, nav_item)
        budget_account_count = sum(
            existing_account.on_budget
            for existing_account in self.accounts
        )
        for position in range(len(self.accounts)):
            account_row = position + 4
            if position >= budget_account_count:
                account_row += 1
            account_item = self.nav.item(account_row)
            account_item.setData(Qt.ItemDataRole.UserRole, position + 2)
        self.nav.blockSignals(False)

    def add_master_category(self, name):
        if categories.get_master_category_by_name(self.con, name) is not None:
            raise ValueError("Master category already exists.")

        category_row = categories.add_master_category(self.con, name)

        # Category definitions shared across months
        for budget in self.budgets:
            category = budget_model.MasterCategory(
                category_row["name"],
                database_id=category_row["id"],
            )
            budget.master_categories.append(category)

        self.budget_page.refresh()

    def refresh_transaction_categories(self):
        # Query once so every existing account page receives the same current choices
        category_rows = categories.list_transaction_categories(self.con)
        for page in self.transaction_pages:
            page.set_category_rows(category_rows)

    def save_new_transaction(self, account, transaction):
        # A retained row id means this transaction has already been inserted
        if transaction.database_id is not None:
            return False

        # Partial grid rows remain in memory until every required relationship exists
        transaction.date = transaction.date.strip()
        transaction.payee = transaction.payee.strip()
        if (
            account.database_id is None
            or not transaction.date
            or not transaction.payee
            or transaction.category_database_id is None
        ):
            return False

        # Exactly one money column must supply the signed database amount
        if (transaction.outgoing == 0) == (transaction.incoming == 0):
            return False

        # Resolve the typed payee before inserting all required relationships
        payee_row = payees.get_or_create_payee(self.con, transaction.payee)
        transaction_row = transactions.add_transaction(
            self.con,
            account.database_id,
            payee_row["id"],
            transaction.category_database_id,
            transaction.date,
            budget_model.transaction_amount_in_cents(transaction),
            transaction.notes or None,
            transaction.cleared,
        )
        # Retaining the new id prevents later cell events from inserting duplicates
        transaction.database_id = transaction_row["id"]
        return True

    def add_subcategory(self, master_category_id, name):
        existing_subcategory = categories.get_budget_category_by_name(
            self.con,
            master_category_id,
            name,
        )
        if existing_subcategory is not None:
            raise ValueError("Subcategory already exists in this master category.")

        subcategory_row = categories.add_budget_category(
            self.con,
            master_category_id,
            name,
        )

        for budget in self.budgets:
            for master_category in budget.master_categories:
                if master_category.database_id != master_category_id:
                    continue
                subcategory = budget_model.Subcategory(
                    subcategory_row["name"],
                    Decimal("0.00"),
                    Decimal("0.00"),
                    database_id=subcategory_row["id"],
                )
                master_category.subcategories.append(subcategory)
                break

        self.budget_page.refresh()
        self.refresh_transaction_categories()
