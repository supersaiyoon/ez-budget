from functools import partial
from html import escape
from pathlib import Path

from PyQt6.QtCore import QEvent, QTimer, QSize, Qt
from PyQt6.QtGui import QColor, QFont, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
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

from budget_model import (
    create_next_month_budget,
    create_previous_month_budget,
    format_money,
    parse_money,
)
from ui.helpers import get_category, money_item, numeric_font
from ui.widgets import MonthScroller, VISIBLE_MONTHS, VISIBLE_SCROLLER_MONTHS


RENAME_ICON_PATH = (
    Path(__file__).parent / "assets" / "icons" / "edit_pencil.svg"
)
DELETE_ICON_PATH = (
    Path(__file__).parent / "assets" / "icons" / "delete.svg"
)
ADD_ICON_PATH = (
    Path(__file__).parent / "assets" / "icons" / "add.svg"
)
BUDGET_VALUE_COLUMN_WIDTH = 96
FEEDBACK_KIND_PROPERTY = "feedbackKind"
EMPTY_FEEDBACK_KIND = "empty"
SUCCESS_FEEDBACK_TIMEOUT_MS = 5000


class BudgetAmountInput(QLineEdit):
    def __init__(self, on_tab_navigation, on_enter_pressed):
        super().__init__()
        self.on_tab_navigation = on_tab_navigation
        self.on_enter_pressed = on_enter_pressed

    def focusInEvent(self, event):
        try:
            amount = parse_money(self.text())
        except ValueError:
            pass
        else:
            self.setText(format(amount, ".2f"))
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        try:
            amount = parse_money(self.text())
        except ValueError:
            pass
        else:
            self.setText(format_money(amount))
        super().focusOutEvent(event)

    def event(self, event):
        if event.type() == QEvent.Type.ShortcutOverride:
            if event.key() in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
                event.accept()
                return True
        if event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Tab:
                self.on_tab_navigation(self, 1)
                return True
            if event.key() == Qt.Key.Key_Backtab:
                self.on_tab_navigation(self, -1)
                return True
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.on_enter_pressed(self)
                return True
        return super().event(event)

    def focusNextPrevChild(self, next_child):
        # Qt routes real Tab traversal here before ordinary key handling
        self.on_tab_navigation(self, 1 if next_child else -1)
        return True


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
        on_master_categories_reordered=None,
        on_subcategories_reordered=None,
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
        self.on_master_categories_reordered = on_master_categories_reordered
        self.on_subcategories_reordered = on_subcategories_reordered
        self.hidden_master_category_rows = []
        self.hidden_subcategory_rows = []
        self.active_index = 0
        self.pending_budget_focus = None

        # For matching visual rows back to category names
        self.rows = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 8)
        layout.setSpacing(3)

        self.month_scroller = MonthScroller(self.set_active_month)
        layout.addWidget(self.month_scroller, 0, Qt.AlignmentFlag.AlignTop)

        self.feedback = QLabel()
        self.feedback.setObjectName("feedbackMessage")
        self.feedback.setWordWrap(True)
        self.feedback.setFixedHeight(30)
        self.feedback_generation = 0
        self.clear_feedback()
        layout.addWidget(self.feedback)

        # Side-by-side month comparison
        self.table = QTableWidget()
        self.table.setColumnCount(1 + (VISIBLE_MONTHS * 3))
        self.table.horizontalHeader().setVisible(False)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setTabKeyNavigation(False)
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
        self.drop_indicator = QFrame(self.table.viewport())
        self.drop_indicator.setObjectName("categoryDropIndicator")
        self.drop_indicator.setFixedHeight(2)
        self.drop_indicator.setStyleSheet(
            "#categoryDropIndicator { background: #2f6f8f; }"
        )
        self.drop_indicator.hide()
        self.drag_state = None
        self.drop_target = None

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
        self.add_master_category_button = QPushButton()
        self.add_master_category_button.setObjectName("addMasterCategoryButton")
        self.add_master_category_button.setToolTip("Add master category")
        self.add_master_category_button.setIcon(QIcon(str(ADD_ICON_PATH)))
        self.add_master_category_button.setIconSize(QSize(14, 14))
        self.add_master_category_button.setFixedWidth(28)
        self.add_master_category_button.clicked.connect(self.prompt_for_master_category)
        category_header_layout.addWidget(self.add_master_category_button)

        self.status = QLabel("Enter a positive or negative amount, then press Enter or leave the field.")
        self.status.setObjectName("statusText")
        self.status.setFixedHeight(20)
        layout.addWidget(self.status)

        self.refresh()

    def show_feedback(self, message, kind="info"):
        self.feedback_generation += 1
        self.feedback.setText(message)
        self.feedback.setProperty(FEEDBACK_KIND_PROPERTY, kind)
        self.feedback.style().unpolish(self.feedback)
        self.feedback.style().polish(self.feedback)
        if kind == "success":
            generation = self.feedback_generation
            QTimer.singleShot(
                SUCCESS_FEEDBACK_TIMEOUT_MS,
                lambda: self.clear_success_feedback(generation),
            )

    def clear_success_feedback(self, generation):
        if generation == self.feedback_generation:
            self.clear_feedback()

    def clear_feedback(self):
        self.feedback.setText("")
        self.feedback.setProperty(FEEDBACK_KIND_PROPERTY, EMPTY_FEEDBACK_KIND)
        self.feedback.style().unpolish(self.feedback)
        self.feedback.style().polish(self.feedback)

    def focus_adjacent_budget_input(self, current_input, direction):
        focus_target = self.adjacent_budget_focus_target(
            current_input,
            direction,
        )
        if focus_target is None:
            return

        self.commit_budget_input(current_input, focus_target)

    def keep_current_budget_input_active(self, current_input):
        focus_target = self.budget_focus_target(current_input)
        if focus_target is None:
            return

        self.commit_budget_input(current_input, focus_target)

    def budget_focus_target(self, input_field):
        subcategory_id = input_field.property("budget_category_id")
        month_date = input_field.property("budget_month_date")
        if subcategory_id is None or month_date is None:
            return {
                "row": input_field.property("budget_row"),
                "column": input_field.property("budget_column"),
            }

        return {
            "budget_category_id": subcategory_id,
            "budget_month_date": month_date,
        }

    def adjacent_budget_focus_target(self, current_input, direction):
        current_row = current_input.property("budget_row")
        current_column = current_input.property("budget_column")
        if current_row is None or current_column is None:
            return None

        for row in range(
            current_row + direction,
            1 if direction < 0 else self.table.rowCount(),
            direction,
        ):
            next_input = self.table.cellWidget(row, current_column)
            if isinstance(next_input, BudgetAmountInput):
                return self.budget_focus_target(next_input)
        return None

    def restore_pending_budget_focus(self):
        if self.pending_budget_focus is None:
            return

        input_field = self.pending_budget_focus_input()
        if isinstance(input_field, BudgetAmountInput):
            input_field.setFocus(Qt.FocusReason.TabFocusReason)
            input_field.selectAll()
        self.pending_budget_focus = None

    def pending_budget_focus_input(self):
        target = self.pending_budget_focus
        if target is None:
            return None

        if "budget_category_id" not in target:
            return self.table.cellWidget(target["row"], target["column"])

        for row in range(2, self.table.rowCount()):
            for column in range(1, self.table.columnCount(), 3):
                input_field = self.table.cellWidget(row, column)
                if not isinstance(input_field, BudgetAmountInput):
                    continue
                if (
                    input_field.property("budget_category_id")
                    == target["budget_category_id"]
                    and input_field.property("budget_month_date")
                    == target["budget_month_date"]
                ):
                    return input_field
        return None

    def commit_budget_input(self, input_field, focus_target):
        # Command commits replace the widget; suppress a second blur commit
        will_refresh = self.budget_input_will_refresh(input_field)
        input_field.blockSignals(True)
        applied = self.apply_adjustment(
            input_field.property("budget"),
            input_field.property("category_name"),
            input_field.property("subcategory_name"),
            input_field,
        )
        if not will_refresh:
            input_field.blockSignals(False)
        if not applied:
            return

        self.pending_budget_focus = focus_target
        self.restore_pending_budget_focus()

    def budget_input_will_refresh(self, input_field):
        raw_value = input_field.text().strip()
        if not raw_value:
            return False

        try:
            new_budgeted = parse_money(raw_value)
        except ValueError:
            return False

        budget = input_field.property("budget")
        try:
            subcategory = budget.get_subcategory(
                input_field.property("category_name"),
                input_field.property("subcategory_name"),
            )
        except KeyError:
            # This input belonged to a category that was just hidden and removed.
            return False
        return new_budgeted != subcategory.budgeted

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
        # Negative indexes represent earlier months not loaded into the model yet
        half_window = VISIBLE_SCROLLER_MONTHS // 2
        start_index = self.active_index - half_window
        return range(start_index, start_index + VISIBLE_SCROLLER_MONTHS)

    def scroller_budget(self, index):
        if index >= 0:
            return self.budgets[index]

        budget = self.budgets[0]
        for _ in range(-index):
            budget = create_previous_month_budget(budget)
        return budget

    def set_active_month(self, index):
        created_month = False
        if index < 0:
            # Left navigation creates earlier months on demand
            for _ in range(-index):
                self.budgets.insert(
                    0,
                    create_previous_month_budget(self.budgets[0]),
                )
            self.active_index = 0
            created_month = True
        else:
            self.active_index = index
        created_month = self.ensure_visible_months() or created_month
        self.refresh()

        # Persist only when navigation forced new budget data into existence
        if created_month:
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
        indexed_budgets = [
            (index, self.scroller_budget(index))
            for index in scroller_indexes
        ]
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
            summary_text = self.month_summary_text(budget)
            month = QTableWidgetItem(summary_text)
            month.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
            month.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(0, column, month)
            self.table.setCellWidget(
                0,
                column,
                self.month_summary_label(budget, summary_text),
            )
            self.table.setSpan(0, column, 1, 3)

            # Comparing months side by side
            for offset, label in enumerate(["Budgeted", "Spent", "Remaining"]):
                item = QTableWidgetItem(label)
                item.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(1, column + offset, item)

        self.table.setRowHeight(0, 98)
        self.table.setRowHeight(1, 30)

    def month_summary_text(self, budget):
        # Negative spent display shows money leaving budget without changing model math
        return (
            f"{budget.month_name}\n"
            f"Income: {format_money(budget.monthly_income)}\n"
            f"Available: {format_money(budget.available_to_budget)}\n"
            f"Budgeted: {format_money(budget.total_budgeted)}\n"
            f"Spent: {format_money(-budget.total_spent)}"
        )

    def month_summary_label(self, budget, summary_text):
        label = QLabel()
        label.setObjectName("monthSummaryHeader")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        available_color = "#c62828" if budget.available_to_budget < 0 else "#000000"
        lines = summary_text.splitlines()
        label.setText(
            "<br>".join(
                escape(line)
                if not line.startswith("Available:")
                else f'<span style="color: {available_color};">{escape(line)}</span>'
                for line in lines
            )
        )
        return label

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
            self.show_feedback("Enter a master category name.", "warning")
            return

        try:
            self.on_master_category_added(name)
        except ValueError as exc:
            self.show_feedback(str(exc), "warning")
            return

        self.show_feedback(f'Added master category "{name}".', "success")

    def submit_subcategory_name(self, master_category_id, name):
        name = name.strip()
        if not name:
            self.show_feedback("Enter a subcategory name.", "warning")
            return

        try:
            self.on_subcategory_added(master_category_id, name)
        except ValueError as exc:
            self.show_feedback(str(exc), "warning")
            return

        self.show_feedback(f'Added subcategory "{name}".', "success")

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

    def request_master_category_reorder(self, ordered_master_category_ids):
        # Page supplies model IDs while controller owns persistence
        if self.on_master_categories_reordered is not None:
            self.on_master_categories_reordered(ordered_master_category_ids)

    def request_subcategory_reorder(
        self,
        master_category_id,
        ordered_budget_category_ids,
    ):
        # Subcategory moves stay scoped to their parent master category
        if self.on_subcategories_reordered is not None:
            self.on_subcategories_reordered(
                master_category_id,
                ordered_budget_category_ids,
            )

    def ordered_master_category_ids(self):
        return [
            category.database_id
            for category in self.budgets[0].master_categories
        ]

    def ordered_subcategory_ids(self, master_category_id):
        for master_category in self.budgets[0].master_categories:
            if master_category.database_id == master_category_id:
                return [
                    subcategory.database_id
                    for subcategory in master_category.subcategories
                ]
        return []

    def moved_ids(self, ordered_ids, moved_id, target_index):
        # Drop index is calculated against the original visible order
        ids = list(ordered_ids)
        source_index = ids.index(moved_id)
        ids.pop(source_index)
        if source_index < target_index:
            target_index -= 1
        ids.insert(target_index, moved_id)
        return ids

    def eventFilter(self, watched, event):
        if watched.property("category_row_kind") is None:
            return super().eventFilter(watched, event)

        if event.type() == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.LeftButton:
                self.start_category_drag(watched, event.globalPosition().toPoint())
                return True
        elif event.type() == QEvent.Type.MouseMove:
            if self.drag_state is not None:
                self.update_category_drag(event.globalPosition().toPoint())
                return True
        elif event.type() == QEvent.Type.MouseButtonRelease:
            if self.drag_state is not None:
                self.finish_category_drag()
                return True

        return super().eventFilter(watched, event)

    def start_category_drag(self, widget, global_position):
        self.drag_state = {
            "kind": widget.property("category_row_kind"),
            "master_category_id": widget.property("master_category_id"),
            "budget_category_id": widget.property("budget_category_id"),
            "press_position": global_position,
            "active": False,
        }
        self.drop_target = None

    def update_category_drag(self, global_position):
        if self.drag_state is None:
            return

        if not self.drag_state["active"]:
            distance = (
                global_position - self.drag_state["press_position"]
            ).manhattanLength()
            if distance < QApplication.startDragDistance():
                return
            self.drag_state["active"] = True

        table_position = self.table.viewport().mapFromGlobal(global_position)
        self.update_drop_target(table_position)

    def finish_category_drag(self):
        drop_target = self.drop_target
        drag_state = self.drag_state
        self.clear_drop_indicator()
        self.drag_state = None
        self.drop_target = None
        if drop_target is None or drag_state is None:
            return

        if drag_state["kind"] == "master":
            ordered_ids = self.ordered_master_category_ids()
            moved_id = drag_state["master_category_id"]
            reordered_ids = self.moved_ids(
                ordered_ids,
                moved_id,
                drop_target["target_index"],
            )
            if reordered_ids != ordered_ids:
                self.request_master_category_reorder(reordered_ids)
            return

        ordered_ids = self.ordered_subcategory_ids(
            drag_state["master_category_id"]
        )
        moved_id = drag_state["budget_category_id"]
        reordered_ids = self.moved_ids(
            ordered_ids,
            moved_id,
            drop_target["target_index"],
        )
        if reordered_ids != ordered_ids:
            self.request_subcategory_reorder(
                drag_state["master_category_id"],
                reordered_ids,
            )

    def update_drop_target(self, table_position):
        if self.drag_state is None:
            return

        row = self.table.rowAt(table_position.y())
        if row < 2:
            self.clear_drop_indicator()
            return

        if self.drag_state["kind"] == "master":
            self.update_master_drop_target(row, table_position.y())
        else:
            self.update_subcategory_drop_target(row, table_position.y())

    def update_master_drop_target(self, row, y_position):
        row_metadata = self.row_metadata(row)
        if row_metadata is None:
            self.clear_drop_indicator()
            return

        ordered_ids = self.ordered_master_category_ids()
        target_master_id = row_metadata["master_category_id"]
        target_index = ordered_ids.index(target_master_id)
        row_middle = self.table.rowViewportPosition(row) + (
            self.table.rowHeight(row) / 2
        )
        insert_after = y_position > row_middle
        if insert_after:
            target_index += 1

        indicator_row = self.master_group_last_row(target_master_id) if insert_after else self.master_group_first_row(target_master_id)
        self.drop_target = {"target_index": target_index}
        self.show_drop_indicator(indicator_row, after=insert_after)

    def update_subcategory_drop_target(self, row, y_position):
        row_metadata = self.row_metadata(row)
        if (
            row_metadata is None
            or row_metadata["master_category_id"]
            != self.drag_state["master_category_id"]
        ):
            self.clear_drop_indicator()
            return

        ordered_ids = self.ordered_subcategory_ids(
            self.drag_state["master_category_id"]
        )
        if row_metadata["kind"] == "master":
            target_index = 0
            indicator_row = row
            insert_after = True
        else:
            target_index = ordered_ids.index(row_metadata["budget_category_id"])
            row_middle = self.table.rowViewportPosition(row) + (
                self.table.rowHeight(row) / 2
            )
            insert_after = y_position > row_middle
            if insert_after:
                target_index += 1
            indicator_row = row

        self.drop_target = {"target_index": target_index}
        self.show_drop_indicator(indicator_row, after=insert_after)

    def row_metadata(self, row):
        if row < 2 or row - 2 >= len(self.rows):
            return None

        category_name, subcategory_name = self.rows[row - 2]
        master_category = get_category(self.budgets[0], category_name)
        if subcategory_name is None:
            return {
                "kind": "master",
                "master_category_id": master_category.database_id,
            }

        subcategory = self.budgets[0].get_subcategory(
            category_name,
            subcategory_name,
        )
        return {
            "kind": "subcategory",
            "master_category_id": master_category.database_id,
            "budget_category_id": subcategory.database_id,
        }

    def master_group_first_row(self, master_category_id):
        for row in range(2, self.table.rowCount()):
            row_metadata = self.row_metadata(row)
            if row_metadata["master_category_id"] == master_category_id:
                return row
        return 2

    def master_group_last_row(self, master_category_id):
        last_row = self.master_group_first_row(master_category_id)
        for row in range(last_row, self.table.rowCount()):
            row_metadata = self.row_metadata(row)
            if row_metadata["master_category_id"] != master_category_id:
                break
            last_row = row
        return last_row

    def show_drop_indicator(self, row, after=False):
        y_position = self.table.rowViewportPosition(row)
        if after:
            y_position += self.table.rowHeight(row)
        self.drop_indicator.setGeometry(
            0,
            y_position - 1,
            self.table.viewport().width(),
            2,
        )
        self.drop_indicator.raise_()
        self.drop_indicator.show()

    def clear_drop_indicator(self):
        self.drop_indicator.hide()
        self.drop_target = None

    def install_category_drag_filter(self, widget, label):
        # Labels pass title-cell drags through while action buttons stay clickable
        label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        widget.installEventFilter(self)

    def _set_master_row(self, row, category_name, budgets):
        master_category = get_category(budgets[0], category_name)
        category_cell = QWidget()
        category_cell.setObjectName("masterCategoryCell")
        category_cell.setProperty("category_row_kind", "master")
        category_cell.setProperty(
            "master_category_id",
            master_category.database_id,
        )
        category_cell.setStyleSheet("#masterCategoryCell { background: lightgray; }")
        category_layout = QHBoxLayout(category_cell)
        category_layout.setContentsMargins(8, 0, 4, 0)

        title = QLabel(category_name)
        title.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        category_layout.addWidget(title)
        category_layout.addStretch()
        self.install_category_drag_filter(category_cell, title)

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

        add_button = QPushButton()
        add_button.setObjectName("addSubcategoryButton")
        add_button.setToolTip(f"Add subcategory to {category_name}")
        add_button.setProperty("master_category_id", master_category.database_id)
        add_button.setIcon(QIcon(str(ADD_ICON_PATH)))
        add_button.setIconSize(QSize(14, 14))
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

            budgeted_item = money_item(category.budgeted, bold=True)
            spent_item = money_item(-category.spent, bold=True)
            remaining_item = money_item(
                category.remaining,
                bold=True,
                negative_is_warning=True,
            )
            for item in (budgeted_item, spent_item, remaining_item):
                item.setBackground(QColor("lightgray"))
            self.table.setItem(row, column, budgeted_item)
            self.table.setItem(row, column + 1, spent_item)
            self.table.setItem(row, column + 2, remaining_item)
        self.table.setRowHeight(row, 34)

    def _set_subcategory_row(self, row, category_name, subcategory_name, budgets):
        master_category = get_category(budgets[0], category_name)
        subcategory = budgets[0].get_subcategory(
            category_name,
            subcategory_name,
        )
        category_cell = QWidget()
        category_cell.setObjectName("subcategoryCell")
        category_cell.setProperty("category_row_kind", "subcategory")
        category_cell.setProperty(
            "master_category_id",
            master_category.database_id,
        )
        category_cell.setProperty(
            "budget_category_id",
            subcategory.database_id,
        )
        category_layout = QHBoxLayout(category_cell)
        category_layout.setContentsMargins(20, 0, 4, 0)
        category_label = QLabel(subcategory_name)
        category_label.setObjectName("subcategoryNameLabel")
        category_layout.addWidget(category_label)
        category_layout.addStretch()
        self.install_category_drag_filter(category_cell, category_label)

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

            input_field = BudgetAmountInput(
                self.focus_adjacent_budget_input,
                self.keep_current_budget_input_active,
            )
            input_field.setProperty("budget_row", row)
            input_field.setProperty("budget_column", column)
            input_field.setProperty(
                "budget_category_id",
                subcategory.database_id,
            )
            input_field.setProperty(
                "budget_month_date",
                budget.month_date.isoformat(),
            )
            input_field.setProperty("budget", budget)
            input_field.setProperty("category_name", category_name)
            input_field.setProperty("subcategory_name", subcategory_name)
            # Current assignment stays visible while cell remains editable
            if subcategory.budgeted != 0:
                input_field.setText(format_money(subcategory.budgeted))
            input_field.setPlaceholderText("0.00")
            # Cell widget fills fixed Budgeted column instead of spilling over
            input_field.setMaximumWidth(BUDGET_VALUE_COLUMN_WIDTH)
            input_field.setAlignment(Qt.AlignmentFlag.AlignRight)
            input_field.setFont(numeric_font())
            input_field.editingFinished.connect(
                partial(self.apply_adjustment, budget, category_name, subcategory_name, input_field)
            )

            self.table.setCellWidget(row, column, input_field)
            self.table.setItem(row, column + 1, money_item(-subcategory.spent))
            self.table.setItem(
                row,
                column + 2,
                money_item(subcategory.remaining, negative_is_warning=True),
            )
        self.table.setRowHeight(row, 38)

    def apply_adjustment(self, budget, category_name, subcategory_name, input_field):
        raw_value = input_field.text().strip()
        if not raw_value:
            return True

        try:
            new_budgeted = parse_money(raw_value)
        except ValueError as exc:
            # Keep bad input in place so user can fix it without retyping
            self.pending_budget_focus = None
            input_field.setFocus(Qt.FocusReason.OtherFocusReason)
            self.show_feedback(str(exc), "warning")
            return False

        try:
            subcategory = budget.get_subcategory(category_name, subcategory_name)
        except KeyError:
            # This input belonged to a category that was just hidden and removed
            return False
        if new_budgeted == subcategory.budgeted:
            if input_field.hasFocus():
                input_field.setText(format(subcategory.budgeted, ".2f"))
            else:
                input_field.setText(format_money(subcategory.budgeted))
            return True

        # Displayed value is target total, so model receives only difference
        adjustment = new_budgeted - subcategory.budgeted
        budget.apply_adjustment(category_name, subcategory_name, str(adjustment))
        self.show_feedback(
            f"{budget.month_name}: budgeted {format_money(new_budgeted)} for {subcategory_name}. "
            f"Available: {format_money(budget.available_to_budget)}",
            "success" if budget.available_to_budget >= 0 else "warning",
        )

        self.refresh()
        if self.on_allocation_changed is not None:
            self.on_allocation_changed(budget, subcategory)
        return True
