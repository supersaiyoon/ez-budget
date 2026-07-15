from PyQt6.QtWidgets import QHBoxLayout, QListWidget, QListWidgetItem, QMainWindow, QStackedWidget, QWidget

import budget_model
from db import accounts, categories, database
from ui import budget_page, reports_page, styles, transactions_page


class MainWindow(QMainWindow):
    def __init__(self, db_path="ez_budget.db"):
        super().__init__()
        # Shared state so pages reflect same sample budget world
        self.budgets = budget_model.create_sample_budgets()
        self.accounts = budget_model.create_sample_accounts()
        self.con = database.connect(db_path)
        database.initialize_database(self.con)
        self.create_sample_account_rows()
        self.create_sample_category_rows()
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
        self.budget_page = budget_page.BudgetPage(self.budgets, self.refresh_reports)
        self.checking_page = transactions_page.TransactionsPage(self.accounts[0], self.category_names())
        self.credit_card_page = transactions_page.TransactionsPage(self.accounts[1], self.category_names())
        self.reports_page = reports_page.ReportsPage(self.budgets)
        self.stack.addWidget(self.budget_page)
        self.stack.addWidget(self.checking_page)
        self.stack.addWidget(self.credit_card_page)
        self.stack.addWidget(self.reports_page)
        shell_layout.addWidget(self.stack)

        # Row order mirrors stack order so navigation needs no mapping table
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)
        self.setCentralWidget(shell)
        self.setStyleSheet(styles.APP_STYLE)

    def create_sample_account_rows(self):
        if accounts.has_accounts(self.con):
            return

        for account in self.accounts:
            accounts.create_account(self.con, account.name)

    def create_sample_category_rows(self):
        for master_category in self.budgets[0].master_categories:
            master_category_row = categories.get_master_category_by_name(
                self.con,
                master_category.name,
            )

            if master_category_row is None:
                master_category_row = categories.add_master_category(
                    self.con,
                    master_category.name,
                )

            for subcategory in master_category.subcategories:
                category_row = categories.get_budget_category_by_name(
                    self.con,
                    subcategory.name,
                )

                if category_row is None:
                    categories.add_budget_category(
                        self.con,
                        master_category_row["id"],
                        subcategory.name,
                    )

    def nav_names(self):
        account_names = []
        for account in accounts.list_accounts(self.con):
            account_names.append(account["name"])
        return ["Budget"] + account_names + ["Reports"]

    def refresh_reports(self):
        # Budget edits need report totals recalculated on demand
        self.reports_page.refresh()

    def category_names(self):
        # Transaction categories sourced from budget structure to avoid drift
        names = ["Income"]
        for category in self.budgets[0].master_categories:
            for subcategory in category.subcategories:
                names.append(subcategory.name)
        return names
