from decimal import Decimal

from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
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
            account = budget_model.Account(account_row["name"])
            self.accounts.append(account)

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
        for name in self.nav_names():
            item = QListWidgetItem(name)
            item.setSizeHint(item.sizeHint())
            self.nav.addItem(item)
        shell_layout.addWidget(self.nav)

        # Stack lets navigation swap full workflows without rebuilding windows
        self.stack = QStackedWidget()
        self.budget_page = budget_page.BudgetPage(
            self.budgets,
            self.refresh_reports,
            self.add_master_category,
        )
        self.reports_page = reports_page.ReportsPage(self.budgets)
        self.stack.addWidget(self.budget_page)

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

        self.stack.addWidget(self.reports_page)
        shell_layout.addWidget(self.stack)

        # Row order mirrors stack order so navigation needs no mapping table
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)
        self.setCentralWidget(shell)
        self.setStyleSheet(styles.APP_STYLE)

    def nav_names(self):
        account_names = []
        for account in self.accounts:
            account_names.append(account.name)

        if not account_names:
            account_names.append("Accounts")

        return ["Budget"] + account_names + ["Reports"]

    def refresh_reports(self):
        # Budget edits need report totals recalculated on demand
        self.reports_page.refresh()

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
