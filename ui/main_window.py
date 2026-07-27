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
from db import (
    accounts,
    budgets as budget_records,
    categories,
    database,
    payees,
    settings as app_settings,
    transactions,
)
from ui import budget_page, reports_page, styles, transactions_page


CLOSED_ACCOUNTS_EXPANDED_SETTING = "closed_accounts_expanded"


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

        # Hidden category ID backs virtual income choices without Budget rows
        self.income_category_id = categories.get_or_create_income_category(
            self.con,
        )["id"]

        self.load_budget_income(self.budgets[0])

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

        self.load_budget_allocations(self.budgets[0])

        # Current month spending derives from saved Budget-account activity
        self.load_budget_spending(self.budgets[0])

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
            for transaction_row in transactions.list_transactions(
                self.con,
                account.database_id,
            ):
                account.transactions.append(
                    budget_model.transaction_from_database_row(transaction_row)
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
        # Missing first-run preference keeps Closed section discoverable
        self.closed_accounts_expanded = (
            app_settings.get_setting(
                self.con,
                CLOSED_ACCOUNTS_EXPANDED_SETTING,
                default="true",
            )
            == "true"
        )
        for page_index, name in enumerate(["Budget", "Reports"]):
            item = QListWidgetItem(name)
            item.setSizeHint(item.sizeHint())
            item.setData(Qt.ItemDataRole.UserRole, page_index)
            self.nav.addItem(item)

        self.accounts_header_item = self._add_navigation_header("Accounts", 12)
        self.rebuild_account_navigation()
        shell_layout.addWidget(self.nav)

        # Stack lets navigation swap full workflows without rebuilding windows
        self.stack = QStackedWidget()
        self.budget_page = budget_page.BudgetPage(
            self.budgets,
            self.budget_months_changed,
            self.add_master_category,
            self.add_subcategory,
            self.budget_allocation_changed,
        )
        # Generated visible months load saved planning data for their own dates
        self.refresh_budget_allocations()
        self.refresh_budget_income()
        self.refresh_budget_spending()
        self.budget_page.refresh()
        self.reports_page = reports_page.ReportsPage(self.budgets)
        self.stack.addWidget(self.budget_page)
        self.stack.addWidget(self.reports_page)

        self.transaction_pages = []
        for account in self.accounts:
            # Account pages report edits so controller can persist complete rows
            page = self.create_transaction_page(account)
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
            + ["Closed"]
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

    def rebuild_account_navigation(self):
        # Rows below permanent Accounts header rebuild from active model order
        # Current page identity survives rebuild when matching row still exists
        selected_item = self.nav.currentItem()
        selected_page_index = (
            selected_item.data(Qt.ItemDataRole.UserRole)
            if selected_item is not None
            else None
        )
        self.nav.blockSignals(True)
        # Generated rows and embedded controls clear before fresh ordering
        while self.nav.count() > 3:
            item = self.nav.item(3)
            item_widget = self.nav.itemWidget(item)
            if item_widget is not None:
                self.nav.removeItemWidget(item)
                item_widget.deleteLater()
            self.nav.takeItem(3)

        # Account positions stay aligned with transaction page positions
        self.on_budget_header_item = self._add_navigation_header("On Budget", 11)
        for account_position, account in enumerate(self.accounts):
            if not account.on_budget:
                continue
            item = QListWidgetItem(account.name)
            item.setSizeHint(item.sizeHint())
            item.setData(Qt.ItemDataRole.UserRole, account_position + 2)
            self.nav.addItem(item)

        self.off_budget_header_item = self._add_navigation_header("Off Budget", 11)
        for account_position, account in enumerate(self.accounts):
            if account.on_budget:
                continue
            item = QListWidgetItem(account.name)
            item.setSizeHint(item.sizeHint())
            item.setData(Qt.ItemDataRole.UserRole, account_position + 2)
            self.nav.addItem(item)

        self.closed_account_items = []
        # Embedded Closed header stays visible even before first account closes
        self.closed_accounts_button = QPushButton()
        self.closed_accounts_button.setObjectName("closedAccountsButton")
        closed_header_font = self.closed_accounts_button.font()
        closed_header_font.setPixelSize(11)
        closed_header_font.setBold(True)
        self.closed_accounts_button.setFont(closed_header_font)
        self.closed_accounts_button.setStyleSheet("text-align: left;")
        self.closed_accounts_button.clicked.connect(
            self.toggle_closed_accounts
        )
        closed_header_item = QListWidgetItem("Closed")
        closed_header_item.setSizeHint(
            QSize(
                self.nav.width(),
                self.closed_accounts_button.sizeHint().height() + 12,
            )
        )
        closed_header_item.setFlags(
            closed_header_item.flags() & ~Qt.ItemFlag.ItemIsSelectable
        )
        self.nav.addItem(closed_header_item)
        self.nav.setItemWidget(
            closed_header_item,
            self.closed_accounts_button,
        )

        # Closed names remain display-only until reopen action is connected
        for account in self.closed_accounts:
            item = QListWidgetItem(account.name)
            item.setFlags(
                item.flags() & ~Qt.ItemFlag.ItemIsSelectable
            )
            self.nav.addItem(item)
            self.closed_account_items.append(item)
        self.update_closed_accounts_visibility()

        # Add action stays below every account group
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

        # Selection restoration avoids unexpected page jumps after rebuild
        if selected_page_index is not None:
            for row in range(self.nav.count()):
                if (
                    self.nav.item(row).data(Qt.ItemDataRole.UserRole)
                    == selected_page_index
                ):
                    self.nav.setCurrentRow(row)
                    break
        self.nav.blockSignals(False)

    def toggle_closed_accounts(self):
        # Header button controls archived account visibility without page changes
        self.closed_accounts_expanded = not self.closed_accounts_expanded

        # Immediate write preserves latest user choice across clean or abrupt exit
        app_settings.set_setting(
            self.con,
            CLOSED_ACCOUNTS_EXPANDED_SETTING,
            "true" if self.closed_accounts_expanded else "false",
        )
        self.update_closed_accounts_visibility()

    def update_closed_accounts_visibility(self):
        # Arrow and hidden state reflect one shared expansion flag
        arrow = "▼" if self.closed_accounts_expanded else "▶"
        self.closed_accounts_button.setText(f"{arrow} Closed")
        for item in self.closed_account_items:
            item.setHidden(not self.closed_accounts_expanded)

    def create_transaction_page(self, account):
        # Shared setup keeps loaded, new, and reopened account pages consistent
        return transactions_page.TransactionsPage(
            account,
            categories.list_transaction_categories(self.con),
            self.save_transaction,
            income_category_id=self.income_category_id,
            on_transaction_delete_requested=self.delete_transaction,
            income_reference_date=self.budgets[0].month_date.isoformat(),
            on_account_close_requested=self.close_account,
        )

    def show_navigation_page(self, row):
        item = self.nav.item(row)
        if item is None:
            return

        page_index = item.data(Qt.ItemDataRole.UserRole)
        if page_index is not None:
            if page_index == 0:
                # Deferred repaint avoids rebuilding Budget table while hidden
                self.budget_page.refresh()
            elif page_index == 1:
                # Deferred report refresh uses latest shared budget totals
                self.reports_page.refresh()
            self.stack.setCurrentIndex(page_index)

    def refresh_reports(self):
        # Budget edits need report totals recalculated on demand
        self.reports_page.refresh()

    def budget_months_changed(self):
        # Newly generated months reload saved data before pages recalculate
        self.refresh_budget_allocations()
        self.refresh_budget_income()
        self.refresh_budget_spending()
        self.budget_page.refresh()
        self.refresh_reports()

    def budget_allocation_changed(self, budget, subcategory):
        # Month date and category ID identify one saved allocation
        budget_month = budget_records.get_or_create_budget_month(
            self.con,
            budget.month_date.isoformat(),
        )
        budget_records.set_budget_allocation(
            self.con,
            budget_month["id"],
            subcategory.database_id,
            budget_model.money_to_cents(subcategory.budgeted),
        )
        self.refresh_reports()

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
        page = self.create_transaction_page(account)
        self.transaction_pages.insert(account_position, page)
        self.stack.insertWidget(page_index, page)
        self.rebuild_account_navigation()

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

    def load_budget_allocations(self, budget):
        # Month row scopes saved category amounts to one planning period
        budget_month = budget_records.get_or_create_budget_month(
            self.con,
            budget.month_date.isoformat(),
        )
        for allocation_row in budget_records.list_budget_allocations(
            self.con,
            budget_month["id"],
        ):
            budget.set_category_budgeted(
                allocation_row["budget_category_id"],
                budget_model.money_from_cents(allocation_row["amount"]),
            )

    def refresh_budget_allocations(self):
        # Every generated month receives only allocations saved for its date
        for budget in self.budgets:
            self.load_budget_allocations(budget)

    def load_budget_income(self, budget):
        # Assigned month controls budget timing independently from transaction date
        income_in_cents = transactions.get_monthly_income_total(
            self.con,
            budget.month_date.isoformat(),
        )
        budget.monthly_income = budget_model.money_from_cents(income_in_cents)

    def refresh_budget_income(self):
        # Every generated month receives only income assigned to its date
        for budget in self.budgets:
            self.load_budget_income(budget)

    def load_budget_spending(self, budget):
        # Reset removes categories absent from latest aggregate results
        budget.reset_spending()
        start_date, end_date = budget.month_date_range
        category_totals = transactions.list_category_transaction_totals(
            self.con,
            start_date.isoformat(),
            end_date.isoformat(),
        )
        for category_total in category_totals:
            # Stable category ID applies total without relying on display name
            spending = budget_model.transaction_total_to_spending(
                category_total["total_amount"]
            )
            budget.set_category_spending(
                category_total["budget_category_id"],
                spending,
            )

    def refresh_budget_spending(self):
        # Every generated month may gain or lose spending after transaction edit
        for budget in self.budgets:
            self.load_budget_spending(budget)

    def save_transaction(self, account, transaction):
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

        # Exactly one money column supplies signed database amount
        if (transaction.outgoing == 0) == (transaction.incoming == 0):
            return False

        # Resolve typed payee before writing required relationships
        payee_row = payees.get_or_create_payee(self.con, transaction.payee)
        amount_in_cents = budget_model.transaction_amount_in_cents(transaction)

        if transaction.database_id is None:
            # Missing row id selects insert path for new transaction
            transaction_row = transactions.add_transaction(
                self.con,
                account.database_id,
                payee_row["id"],
                transaction.category_database_id,
                transaction.date,
                amount_in_cents,
                transaction.notes or None,
                transaction.cleared,
                income_month_date=transaction.income_month_date,
            )

            # Retained id sends later cell changes through update path
            transaction.database_id = transaction_row["id"]
            self.refresh_budget_spending()

            # New assigned income may affect any generated Budget month
            self.refresh_budget_income()
            return True

        # Existing row id updates editable values without changing owning account
        transactions.update_transaction(
            self.con,
            transaction.database_id,
            payee_row["id"],
            transaction.category_database_id,
            transaction.date,
            amount_in_cents,
            transaction.notes or None,
            transaction.cleared,
            income_month_date=transaction.income_month_date,
        )
        self.refresh_budget_spending()

        # Updated assignment may remove income from old month and add it elsewhere
        self.refresh_budget_income()
        return True

    def delete_transaction(self, account, transaction):
        # Object identity prevents equal-looking rows from removing wrong model
        transaction_index = next(
            (
                index
                for index, existing_transaction in enumerate(account.transactions)
                if existing_transaction is transaction
            ),
            None,
        )
        if transaction_index is None:
            return False

        if transaction.database_id is not None:
            deleted_row = transactions.delete_transaction(
                self.con,
                transaction.database_id,
            )
            if deleted_row is None:
                return False

        account.transactions.pop(transaction_index)
        self.refresh_budget_spending()
        self.refresh_budget_income()
        return True

    def set_account_closed(self, account, closed):
        if account.database_id is None:
            return False

        source_accounts = self.accounts if closed else self.closed_accounts
        account_index = next(
            (
                index
                for index, existing_account in enumerate(source_accounts)
                if existing_account is account
            ),
            None,
        )
        if account_index is None:
            return False

        account_row = accounts.set_account_closed(
            self.con,
            account.database_id,
            closed,
        )
        if account_row is None:
            return False

        # Database result keeps model state aligned with persisted value
        account.closed = bool(account_row["closed"])
        if closed:
            self.accounts.pop(account_index)
            page = self.transaction_pages.pop(account_index)

            if self.stack.currentWidget() is page:
                # Budget becomes safe destination before selected page disappears
                self.nav.setCurrentRow(0)

            self.stack.removeWidget(page)
            page.deleteLater()
            self.closed_accounts.append(account)
            self.rebuild_account_navigation()
            return True

        self.closed_accounts.pop(account_index)
        if account.on_budget:
            active_position = sum(
                existing_account.on_budget
                for existing_account in self.accounts
            )
        else:
            active_position = len(self.accounts)
        self.accounts.insert(active_position, account)
        page = self.create_transaction_page(account)
        self.transaction_pages.insert(active_position, page)
        self.stack.insertWidget(active_position + 2, page)
        self.rebuild_account_navigation()
        return True

    def close_account(self, account):
        # Page callback exposes only close action while shared method supports reopen
        return self.set_account_closed(account, True)

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
