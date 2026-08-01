from functools import partial
from pathlib import Path

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import (
    QHeaderView,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from budget_model import create_next_month_budget, format_money, parse_money
from ui.helpers import get_category, money_item
from ui.widgets import MonthScroller, VISIBLE_MONTHS, VISIBLE_SCROLLER_MONTHS


RENAME_ICON_PATH = (
    Path(__file__).parent / "assets" / "icons" / "edit_pencil.svg"
)
DELETE_ICON_PATH = (
    Path(__file__).parent / "assets" / "icons" / "delete.svg"
)
BUDGET_VALUE_COLUMN_WIDTH = 96


class BudgetPage(QWidget):
    def __init__(
        self,
        budgets,
        on_budget_changed,
        on_master_category_added,
        on_subcategory_added,
        on_allocation_changed=None,
        on_master_category_rename_requested=None,
        on_subcategory_rename_requested=None,
        on_master_category_delete_requested=None,
        on_subcategory_delete_requested=None,
        hidden_master_category_rows=None,
        hidden_subcategory_rows=None,
        on_master_category_restore_requested=None,
        on_subcategory_restore_requested=None,
    ):
        super().__init__()
        # Shared list so generated months and edits stay visible to other pages
        self.budgets = budgets
        
        # Only signals changed budget data
        self.on_budget_changed = on_budget_changed
        self.on_master_category_added = on_master_category_added
        self.on_subcategory_added = on_subcategory_added
        self.on_allocation_changed = on_allocation_changed
        self.on_master_category_rename_requested = (
            on_master_category_rename_requested
        )
        self.on_subcategory_rename_requested = (
            on_subcategory_rename_requested
        )
        self.on_master_category_delete_requested = (
            on_master_category_delete_requested
        )
        self.on_subcategory_delete_requested = (
            on_subcategory_delete_requested
        )
        self.on_master_category_restore_requested = (
            on_master_category_restore_requested
        )
        self.on_subcategory_restore_requested = (
            on_subcategory_restore_requested
        )
        self.hidden_master_category_rows = []
        self.hidden_subcategory_rows = []
        self.active_index = 0

        # For matching visual rows back to category names
        self.rows = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 8)
        layout.setSpacing(3)

        self.month_scroller = MonthScroller(self.set_active_month)
        layout.addWidget(self.month_scroller, 0, Qt.AlignmentFlag.AlignTop)

        # Side-by-side month comparison
        self.table = QTableWidget()
        self.table.setColumnCount(1 + (VISIBLE_MONTHS * 3))
        self.table.horizontalHeader().setVisible(False)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, self.table.columnCount()):
            # Fixed month columns avoid layout jumps as category rows change
            self.table.horizontalHeader().setSectionResizeMode(
                column,
                QHeaderView.ResizeMode.Fixed,
            )
            self.table.setColumnWidth(column, BUDGET_VALUE_COLUMN_WIDTH)
        layout.addWidget(self.table, 1)

        # Collapsible shell reserved for later hidden-category restore rows
        self.hidden_categories_expanded = False
        self.hidden_categories_section = QWidget()
        hidden_section_layout = QVBoxLayout(self.hidden_categories_section)
        hidden_section_layout.setContentsMargins(0, 0, 0, 0)
        hidden_section_layout.setSpacing(0)

        self.hidden_categories_button = QPushButton()
        self.hidden_categories_button.setObjectName("hiddenCategoriesButton")
        hidden_button_font = self.hidden_categories_button.font()
        hidden_button_font.setPixelSize(10)
        hidden_button_font.setBold(True)
        self.hidden_categories_button.setFont(hidden_button_font)
        self.hidden_categories_button.setStyleSheet("text-align: left;")
        self.hidden_categories_button.clicked.connect(
            self.toggle_hidden_categories
        )
        hidden_section_layout.addWidget(self.hidden_categories_button)

        # Empty container keeps row rendering separate from expansion behavior
        self.hidden_categories_content = QWidget()
        self.hidden_categories_content.setObjectName("hiddenCategoriesContent")
        self.hidden_categories_content_layout = QVBoxLayout(
            self.hidden_categories_content
        )
        self.hidden_categories_content_layout.setContentsMargins(8, 0, 0, 0)
        self.hidden_categories_content_layout.setSpacing(2)
        hidden_section_layout.addWidget(self.hidden_categories_content)
        layout.addWidget(self.hidden_categories_section)
        self.set_hidden_category_rows(
            hidden_master_category_rows,
            hidden_subcategory_rows,
        )
        self.update_hidden_categories_visibility()

        self.category_header = QWidget()
        category_header_layout = QHBoxLayout(self.category_header)
        category_header_layout.setContentsMargins(8, 0, 8, 0)
        category_label = QLabel("Category")
        category_label.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        category_header_layout.addWidget(category_label)
        category_header_layout.addStretch()
        self.add_master_category_button = QPushButton("+")
        self.add_master_category_button.setObjectName("addMasterCategoryButton")
        self.add_master_category_button.setToolTip("Add master category")
        # Bold icon-sized plus matches weight of filled rename SVG
        add_master_font = self.add_master_category_button.font()
        add_master_font.setPixelSize(18)
        add_master_font.setBold(True)
        self.add_master_category_button.setFont(add_master_font)
        self.add_master_category_button.setFixedWidth(28)
        self.add_master_category_button.clicked.connect(self.prompt_for_master_category)
        category_header_layout.addWidget(self.add_master_category_button)

        self.status = QLabel("Enter a positive or negative amount, then press Enter or leave the field.")
        self.status.setObjectName("statusText")
        self.status.setFixedHeight(20)
        layout.addWidget(self.status)

        self.refresh()

    def visible_budgets(self):
        # Active month plus neighbors, matching the comparison window width
        return self.budgets[self.active_index : self.active_index + VISIBLE_MONTHS]

    def set_hidden_category_rows(
        self,
        master_category_rows,
        subcategory_rows,
    ):
        # Controller-owned query results ready for later section rendering
        self.hidden_master_category_rows = (
            master_category_rows
            if master_category_rows is not None
            else []
        )
        self.hidden_subcategory_rows = (
            subcategory_rows
            if subcategory_rows is not None
            else []
        )
        self._refresh_hidden_category_rows()

    def _refresh_hidden_category_rows(self):
        # Replace stale widgets after controller supplies fresh query rows
        while self.hidden_categories_content_layout.count():
            layout_item = self.hidden_categories_content_layout.takeAt(0)
            widget = layout_item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        for category_row in self.hidden_master_category_rows:
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(8, 2, 8, 2)

            label = QLabel(category_row["name"])
            label.setObjectName("hiddenMasterCategoryLabel")
            label.setFont(
                QFont("Segoe UI", 10, QFont.Weight.DemiBold)
            )
            row_layout.addWidget(label)
            row_layout.addStretch()

            restore_button = QPushButton("Restore")
            restore_button.setObjectName("restoreMasterCategoryButton")
            restore_button.setProperty(
                "master_category_id",
                category_row["id"],
            )
            restore_button.clicked.connect(
                lambda checked=False, row=category_row: (
                    self.request_master_category_restore(row)
                )
            )
            row_layout.addWidget(restore_button)
            self.hidden_categories_content_layout.addWidget(row_widget)

        # Parent context distinguishes same-named subcategories
        for category_row in self.hidden_subcategory_rows:
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(16, 2, 8, 2)

            label = QLabel(
                f'{category_row["master_category_name"]}: '
                f'{category_row["name"]}'
            )
            label.setObjectName("hiddenSubcategoryLabel")
            row_layout.addWidget(label)
            row_layout.addStretch()

            restore_button = QPushButton("Restore")
            restore_button.setObjectName("restoreSubcategoryButton")
            restore_button.setProperty(
                "budget_category_id",
                category_row["id"],
            )
            restore_button.clicked.connect(
                lambda checked=False, row=category_row: (
                    self.request_subcategory_restore(row)
                )
            )
            row_layout.addWidget(restore_button)
            self.hidden_categories_content_layout.addWidget(row_widget)

    def request_master_category_restore(self, category_row):
        # Page reports selected database row while controller owns persistence
        if self.on_master_category_restore_requested is not None:
            self.on_master_category_restore_requested(category_row)

    def request_subcategory_restore(self, category_row):
        # Stable row ID keeps restore correctly scoped under parent category
        if self.on_subcategory_restore_requested is not None:
            self.on_subcategory_restore_requested(category_row)

    def visible_scroller_indexes(self):
        # Centered window when possible, easier context while stepping through months
        half_window = VISIBLE_SCROLLER_MONTHS // 2
        start_index = max(self.active_index - half_window, 0)
        return range(start_index, start_index + VISIBLE_SCROLLER_MONTHS)

    def set_active_month(self, index):
        # Clamp left edge so arrow clicks cannot ask for a negative month
        self.active_index = max(index, 0)
        created_future_month = self.ensure_visible_months()
        self.refresh()

        # Persist only when navigation forced new budget data into existence
        if created_future_month:
            self.on_budget_changed()

    def ensure_visible_months(self):
        # Scroller can look farther ahead than the table, so both ranges need backing data
        scroller_indexes = list(self.visible_scroller_indexes())
        count = max(self.active_index + VISIBLE_MONTHS, scroller_indexes[-1] + 1)
        created_future_month = False

        while count > len(self.budgets):
            # Future month starts clean while preserving category structure and income
            self.budgets.append(create_next_month_budget(self.budgets[-1]))
            created_future_month = True
        return created_future_month

    def refresh(self):
        # Regenerate from model state so edits, generated months, and summaries stay aligned
        self.ensure_visible_months()
        scroller_indexes = list(self.visible_scroller_indexes())
        budgets = self.visible_budgets()
        indexed_budgets = [(index, self.budgets[index]) for index in scroller_indexes]
        self.month_scroller.set_months(indexed_budgets, self.active_index)
        self._refresh_budget_table(budgets)

    def toggle_hidden_categories(self):
        # Header controls restore-area visibility without rebuilding Budget table
        self.hidden_categories_expanded = not self.hidden_categories_expanded
        self.update_hidden_categories_visibility()

    def update_hidden_categories_visibility(self):
        # Arrow and container share one expansion flag
        arrow = "\u25bc" if self.hidden_categories_expanded else "\u25b6"
        self.hidden_categories_button.setText(
            f"{arrow} Hidden Categories"
        )
        self.hidden_categories_content.setVisible(
            self.hidden_categories_expanded
        )

    def _refresh_budget_table(self, budgets):
        self.rows = []
        for category in budgets[0].master_categories:
            # Master rows anchor groups before subcategory rows add editable detail
            self.rows.append((category.name, None))
            for subcategory in category.subcategories:
                self.rows.append((category.name, subcategory.name))

        # Two header rows leave room for month summary plus per-month money columns
        self.table.clearSpans()
        # Drop old data widgets before shifted rows rebuild
        self.table.setRowCount(2)
        self.table.setRowCount(len(self.rows) + 2)
        self._set_table_headers(budgets)
        for row, (category_name, subcategory_name) in enumerate(self.rows, start=2):
            if subcategory_name is None:
                self._set_master_row(row, category_name, budgets)
            else:
                self._set_subcategory_row(row, category_name, subcategory_name, budgets)

    def _set_table_headers(self, budgets):
        self.table.setItem(0, 0, QTableWidgetItem(""))

        # Category header separated from month headers for scan-friendly budgeting
        if self.table.cellWidget(1, 0) is None:
            self.table.setCellWidget(1, 0, self.category_header)

        for month_index, budget in enumerate(budgets):
            # Month group owns three child columns, keeping totals close to inputs
            column = 1 + (month_index * 3)
            month = QTableWidgetItem(
                f"{budget.month_name}\n"
                f"Income: {format_money(budget.monthly_income)}\n"
                f"Available: {format_money(budget.available_to_budget)}\n"
                f"Budgeted: {format_money(budget.total_budgeted)}\n"
                # Negative display shows money leaving budget without changing model math
                f"Spent: {format_money(-budget.total_spent)}"
            )
            month.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
            month.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(0, column, month)
            self.table.setSpan(0, column, 1, 3)

            # Comparing months side by side
            for offset, label in enumerate(["Budgeted", "Spent", "Remaining"]):
                item = QTableWidgetItem(label)
                item.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(1, column + offset, item)

        self.table.setRowHeight(0, 98)
        self.table.setRowHeight(1, 30)

    def prompt_for_master_category(self):
        name, accepted = QInputDialog.getText(
            self,
            "Add Master Category",
            "Master category name:",
        )
        if accepted:
            self.submit_master_category_name(name)

    def prompt_for_subcategory(self, master_category_id):
        name, accepted = QInputDialog.getText(
            self,
            "Add Subcategory",
            "Subcategory name:",
        )
        if accepted:
            self.submit_subcategory_name(master_category_id, name)

    def submit_master_category_name(self, name):
        name = name.strip()
        if not name:
            self.status.setText("Enter a master category name.")
            return

        try:
            self.on_master_category_added(name)
        except ValueError as exc:
            self.status.setText(str(exc))
            return

        self.status.setText(f'Added master category "{name}".')

    def submit_subcategory_name(self, master_category_id, name):
        name = name.strip()
        if not name:
            self.status.setText("Enter a subcategory name.")
            return

        try:
            self.on_subcategory_added(master_category_id, name)
        except ValueError as exc:
            self.status.setText(str(exc))
            return

        self.status.setText(f'Added subcategory "{name}".')

    def request_master_category_rename(self, master_category):
        # Page reports selected model while controller owns persistence
        if self.on_master_category_rename_requested is not None:
            self.on_master_category_rename_requested(master_category)

    def request_subcategory_rename(self, master_category, subcategory):
        # Parent model keeps later duplicate validation correctly scoped
        if self.on_subcategory_rename_requested is not None:
            self.on_subcategory_rename_requested(
                master_category,
                subcategory,
            )

    def request_master_category_delete(self, master_category):
        # Controller decides between permanent deletion and hiding
        if self.on_master_category_delete_requested is not None:
            self.on_master_category_delete_requested(master_category)

    def request_subcategory_delete(self, master_category, subcategory):
        # Parent model keeps later delete or hide handling correctly scoped
        if self.on_subcategory_delete_requested is not None:
            self.on_subcategory_delete_requested(
                master_category,
                subcategory,
            )

    def _set_master_row(self, row, category_name, budgets):
        master_category = get_category(budgets[0], category_name)
        category_cell = QWidget()
        category_cell.setObjectName("masterCategoryCell")
        category_cell.setStyleSheet("#masterCategoryCell { background: lightgray; }")
        category_layout = QHBoxLayout(category_cell)
        category_layout.setContentsMargins(8, 0, 4, 0)

        title = QLabel(category_name)
        title.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        category_layout.addWidget(title)
        category_layout.addStretch()

        rename_button = QPushButton()
        rename_button.setObjectName("renameMasterCategoryButton")
        rename_button.setToolTip(f"Rename {category_name}")
        rename_button.setProperty(
            "master_category_id",
            master_category.database_id,
        )
        # Project SVG provides consistent filled icon across system fonts
        rename_button.setIcon(QIcon(str(RENAME_ICON_PATH)))
        rename_button.setIconSize(QSize(18, 18))
        rename_button.setFixedSize(32, 32)
        rename_button.clicked.connect(
            lambda checked=False, category=master_category: (
                self.request_master_category_rename(category)
            )
        )
        category_layout.addWidget(rename_button)

        delete_button = QPushButton()
        delete_button.setObjectName("deleteMasterCategoryButton")
        delete_button.setToolTip(f"Delete {category_name}")
        delete_button.setProperty(
            "master_category_id",
            master_category.database_id,
        )
        delete_button.setIcon(QIcon(str(DELETE_ICON_PATH)))
        delete_button.setIconSize(QSize(18, 18))
        delete_button.setFixedSize(32, 32)
        delete_button.clicked.connect(
            lambda checked=False, category=master_category: (
                self.request_master_category_delete(category)
            )
        )
        category_layout.addWidget(delete_button)

        add_button = QPushButton("+")
        add_button.setObjectName("addSubcategoryButton")
        add_button.setToolTip(f"Add subcategory to {category_name}")
        add_button.setProperty("master_category_id", master_category.database_id)
        # Same glyph sizing keeps category actions visually balanced
        add_button_font = add_button.font()
        add_button_font.setPixelSize(18)
        add_button_font.setBold(True)
        add_button.setFont(add_button_font)
        add_button.setFixedSize(32, 32)
        add_button.setEnabled(master_category.database_id is not None)
        add_button.clicked.connect(
            lambda checked=False, category_id=master_category.database_id: self.prompt_for_subcategory(
                category_id
            )
        )
        category_layout.addWidget(add_button)
        self.table.setCellWidget(row, 0, category_cell)

        for month_index, budget in enumerate(budgets):
            category = get_category(budget, category_name)
            column = 1 + (month_index * 3)

            self.table.setItem(row, column, QTableWidgetItem(""))
            self.table.setItem(row, column + 1, money_item(-category.spent, bold=True))
            self.table.setItem(row, column + 2, money_item(category.remaining, bold=True))
        self.table.setRowHeight(row, 34)

    def _set_subcategory_row(self, row, category_name, subcategory_name, budgets):
        master_category = get_category(budgets[0], category_name)
        subcategory = budgets[0].get_subcategory(
            category_name,
            subcategory_name,
        )
        category_cell = QWidget()
        category_cell.setObjectName("subcategoryCell")
        category_layout = QHBoxLayout(category_cell)
        category_layout.setContentsMargins(20, 0, 4, 0)
        category_label = QLabel(subcategory_name)
        category_label.setObjectName("subcategoryNameLabel")
        category_layout.addWidget(category_label)
        category_layout.addStretch()

        rename_button = QPushButton()
        rename_button.setObjectName("renameSubcategoryButton")
        rename_button.setToolTip(f"Rename {subcategory_name}")
        rename_button.setProperty(
            "budget_category_id",
            subcategory.database_id,
        )
        # Same SVG treatment keeps rename actions consistent across row types
        rename_button.setIcon(QIcon(str(RENAME_ICON_PATH)))
        rename_button.setIconSize(QSize(12, 12))
        rename_button.setFixedSize(24, 24)
        rename_button.clicked.connect(
            lambda checked=False,
            category=master_category,
            selected_subcategory=subcategory: self.request_subcategory_rename(
                category,
                selected_subcategory,
            )
        )
        category_layout.addWidget(rename_button)

        delete_button = QPushButton()
        delete_button.setObjectName("deleteSubcategoryButton")
        delete_button.setToolTip(f"Delete {subcategory_name}")
        delete_button.setProperty(
            "budget_category_id",
            subcategory.database_id,
        )
        # Smaller icon matches existing subcategory action hierarchy
        delete_button.setIcon(QIcon(str(DELETE_ICON_PATH)))
        delete_button.setIconSize(QSize(12, 12))
        delete_button.setFixedSize(24, 24)
        delete_button.clicked.connect(
            lambda checked=False,
            category=master_category,
            selected_subcategory=subcategory: self.request_subcategory_delete(
                category,
                selected_subcategory,
            )
        )
        category_layout.addWidget(delete_button)
        self.table.setCellWidget(row, 0, category_cell)

        for month_index, budget in enumerate(budgets):
            subcategory = budget.get_subcategory(category_name, subcategory_name)
            column = 1 + (month_index * 3)

            input_field = QLineEdit()
            # Current assignment stays visible while cell remains editable
            if subcategory.budgeted != 0:
                input_field.setText(format(subcategory.budgeted, ".2f"))
            input_field.setPlaceholderText("0.00")
            input_field.setFixedWidth(116)
            input_field.setAlignment(Qt.AlignmentFlag.AlignRight)
            input_field.editingFinished.connect(
                partial(self.apply_adjustment, budget, category_name, subcategory_name, input_field)
            )

            self.table.setCellWidget(row, column, input_field)
            self.table.setItem(row, column + 1, money_item(-subcategory.spent))
            self.table.setItem(row, column + 2, money_item(subcategory.remaining))
        self.table.setRowHeight(row, 38)

    def apply_adjustment(self, budget, category_name, subcategory_name, input_field):
        raw_value = input_field.text().strip()
        if not raw_value:
            return

        try:
            new_budgeted = parse_money(raw_value)
        except ValueError as exc:
            # Keep bad input in place so user can fix it without retyping
            self.status.setText(str(exc))
            return

        subcategory = budget.get_subcategory(category_name, subcategory_name)
        if new_budgeted == subcategory.budgeted:
            return

        # Displayed value is target total, so model receives only difference
        adjustment = new_budgeted - subcategory.budgeted
        budget.apply_adjustment(category_name, subcategory_name, str(adjustment))
        self.status.setText(
            f"{budget.month_name}: budgeted {format_money(new_budgeted)} for {subcategory_name}. "
            f"Available: {format_money(budget.available_to_budget)}"
        )

        self.refresh()
        if self.on_allocation_changed is not None:
            self.on_allocation_changed(budget, subcategory)
