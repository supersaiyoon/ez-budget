from PyQt6.QtWidgets import QHBoxLayout, QListWidget, QListWidgetItem, QMainWindow, QStackedWidget, QWidget

from budget_model import create_sample_accounts, create_sample_budgets
from ui.budget_page import BudgetPage
from ui.reports_page import ReportsPage
from ui.styles import APP_STYLE
from ui.transactions_page import TransactionsPage


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.budgets = create_sample_budgets()
        self.accounts = create_sample_accounts()
        self.setWindowTitle("EZ Budget Prototype")
        self.resize(1160, 720)

        shell = QWidget()
        shell_layout = QHBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)

        self.nav = QListWidget()
        self.nav.setObjectName("navList")
        self.nav.setFixedWidth(170)
        for name in ["Budget", "Checking", "Credit Card", "Reports"]:
            item = QListWidgetItem(name)
            item.setSizeHint(item.sizeHint())
            self.nav.addItem(item)
        shell_layout.addWidget(self.nav)

        self.stack = QStackedWidget()
        self.budget_page = BudgetPage(self.budgets, self.refresh_reports)
        self.checking_page = TransactionsPage(self.accounts[0], self.category_names())
        self.credit_card_page = TransactionsPage(self.accounts[1], self.category_names())
        self.reports_page = ReportsPage(self.budgets)
        self.stack.addWidget(self.budget_page)
        self.stack.addWidget(self.checking_page)
        self.stack.addWidget(self.credit_card_page)
        self.stack.addWidget(self.reports_page)
        shell_layout.addWidget(self.stack)

        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)
        self.setCentralWidget(shell)
        self.setStyleSheet(APP_STYLE)

    def refresh_reports(self):
        self.reports_page.refresh()

    def category_names(self):
        names = ["Income"]
        for category in self.budgets[0].master_categories:
            for subcategory in category.subcategories:
                names.append(subcategory.name)
        return names
