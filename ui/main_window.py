from datetime import date
from decimal import Decimal
from pathlib import Path

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QStackedWidget,
    QVBoxLayout,
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
from ui import budget_page, payees_dialog, reports_page, styles, transactions_page


CLOSED_ACCOUNTS_EXPANDED_SETTING = "closed_accounts_expanded"
ACCOUNT_NAV_INDENT_WIDTH = 12
NAV_WIDTH = 170
NAV_BUTTON_WIDTH = NAV_WIDTH - 24
PAYEES_ICON_PATH = Path(__file__).parent / "assets" / "icons" / "payees.svg"
SETTINGS_ICON_PATH = Path(__file__).parent / "assets" / "icons" / "settings.svg"


def index_by_identity(items, selected_item):
    # Object identity keeps equal-looking model rows distinct
    return next(
        (
            index
            for index, item in enumerate(items)
            if item is selected_item
        ),
        None,
    )


class AccountDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Account")

        layout = QFormLayout(self)
        self.name_input = QLineEdit()
        layout.addRow("Account name:", self.name_input)

        # Optional starting amount prepares account without manual first transaction
        self.opening_balance_input = QLineEdit()
        self.opening_balance_input.setObjectName("openingBalanceInput")
        self.opening_balance_input.setPlaceholderText("0.00")
        layout.addRow("Opening balance:", self.opening_balance_input)

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

    def opening_balance(self):
        # Blank optional field represents zero while typed values use money rules
        raw_value = self.opening_balance_input.text().strip()
        if not raw_value:
            return Decimal("0.00")
        return budget_model.parse_money(raw_value)


class MainWindow(QMainWindow):
    def __init__(self, db_path="ez_budget.db"):
        super().__init__()
        # One month keeps navigation valid without showing sample data
        self.budgets = [budget_model.create_empty_budget()]
        self.con = database.connect(db_path)
        database.initialize_database(self.con)
        # Page created after initial hidden-category query
        self.budget_page = None

        # Hidden category ID backs virtual income choices without Budget rows
        self.income_category_id = categories.get_or_create_income_category(
            self.con,
        )["id"]

        # Hidden rows stay outside active Budget models until restored
        self.refresh_hidden_category_rows()

        self.load_startup_budget_data()

        self.accounts = self.load_accounts()
        self.accounts.sort(key=lambda account: not account.on_budget)

        self.closed_accounts = self.load_closed_accounts()

        self.setWindowTitle("EZ Budget")
        self.resize(1160, 720)

        shell = QWidget()
        shell_layout = QHBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)

        self.navigation_sidebar = self.create_navigation_sidebar()
        shell_layout.addWidget(self.navigation_sidebar)

        # Stack lets navigation swap full workflows without rebuilding windows
        self.stack = QStackedWidget()
        self.budget_page = self.create_budget_page()

        self.refresh_budget_page_totals()
        self.reports_page = reports_page.ReportsPage(self.budgets)
        self.stack.addWidget(self.budget_page)
        self.stack.addWidget(self.reports_page)

        self.transaction_pages = self.create_transaction_pages(
            self.accounts,
        )
        self.closed_transaction_pages = self.create_closed_transaction_pages(
            self.closed_accounts,
        )

        shell_layout.addWidget(self.stack)

        self.nav.currentRowChanged.connect(self.show_navigation_page)
        self.nav.setCurrentRow(0)
        self.setCentralWidget(shell)
        self.setStyleSheet(styles.APP_STYLE)

    def account_from_database_row(self, account_row):
        # Startup account models include persisted transaction history
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
        return account

    def load_accounts(self):
        # Active accounts drive navigation and editable transaction pages
        return [
            self.account_from_database_row(account_row)
            for account_row in accounts.list_accounts(self.con)
        ]

    def load_closed_accounts(self):
        # Closed accounts keep history available outside active workflows
        return [
            self.account_from_database_row(account_row)
            for account_row in accounts.list_closed_accounts(self.con)
        ]

    def load_startup_budget_data(self):
        # BudgetPage constructor needs the first month already populated
        current_budget = self.budgets[0]
        self.load_budget_income(current_budget)
        self.load_budget_categories(current_budget)
        self.load_budget_allocations(current_budget)
        self.load_budget_spending(current_budget)

    def load_budget_categories(self, budget):
        # Visible database categories become active Budget rows
        for category_row in categories.list_master_categories(self.con):
            category = budget_model.MasterCategory(
                category_row["name"],
                database_id=category_row["id"],
            )
            for subcategory_row in categories.list_budget_categories(
                self.con,
                category_row["id"],
            ):
                subcategory = budget_model.Subcategory(
                    subcategory_row["name"],
                    Decimal("0.00"),
                    Decimal("0.00"),
                    database_id=subcategory_row["id"],
                )
                category.subcategories.append(subcategory)
            budget.master_categories.append(category)

    def create_budget_page(self):
        # Callback wiring keeps persistence in MainWindow, not BudgetPage
        return budget_page.BudgetPage(
            self.budgets,
            self.budget_months_changed,
            self.add_master_category,
            self.add_subcategory,
            self.budget_allocation_changed,
            on_master_category_rename_requested=(
                self.prompt_for_master_category_rename
            ),
            on_subcategory_rename_requested=(
                self.prompt_for_subcategory_rename
            ),
            on_master_category_delete_requested=self.delete_master_category,
            on_subcategory_delete_requested=self.delete_subcategory,
            hidden_master_category_rows=self.hidden_master_category_rows,
            hidden_subcategory_rows=self.hidden_subcategory_rows,
            on_master_category_restore_requested=(
                self.restore_master_category
            ),
            on_subcategory_restore_requested=self.restore_subcategory,
            on_master_categories_reordered=self.reorder_master_categories,
            on_subcategories_reordered=self.reorder_subcategories,
        )

    def create_transaction_pages(self, account_list):
        # Active account pages include the blank entry row
        pages = []
        for account in account_list:
            page = self.create_transaction_page(account)
            pages.append(page)
            self.stack.addWidget(page)
        return pages

    def create_closed_transaction_pages(self, account_list):
        # Closed account pages show history without new entry rows
        pages = []
        for account in account_list:
            page = self.create_transaction_page(
                account,
                allow_new_transactions=False,
            )
            pages.append(page)
            self.stack.addWidget(page)
        return pages

    def create_navigation_sidebar(self):
        # Account list scrolls independently from pinned bottom actions
        sidebar = QWidget()
        sidebar.setObjectName("navigationSidebar")
        sidebar.setFixedWidth(NAV_WIDTH)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.nav = self.create_navigation_list()
        layout.addWidget(self.nav, 1)

        actions = QWidget()
        actions.setObjectName("navigationActions")
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(8, 8, 8, 10)
        actions_layout.setSpacing(8)

        self.payees_button = QPushButton()
        self.payees_button.setObjectName("payeesButton")
        self.payees_button.setToolTip("Payees")
        self.payees_button.setIcon(QIcon(str(PAYEES_ICON_PATH)))
        self.payees_button.setIconSize(QSize(18, 18))
        self.payees_button.setFixedSize(44, 44)
        self.payees_button.clicked.connect(self.open_payees_dialog)
        actions_layout.addWidget(self.payees_button)

        self.settings_button = QPushButton()
        self.settings_button.setObjectName("settingsButton")
        self.settings_button.setToolTip("Settings coming later")
        self.settings_button.setIcon(QIcon(str(SETTINGS_ICON_PATH)))
        self.settings_button.setIconSize(QSize(18, 18))
        self.settings_button.setFixedSize(44, 44)
        actions_layout.addWidget(self.settings_button)
        actions_layout.addStretch()

        layout.addWidget(actions)
        return sidebar

    def create_navigation_list(self):
        # Left rail kept fixed so page switching stays predictable
        nav = QListWidget()
        nav.setObjectName("navList")
        nav.setFixedWidth(NAV_WIDTH)
        nav.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.nav = nav

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
            nav.addItem(item)

        self.accounts_header_item = self._add_navigation_header("Accounts", 12)
        self.rebuild_account_navigation()
        return nav

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

    def refresh_hidden_category_rows(self):
        # Separate collections match Hidden section group and child entries
        self.hidden_master_category_rows = (
            categories.list_hidden_master_categories(self.con)
        )
        self.hidden_subcategory_rows = (
            categories.list_hidden_budget_categories(self.con)
        )
        # Existing page receives fresh query rows after hide or later restore
        if self.budget_page is not None:
            self.budget_page.set_hidden_category_rows(
                self.hidden_master_category_rows,
                self.hidden_subcategory_rows,
            )

    def _add_navigation_header(self, text, pixel_size):
        item = QListWidgetItem(text)
        header_font = item.font()
        header_font.setPixelSize(pixel_size)
        header_font.setBold(True)
        item.setFont(header_font)
        item.setSizeHint(QSize(NAV_WIDTH, 36))
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
        self.nav.addItem(item)
        return item

    def _add_account_navigation_item(self, account, page_index):
        item = QListWidgetItem(account.name)
        indent_icon = QPixmap(ACCOUNT_NAV_INDENT_WIDTH, 1)
        indent_icon.fill(Qt.GlobalColor.transparent)
        # Transparent decoration indents child rows without changing item text
        item.setIcon(QIcon(indent_icon))
        item_font = item.font()
        item_font.setPixelSize(11)
        item.setFont(item_font)
        item.setSizeHint(QSize(NAV_WIDTH, 32))
        item.setData(Qt.ItemDataRole.UserRole, page_index)
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
            self._add_account_navigation_item(account, account_position + 2)

        self.off_budget_header_item = self._add_navigation_header("Off Budget", 11)
        for account_position, account in enumerate(self.accounts):
            if account.on_budget:
                continue
            self._add_account_navigation_item(account, account_position + 2)

        self.closed_account_items = []
        # Embedded Closed header stays visible even before first account closes
        self.closed_accounts_button = QPushButton()
        self.closed_accounts_button.setObjectName("closedAccountsButton")
        closed_header_font = self.closed_accounts_button.font()
        closed_header_font.setPixelSize(11)
        closed_header_font.setBold(True)
        self.closed_accounts_button.setFont(closed_header_font)
        self.closed_accounts_button.setStyleSheet("text-align: left;")
        self.closed_accounts_button.setFixedWidth(NAV_BUTTON_WIDTH)
        self.closed_accounts_button.setFixedHeight(36)
        self.closed_accounts_button.clicked.connect(
            self.toggle_closed_accounts
        )

        self.closed_accounts_header_item = QListWidgetItem("Closed")

        # Full nav padding prevents embedded button from collapsing into a bar
        self.closed_accounts_header_item.setSizeHint(
            QSize(
                NAV_WIDTH,
                42,
            )
        )

        self.closed_accounts_header_item.setFlags(
            self.closed_accounts_header_item.flags()
            & ~Qt.ItemFlag.ItemIsSelectable
        )

        self.nav.addItem(self.closed_accounts_header_item)
        self.nav.setItemWidget(
            self.closed_accounts_header_item,
            self.closed_accounts_button,
        )

        # Closed account rows navigate like normal account rows
        for account_position, account in enumerate(self.closed_accounts):
            item = self._add_account_navigation_item(
                account,
                2 + len(self.accounts) + account_position,
            )
            self.closed_account_items.append(item)
        self.update_closed_accounts_visibility()

        # Add action stays below every account group
        self.add_account_button = QPushButton("+ Add Account")
        self.add_account_button.setObjectName("addAccountButton")
        self.add_account_button.setFixedHeight(36)
        self.add_account_button.clicked.connect(self.prompt_for_account)
        self._add_navigation_button(self.add_account_button)

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

    def _add_navigation_button(self, button):
        item = QListWidgetItem()

        button.setFixedWidth(NAV_BUTTON_WIDTH)
        item.setSizeHint(QSize(NAV_WIDTH, button.height() + 12))
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
        self.nav.addItem(item)
        self.nav.setItemWidget(item, button)
        return item

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
        arrow = "\u25bc" if self.closed_accounts_expanded else "\u25b6"
        self.closed_accounts_button.setText(f"{arrow} Closed")
        for item in self.closed_account_items:
            item.setHidden(not self.closed_accounts_expanded)

    def create_transaction_page(
        self,
        account,
        allow_new_transactions=True,
    ):
        # Shared setup keeps loaded, new, and reopened account pages consistent
        return transactions_page.TransactionsPage(
            account,
            categories.list_transaction_categories(self.con),
            self.save_transaction,
            income_category_id=self.income_category_id,
            on_transaction_delete_requested=self.delete_transaction,
            income_reference_date=self.budgets[0].month_date.isoformat(),
            on_account_close_requested=self.close_account,
            on_account_reopen_requested=self.reopen_account,
            on_account_delete_requested=self.delete_account,
            allow_new_transactions=allow_new_transactions,
            payee_names=self.payee_names(),
        )

    def payee_names(self):
        # Autocomplete uses same user-facing list as Payees dialog
        return [payee["name"] for payee in payees.list_payees(self.con)]

    def refresh_transaction_payees(self):
        # New saved payees should appear in every open transaction editor
        payee_names = self.payee_names()
        for page in self.transaction_pages + self.closed_transaction_pages:
            page.set_payee_names(payee_names)

    def refresh_transaction_pages(self):
        # Payee management can change joined transaction display names
        for account, page in zip(self.accounts, self.transaction_pages):
            account.transactions = [
                budget_model.transaction_from_database_row(transaction_row)
                for transaction_row in transactions.list_transactions(
                    self.con,
                    account.database_id,
                )
            ]
            page.refresh()
        for account, page in zip(
            self.closed_accounts,
            self.closed_transaction_pages,
        ):
            account.transactions = [
                budget_model.transaction_from_database_row(transaction_row)
                for transaction_row in transactions.list_transactions(
                    self.con,
                    account.database_id,
                )
            ]
            page.refresh()

    def show_closed_account(self, account):
        account_index = index_by_identity(self.closed_accounts, account)
        if account_index is None:
            return False

        # Button-driven row clears active selection before history page swap
        self.nav.setCurrentRow(-1)
        self.stack.setCurrentWidget(
            self.closed_transaction_pages[account_index]
        )
        return True

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

    def refresh_budget_page_totals(self):
        # Generated months reload saved planning data before repaint
        self.refresh_budget_allocations()
        self.refresh_budget_income()
        self.refresh_budget_spending()
        self.budget_page.refresh()

    def budget_months_changed(self):
        self.refresh_budget_page_totals()
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
            try:
                opening_balance = dialog.opening_balance()
            except ValueError as exc:
                QMessageBox.warning(self, "Add Account", str(exc))
                return
            self.submit_account_name(
                dialog.name_input.text(),
                dialog.budget_radio.isChecked(),
                opening_balance,
            )

    def open_payees_dialog(self):
        # Modal manager edits shared DB rows directly
        dialog = payees_dialog.PayeesDialog(self.con, self)
        dialog.exec()
        self.refresh_transaction_pages()
        self.refresh_transaction_payees()

    def submit_account_name(
        self,
        name,
        on_budget=True,
        opening_balance=Decimal("0.00"),
    ):
        name = name.strip()
        if not name:
            QMessageBox.warning(self, "Add Account", "Enter an account name.")
            return

        try:
            self.add_account(name, on_budget, opening_balance)
        except ValueError as exc:
            QMessageBox.warning(self, "Add Account", str(exc))

    def add_account(
        self,
        name,
        on_budget=True,
        opening_balance=Decimal("0.00"),
    ):
        if accounts.get_account_by_name(self.con, name) is not None:
            raise ValueError("Account already exists.")

        account_row = accounts.create_account(self.con, name, on_budget)
        account = budget_model.Account(
            account_row["name"],
            database_id=account_row["id"],
            on_budget=bool(account_row["on_budget"]),
            closed=bool(account_row["closed"]),
        )

        if opening_balance != 0:
            # Opening balance uses normal transaction storage and balance math
            opening_transaction = budget_model.Transaction(
                date=date.today().isoformat(),
                payee="Opening Balance",
                category="Income",
                notes="",
                outgoing=(
                    abs(opening_balance)
                    if opening_balance < 0
                    else Decimal("0.00")
                ),
                incoming=(
                    opening_balance
                    if opening_balance > 0
                    else Decimal("0.00")
                ),
                cleared=True,
                category_database_id=self.income_category_id,
                income_month_date=self.budgets[0].month_date.isoformat(),
            )
            account.transactions.append(opening_transaction)
            self.save_transaction(account, opening_transaction)

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

    def rename_master_category(self, master_category_id, name):
        name = name.strip()
        if not name:
            raise ValueError("Enter a master category name.")

        existing_category = categories.get_master_category_by_name(
            self.con,
            name,
        )
        if (
            existing_category is not None
            and existing_category["id"] != master_category_id
        ):
            raise ValueError("Master category already exists.")

        renamed_row = categories.rename_master_category(
            self.con,
            master_category_id,
            name,
        )
        if renamed_row is None:
            return False

        # Shared ID updates same category object in every generated month
        for budget in self.budgets:
            for master_category in budget.master_categories:
                if master_category.database_id == master_category_id:
                    master_category.name = renamed_row["name"]
                    break

        self.refresh_category_views()
        return True

    def reorder_master_categories(self, ordered_master_category_ids):
        # Drag order is persisted once, then mirrored into every loaded month
        categories.reorder_master_categories(
            self.con,
            ordered_master_category_ids,
        )
        order_by_id = {
            category_id: index
            for index, category_id in enumerate(ordered_master_category_ids)
        }
        for budget in self.budgets:
            budget.master_categories.sort(
                key=lambda category: order_by_id.get(
                    category.database_id,
                    len(order_by_id),
                )
            )

        self.refresh_category_views()

    def prompt_for_master_category_rename(self, master_category):
        name, accepted = QInputDialog.getText(
            self,
            "Rename Master Category",
            "Master category name:",
            QLineEdit.EchoMode.Normal,
            master_category.name,
        )
        if not accepted:
            return False

        try:
            renamed = self.rename_master_category(
                master_category.database_id,
                name,
            )
        except ValueError as exc:
            self.budget_page.status.setText(str(exc))
            return False

        if renamed:
            self.budget_page.status.setText(
                f'Renamed master category to "{name.strip()}".'
            )
        return renamed

    def rename_subcategory(
        self,
        master_category_id,
        budget_category_id,
        name,
    ):
        name = name.strip()
        if not name:
            raise ValueError("Enter a subcategory name.")

        existing_category = categories.get_budget_category_by_name(
            self.con,
            master_category_id,
            name,
        )
        if (
            existing_category is not None
            and existing_category["id"] != budget_category_id
        ):
            raise ValueError(
                "Subcategory already exists in this master category."
            )

        renamed_row = categories.rename_budget_category(
            self.con,
            budget_category_id,
            name,
        )
        if renamed_row is None:
            return False

        # Stable category ID updates every month without changing allocations
        for budget in self.budgets:
            for master_category in budget.master_categories:
                for subcategory in master_category.subcategories:
                    if subcategory.database_id == budget_category_id:
                        subcategory.name = renamed_row["name"]
                        break

        # Existing rows retain display name alongside unchanged database ID
        for account in self.accounts + self.closed_accounts:
            for transaction in account.transactions:
                if transaction.category_database_id == budget_category_id:
                    transaction.category = renamed_row["name"]

        self.refresh_category_views()
        return True

    def reorder_subcategories(
        self,
        master_category_id,
        ordered_budget_category_ids,
    ):
        # Subcategory order stays scoped to one parent category
        categories.reorder_budget_categories(
            self.con,
            master_category_id,
            ordered_budget_category_ids,
        )
        order_by_id = {
            category_id: index
            for index, category_id in enumerate(ordered_budget_category_ids)
        }
        for budget in self.budgets:
            for master_category in budget.master_categories:
                if master_category.database_id != master_category_id:
                    continue
                master_category.subcategories.sort(
                    key=lambda subcategory: order_by_id.get(
                        subcategory.database_id,
                        len(order_by_id),
                    )
                )
                break

        self.refresh_category_views()

    def prompt_for_subcategory_rename(
        self,
        master_category,
        subcategory,
    ):
        name, accepted = QInputDialog.getText(
            self,
            "Rename Subcategory",
            "Subcategory name:",
            QLineEdit.EchoMode.Normal,
            subcategory.name,
        )
        if not accepted:
            return False

        try:
            renamed = self.rename_subcategory(
                master_category.database_id,
                subcategory.database_id,
                name,
            )
        except ValueError as exc:
            self.budget_page.status.setText(str(exc))
            return False

        if renamed:
            self.budget_page.status.setText(
                f'Renamed subcategory to "{name.strip()}".'
            )
        return renamed

    def delete_master_category(self, master_category):
        # Stable database ID scopes group across every loaded budget month
        if master_category.database_id is None:
            return False

        # Include individually hidden children omitted from active Budget models
        child_category_ids = {
            subcategory.database_id
            for subcategory in master_category.subcategories
        }
        child_category_ids.update(
            row["id"]
            for row in self.hidden_subcategory_rows
            if (
                row["master_budget_category_id"]
                == master_category.database_id
            )
        )
        has_transactions = any(
            transaction.category_database_id in child_category_ids
            for account in self.accounts + self.closed_accounts
            for transaction in account.transactions
        )

        if has_transactions:
            choice = QMessageBox.question(
                self,
                "Delete Master Category",
                (
                    f'"{master_category.name}" cannot be deleted because one '
                    "or more subcategories have transactions. Hide master "
                    "category instead?"
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if choice != QMessageBox.StandardButton.Yes:
                return False

            changed_row = categories.set_master_category_hidden(
                self.con,
                master_category.database_id,
                True,
            )
            action = "Hidden"
        else:
            choice = QMessageBox.question(
                self,
                "Delete Master Category",
                f'Delete "{master_category.name}" permanently?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if choice != QMessageBox.StandardButton.Yes:
                return False

            changed_row = categories.delete_master_category(
                self.con,
                master_category.database_id,
            )
            action = "Deleted"

        if changed_row is None:
            return False

        # Remove matching group from every generated month
        for budget in self.budgets:
            budget.master_categories = [
                loaded_master_category
                for loaded_master_category in budget.master_categories
                if (
                    loaded_master_category.database_id
                    != master_category.database_id
                )
            ]

        self.refresh_budget_allocations()
        self.refresh_budget_spending()
        self.refresh_hidden_category_views()
        self.budget_page.status.setText(
            f'{action} master category "{master_category.name}".'
        )
        return True

    def restore_master_category(self, category_row):
        # Database flag returns group to active category queries
        restored_row = categories.set_master_category_hidden(
            self.con,
            category_row["id"],
            False,
        )
        if restored_row is None:
            return False

        subcategory_rows = categories.list_budget_categories(
            self.con,
            restored_row["id"],
        )

        # Rebuild same stable category identities in every generated month
        for budget in self.budgets:
            master_category = budget_model.MasterCategory(
                restored_row["name"],
                database_id=restored_row["id"],
            )
            for subcategory_row in subcategory_rows:
                master_category.subcategories.append(
                    budget_model.Subcategory(
                        subcategory_row["name"],
                        Decimal("0.00"),
                        Decimal("0.00"),
                        database_id=subcategory_row["id"],
                    )
                )
            budget.master_categories.append(master_category)

        # Restored rows regain saved month allocations and transaction spending
        self.refresh_budget_allocations()
        self.refresh_budget_spending()
        self.refresh_hidden_category_views()
        self.budget_page.status.setText(
            f'Restored master category "{restored_row["name"]}".'
        )
        return True

    def restore_subcategory(self, category_row):
        # Database flag returns category to active Budget and transaction queries
        restored_row = categories.set_budget_category_hidden(
            self.con,
            category_row["id"],
            False,
        )
        if restored_row is None:
            return False

        # Stable parent ID restores category under matching group in every month
        for budget in self.budgets:
            for master_category in budget.master_categories:
                if (
                    master_category.database_id
                    != restored_row["master_budget_category_id"]
                ):
                    continue
                master_category.subcategories.append(
                    budget_model.Subcategory(
                        restored_row["name"],
                        Decimal("0.00"),
                        Decimal("0.00"),
                        database_id=restored_row["id"],
                    )
                )
                break

        # Restored row regains saved month allocations and transaction spending
        self.refresh_budget_allocations()
        self.refresh_budget_spending()
        self.refresh_hidden_category_views()
        self.budget_page.status.setText(
            f'Restored subcategory "{restored_row["name"]}".'
        )
        return True

    def delete_subcategory(self, master_category, subcategory):
        if subcategory.database_id is None:
            return False

        # Saved transaction relationships decide whether data must be retained
        has_transactions = any(
            transaction.category_database_id == subcategory.database_id
            for account in self.accounts + self.closed_accounts
            for transaction in account.transactions
        )
        if has_transactions:
            choice = QMessageBox.question(
                self,
                "Delete Subcategory",
                (
                    f'"{subcategory.name}" cannot be deleted because it has '
                    "transactions. Hide subcategory instead?"
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if choice != QMessageBox.StandardButton.Yes:
                return False

            changed_row = categories.set_budget_category_hidden(
                self.con,
                subcategory.database_id,
                True,
            )
            action = "Hidden"
        else:
            choice = QMessageBox.question(
                self,
                "Delete Subcategory",
                f'Delete "{subcategory.name}" permanently?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if choice != QMessageBox.StandardButton.Yes:
                return False

            changed_row = categories.delete_budget_category(
                self.con,
                subcategory.database_id,
            )
            action = "Deleted"

        if changed_row is None:
            return False

        # Stable ID removes matching category from every loaded budget month
        for budget in self.budgets:
            for loaded_master_category in budget.master_categories:
                if (
                    loaded_master_category.database_id
                    != master_category.database_id
                ):
                    continue
                loaded_master_category.subcategories = [
                    loaded_subcategory
                    for loaded_subcategory
                    in loaded_master_category.subcategories
                    if (
                        loaded_subcategory.database_id
                        != subcategory.database_id
                    )
                ]
                break

        self.refresh_budget_allocations()
        self.refresh_budget_spending()
        self.refresh_hidden_category_views()
        self.budget_page.status.setText(
            f'{action} subcategory "{subcategory.name}".'
        )
        return True

    def refresh_category_views(self):
        # Category edits affect Budget rows and transaction dropdown labels
        self.budget_page.refresh()
        self.refresh_transaction_categories()

    def refresh_hidden_category_views(self):
        # Hidden list must reload after hide or restore
        self.refresh_hidden_category_rows()
        self.refresh_category_views()

    def refresh_transaction_categories(self):
        # Query once so every existing account page receives the same current choices
        category_rows = categories.list_transaction_categories(self.con)
        for page in (
            self.transaction_pages + self.closed_transaction_pages
        ):
            page.set_category_rows(category_rows)

    def active_budget_category_ids(self, budget):
        # Hidden categories are absent from active Budget rows
        return {
            subcategory.database_id
            for master_category in budget.master_categories
            for subcategory in master_category.subcategories
        }

    def load_budget_allocations(self, budget):
        # Month row scopes saved category amounts to one planning period
        budget.hidden_budgeted = Decimal("0.00")
        budget_month = budget_records.get_or_create_budget_month(
            self.con,
            budget.month_date.isoformat(),
        )
        active_category_ids = self.active_budget_category_ids(budget)
        for allocation_row in budget_records.list_budget_allocations(
            self.con,
            budget_month["id"],
        ):
            # Hidden category allocations stay saved until category is restored
            if allocation_row["budget_category_id"] not in active_category_ids:
                budget.hidden_budgeted += budget_model.money_from_cents(
                    allocation_row["amount"]
                )
                continue
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

        active_category_ids = self.active_budget_category_ids(budget)

        for category_total in category_totals:
            # Hidden category spending stays queryable without an active UI row
            if category_total["budget_category_id"] not in active_category_ids:
                budget.hidden_spent += (
                    budget_model.transaction_total_to_spending(
                        category_total["total_amount"]
                    )
                )
                continue
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
            self.refresh_transaction_payees()
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
        self.refresh_transaction_payees()
        return True

    def delete_transaction(self, account, transaction):
        transaction_index = index_by_identity(account.transactions, transaction)
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

    def delete_account(self, account):
        if account.database_id is None:
            return False

        account_index = index_by_identity(self.accounts, account)
        if account_index is None:
            return False

        if account.transactions:
            # Accounts with history can leave active workflow without data loss
            choice = QMessageBox.question(
                self,
                "Delete Account",
                (
                    f'"{account.name}" cannot be deleted because it has '
                    "transactions. Close account instead?"
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if choice == QMessageBox.StandardButton.Yes:
                return self.close_account(account)
            return False

        # Permanent deletion requires confirmation even when account is empty
        choice = QMessageBox.question(
            self,
            "Delete Account",
            f'Delete "{account.name}" permanently?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if choice != QMessageBox.StandardButton.Yes:
            return False

        deleted_row = accounts.delete_account(
            self.con,
            account.database_id,
        )
        if deleted_row is None:
            return False

        self.accounts.pop(account_index)
        page = self.transaction_pages.pop(account_index)
        if self.stack.currentWidget() is page:
            # Budget becomes safe destination before selected page disappears
            self.nav.setCurrentRow(0)
        self.stack.removeWidget(page)
        page.deleteLater()
        self.rebuild_account_navigation()
        return True

    def set_account_closed(self, account, closed):
        if account.database_id is None:
            return False

        source_accounts = self.accounts if closed else self.closed_accounts
        account_index = index_by_identity(source_accounts, account)
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

            closed_page = self.create_transaction_page(
                account,
                allow_new_transactions=False,
            )

            self.closed_transaction_pages.append(closed_page)
            self.stack.addWidget(closed_page)
            self.rebuild_account_navigation()
            return True

        self.closed_accounts.pop(account_index)
        closed_page = self.closed_transaction_pages.pop(account_index)

        if self.stack.currentWidget() is closed_page:
            # Budget becomes safe destination before history page disappears
            self.nav.setCurrentRow(0)

        self.stack.removeWidget(closed_page)
        closed_page.deleteLater()
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

    def reopen_account(self, account):
        # Closed-row action restores account through shared state transition
        return self.set_account_closed(account, False)

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

        self.refresh_category_views()
