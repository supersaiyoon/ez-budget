from decimal import Decimal

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QWidget,
)

import budget_model
from db import accounts, categories, database
from ui import budget_page, reports_page, styles, transactions_page


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
            self.accounts.append(account)

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
        for page_index, name in enumerate(self.nav_names()):
            item = QListWidgetItem(name)
            item.setSizeHint(item.sizeHint())
            item.setData(Qt.ItemDataRole.UserRole, page_index)
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
            page = transactions_page.TransactionsPage(
                account,
                self.category_names(),
            )
            self.transaction_pages.append(page)
            self.stack.addWidget(page)

        if not self.accounts:
            self.empty_accounts_page = QLabel("No accounts yet.")
            self.empty_accounts_page.setObjectName("pageTitle")
            self.stack.addWidget(self.empty_accounts_page)

        shell_layout.addWidget(self.stack)

        self.nav.currentRowChanged.connect(self.show_navigation_page)
        self.nav.setCurrentRow(0)
        self.setCentralWidget(shell)
        self.setStyleSheet(styles.APP_STYLE)

    def nav_names(self):
        account_names = []
        for account in self.accounts:
            account_names.append(account.name)

        if not account_names:
            account_names.append("Accounts")

        return ["Budget", "Reports"] + account_names

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
        name, accepted = QInputDialog.getText(
            self,
            "Add Account",
            "Account name:",
        )
        if accepted:
            self.submit_account_name(name)

    def submit_account_name(self, name):
        name = name.strip()
        if not name:
            QMessageBox.warning(self, "Add Account", "Enter an account name.")
            return

        try:
            self.add_account(name)
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
        self.accounts.append(account)

        account_index = len(self.accounts) + 1
        replacing_empty_page = len(self.accounts) == 1
        empty_page_selected = replacing_empty_page and self.nav.currentRow() == 2
        if replacing_empty_page:
            self.stack.removeWidget(self.empty_accounts_page)
            self.nav.takeItem(2)

        page = transactions_page.TransactionsPage(
            account,
            self.category_names(),
        )
        self.transaction_pages.append(page)
        self.stack.insertWidget(account_index, page)

        nav_item = QListWidgetItem(account.name)
        nav_item.setSizeHint(nav_item.sizeHint())
        nav_item.setData(Qt.ItemDataRole.UserRole, account_index)
        self.nav.insertItem(account_index, nav_item)
        if empty_page_selected:
            self.nav.setCurrentRow(account_index)

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

    def category_names(self):
        # Transaction categories sourced from budget structure to avoid drift
        names = ["Income"]
        for category in self.budgets[0].master_categories:
            for subcategory in category.subcategories:
                names.append(subcategory.name)
        return names
