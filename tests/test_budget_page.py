from decimal import Decimal

import pytest

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QApplication, QLabel, QPushButton

from budget_model import Subcategory, create_sample_budgets, format_money
from ui.budget_page import (
    BudgetAmountInput,
    BudgetPage,
)


# Every test in this module creates Qt widgets and requires the shared application
pytestmark = pytest.mark.usefixtures("qapp")


def test_next_month_arrow_can_generate_future_months(qapp):
    budgets = create_sample_budgets()
    change_count = 0

    def on_budget_changed():
        nonlocal change_count
        change_count += 1

    page = BudgetPage(
        budgets,
        on_budget_changed,
        lambda name: None,
        lambda master_category_id, name: None,
    )

    for _ in range(10):
        page.month_scroller.next_button.click()
        qapp.processEvents()

    assert page.active_index == 10
    assert page.month_scroller.active_index == 10
    assert len(budgets) >= 13
    assert change_count > 0


def test_previous_month_arrow_can_generate_past_months(qapp):
    budgets = create_sample_budgets()
    change_count = 0

    def on_budget_changed():
        nonlocal change_count
        change_count += 1

    page = BudgetPage(
        budgets,
        on_budget_changed,
        lambda name: None,
        lambda master_category_id, name: None,
    )

    for _ in range(3):
        page.month_scroller.previous_button.click()
        qapp.processEvents()

    assert page.active_index == 0
    assert page.month_scroller.active_index == 0
    assert budgets[0].month_name == "December 2025"
    assert len(budgets) >= 9
    assert change_count == 3


def test_master_category_name_is_sent_to_callback():
    added_names = []
    page = BudgetPage(
        create_sample_budgets(),
        lambda: None,
        added_names.append,
        lambda master_category_id, name: None,
    )

    page.submit_master_category_name(" Savings ")

    assert added_names == ["Savings"]


def test_budget_category_title_cells_keep_reorder_metadata():
    budgets = create_sample_budgets()
    budgets[0].master_categories[0].database_id = 12
    budgets[0].master_categories[0].subcategories[0].database_id = 24
    page = BudgetPage(
        budgets,
        lambda: None,
        lambda name: None,
        lambda master_category_id, name: None,
    )

    master_cell = page.table.cellWidget(2, 0)
    subcategory_cell = page.table.cellWidget(3, 0)

    assert master_cell.property("category_row_kind") == "master"
    assert master_cell.property("master_category_id") == 12
    assert subcategory_cell.property("category_row_kind") == "subcategory"
    assert subcategory_cell.property("master_category_id") == 12
    assert subcategory_cell.property("budget_category_id") == 24


def test_budget_page_reports_master_category_reorder():
    reordered_ids = []
    page = BudgetPage(
        create_sample_budgets(),
        lambda: None,
        lambda name: None,
        lambda master_category_id, name: None,
        on_master_categories_reordered=reordered_ids.append,
    )

    page.request_master_category_reorder([3, 1, 2])

    assert reordered_ids == [[3, 1, 2]]


def test_budget_page_reports_subcategory_reorder():
    reordered = []
    page = BudgetPage(
        create_sample_budgets(),
        lambda: None,
        lambda name: None,
        lambda master_category_id, name: None,
        on_subcategories_reordered=(
            lambda master_category_id, category_ids: reordered.append(
                (master_category_id, category_ids)
            )
        ),
    )

    page.request_subcategory_reorder(12, [24, 22, 23])

    assert reordered == [(12, [24, 22, 23])]


def test_budget_page_moves_ids_to_drop_index():
    page = BudgetPage(
        create_sample_budgets(),
        lambda: None,
        lambda name: None,
        lambda master_category_id, name: None,
    )

    assert page.moved_ids([1, 2, 3], 1, 3) == [2, 3, 1]
    assert page.moved_ids([1, 2, 3], 3, 0) == [3, 1, 2]


def test_finishing_master_category_drag_reports_reordered_ids():
    budgets = create_sample_budgets()
    for index, master_category in enumerate(
        budgets[0].master_categories,
        start=1,
    ):
        master_category.database_id = index
    reordered_ids = []
    page = BudgetPage(
        budgets,
        lambda: None,
        lambda name: None,
        lambda master_category_id, name: None,
        on_master_categories_reordered=reordered_ids.append,
    )
    page.drag_state = {
        "kind": "master",
        "master_category_id": 1,
        "budget_category_id": None,
        "active": True,
    }
    page.drop_target = {"target_index": 3}

    page.finish_category_drag()

    assert reordered_ids == [[2, 3, 1]]


def test_finishing_subcategory_drag_reports_sibling_order():
    budgets = create_sample_budgets()
    master_category = budgets[0].master_categories[0]
    master_category.database_id = 12
    for index, subcategory in enumerate(master_category.subcategories, start=21):
        subcategory.database_id = index
    reordered = []
    page = BudgetPage(
        budgets,
        lambda: None,
        lambda name: None,
        lambda master_category_id, name: None,
        on_subcategories_reordered=(
            lambda master_category_id, category_ids: reordered.append(
                (master_category_id, category_ids)
            )
        ),
    )
    page.drag_state = {
        "kind": "subcategory",
        "master_category_id": 12,
        "budget_category_id": 21,
        "active": True,
    }
    page.drop_target = {"target_index": 4}

    page.finish_category_drag()

    assert reordered == [(12, [22, 23, 24, 21])]


def test_subcategory_drag_ignores_drop_outside_own_master():
    budgets = create_sample_budgets()
    budgets[0].master_categories[0].database_id = 12
    budgets[0].master_categories[1].database_id = 34
    budgets[0].master_categories[0].subcategories[0].database_id = 21
    page = BudgetPage(
        budgets,
        lambda: None,
        lambda name: None,
        lambda master_category_id, name: None,
    )
    page.drag_state = {
        "kind": "subcategory",
        "master_category_id": 12,
        "budget_category_id": 21,
        "active": True,
    }
    other_master_row = page.rows.index(("Everyday Spending", None)) + 2

    page.update_subcategory_drop_target(
        other_master_row,
        page.table.rowViewportPosition(other_master_row) + 1,
    )

    assert page.drop_target is None
    assert page.drop_indicator.isHidden() is True


def test_master_category_error_is_shown_in_feedback():
    def reject_duplicate(name):
        raise ValueError("Master category already exists.")

    page = BudgetPage(
        create_sample_budgets(),
        lambda: None,
        reject_duplicate,
        lambda master_category_id, name: None,
    )

    page.submit_master_category_name("Savings")

    assert page.feedback.text() == "Master category already exists."
    assert page.feedback.property("feedbackKind") == "warning"
    assert page.feedback.isHidden() is False


def test_subcategory_error_is_shown_in_feedback():
    submitted_categories = []

    def reject_duplicate(master_category_id, name):
        submitted_categories.append((master_category_id, name))
        raise ValueError("Subcategory already exists in this master category.")

    page = BudgetPage(
        create_sample_budgets(),
        lambda: None,
        lambda name: None,
        reject_duplicate,
    )

    page.submit_subcategory_name(12, " Groceries ")

    assert submitted_categories == [(12, "Groceries")]
    assert page.feedback.text() == (
        "Subcategory already exists in this master category."
    )
    assert page.feedback.property("feedbackKind") == "warning"


def test_hidden_categories_section_toggles_open_and_closed():
    page = BudgetPage(
        create_sample_budgets(),
        lambda: None,
        lambda name: None,
        lambda master_category_id, name: None,
    )

    assert page.hidden_categories_expanded is False
    assert page.hidden_categories_button.text() == "▶ Hidden Categories"
    assert page.hidden_categories_content.isHidden() is True

    page.hidden_categories_button.click()

    assert page.hidden_categories_expanded is True
    assert page.hidden_categories_button.text() == "▼ Hidden Categories"
    assert page.hidden_categories_content.isHidden() is False

    page.hidden_categories_button.click()

    assert page.hidden_categories_expanded is False
    assert page.hidden_categories_content.isHidden() is True


def test_hidden_master_category_row_reports_restore_request():
    hidden_master_category = {
        "id": 12,
        "name": "Archived Goals",
        "hidden": True,
    }
    restore_requests = []
    page = BudgetPage(
        create_sample_budgets(),
        lambda: None,
        lambda name: None,
        lambda master_category_id, name: None,
        hidden_master_category_rows=[hidden_master_category],
        on_master_category_restore_requested=restore_requests.append,
    )
    label = page.findChild(QLabel, "hiddenMasterCategoryLabel")
    restore_button = page.findChild(
        QPushButton,
        "restoreMasterCategoryButton",
    )

    assert label.text() == "Archived Goals"
    assert restore_button.text() == "Restore"
    assert restore_button.property("master_category_id") == 12

    restore_button.click()

    assert restore_requests == [hidden_master_category]


def test_hidden_subcategory_row_shows_parent_and_reports_restore_request():
    hidden_subcategory = {
        "id": 34,
        "master_budget_category_id": 12,
        "name": "Groceries",
        "hidden": True,
        "master_category_name": "Everyday Expenses",
    }
    restore_requests = []
    page = BudgetPage(
        create_sample_budgets(),
        lambda: None,
        lambda name: None,
        lambda master_category_id, name: None,
        hidden_subcategory_rows=[hidden_subcategory],
        on_subcategory_restore_requested=restore_requests.append,
    )
    label = page.findChild(QLabel, "hiddenSubcategoryLabel")
    restore_button = page.findChild(
        QPushButton,
        "restoreSubcategoryButton",
    )

    assert label.text() == "Everyday Expenses: Groceries"
    assert restore_button.text() == "Restore"
    assert restore_button.property("budget_category_id") == 34

    restore_button.click()

    assert restore_requests == [hidden_subcategory]


def test_master_category_row_has_subcategory_button_with_database_id():
    budgets = create_sample_budgets()
    budgets[0].master_categories[0].database_id = 12
    page = BudgetPage(
        budgets,
        lambda: None,
        lambda name: None,
        lambda master_category_id, name: None,
    )

    buttons = page.findChildren(QPushButton, "addSubcategoryButton")
    add_button = next(
        button for button in buttons if button.property("master_category_id") == 12
    )

    assert add_button.isEnabled() is True


def test_master_category_rename_button_reports_selected_model():
    budgets = create_sample_budgets()
    master_category = budgets[0].master_categories[0]
    master_category.database_id = 12
    rename_requests = []
    page = BudgetPage(
        budgets,
        lambda: None,
        lambda name: None,
        lambda master_category_id, name: None,
        on_master_category_rename_requested=(
            lambda category: rename_requests.append(category)
        ),
    )
    master_button = next(
        button
        for button in page.findChildren(
            QPushButton,
            "renameMasterCategoryButton",
        )
        if button.property("master_category_id") == 12
    )
    master_button.click()

    assert rename_requests == [master_category]


def test_master_category_delete_button_reports_selected_model():
    budgets = create_sample_budgets()
    master_category = budgets[0].master_categories[0]
    master_category.database_id = 12
    delete_requests = []
    page = BudgetPage(
        budgets,
        lambda: None,
        lambda name: None,
        lambda master_category_id, name: None,
        on_master_category_delete_requested=delete_requests.append,
    )
    delete_button = next(
        button
        for button in page.findChildren(
            QPushButton,
            "deleteMasterCategoryButton",
        )
        if button.property("master_category_id") == 12
    )

    delete_button.click()

    assert delete_requests == [master_category]


def test_subcategory_rename_button_reports_selected_models():
    budgets = create_sample_budgets()
    master_category = budgets[0].master_categories[0]
    subcategory = master_category.subcategories[0]
    subcategory.database_id = 34
    rename_requests = []
    page = BudgetPage(
        budgets,
        lambda: None,
        lambda name: None,
        lambda master_category_id, name: None,
        on_subcategory_rename_requested=(
            lambda category, selected_subcategory: rename_requests.append(
                (category, selected_subcategory)
            )
        ),
    )
    rename_button = next(
        button
        for button in page.findChildren(
            QPushButton,
            "renameSubcategoryButton",
        )
        if button.property("budget_category_id") == 34
    )

    rename_button.click()

    assert rename_requests == [(master_category, subcategory)]


def test_subcategory_delete_button_reports_selected_models():
    budgets = create_sample_budgets()
    master_category = budgets[0].master_categories[0]
    subcategory = master_category.subcategories[0]
    subcategory.database_id = 34
    delete_requests = []
    page = BudgetPage(
        budgets,
        lambda: None,
        lambda name: None,
        lambda master_category_id, name: None,
        on_subcategory_delete_requested=(
            lambda category, selected_subcategory: delete_requests.append(
                (category, selected_subcategory)
            )
        ),
    )
    delete_button = next(
        button
        for button in page.findChildren(
            QPushButton,
            "deleteSubcategoryButton",
        )
        if button.property("budget_category_id") == 34
    )

    delete_button.click()

    assert delete_requests == [(master_category, subcategory)]


def test_spending_values_display_as_negative_on_budget_page():
    budgets = create_sample_budgets()
    page = BudgetPage(
        budgets,
        lambda: None,
        lambda name: None,
        lambda master_category_id, name: None,
    )
    budget = budgets[0]
    master_category = budget.master_categories[0]
    subcategory = master_category.subcategories[0]
    master_row = page.rows.index((master_category.name, None)) + 2
    subcategory_row = page.rows.index(
        (master_category.name, subcategory.name)
    ) + 2

    assert f"Spent: {format_money(-budget.total_spent)}" in page.table.item(0, 1).text()
    assert page.table.item(master_row, 1).text() == format_money(master_category.budgeted)
    assert page.table.item(master_row, 2).text() == format_money(-master_category.spent)
    assert page.table.item(subcategory_row, 2).text() == format_money(-subcategory.spent)


def test_budgeted_cell_displays_current_subcategory_amount():
    budgets = create_sample_budgets()
    budgets[0].master_categories[0].subcategories[0].database_id = 24
    page = BudgetPage(
        budgets,
        lambda: None,
        lambda name: None,
        lambda master_category_id, name: None,
    )
    subcategory = budgets[0].master_categories[0].subcategories[0]
    row = page.rows.index(("Monthly Bills", subcategory.name)) + 2
    budgeted_input = page.table.cellWidget(row, 1)

    assert budgeted_input.text() == format_money(subcategory.budgeted)
    assert isinstance(budgeted_input, BudgetAmountInput)
    assert budgeted_input.property("budget_row") == row
    assert budgeted_input.property("budget_column") == 1
    assert budgeted_input.property("budget_category_id") == 24
    assert budgeted_input.property("budget_month_date") == (
        budgets[0].month_date.isoformat()
    )
def test_budget_input_accepts_tab_shortcut_override():
    page = BudgetPage(
        create_sample_budgets(),
        lambda: None,
        lambda name: None,
        lambda master_category_id, name: None,
    )
    budgeted_input = page.table.cellWidget(3, 1)
    event = QKeyEvent(
        QKeyEvent.Type.ShortcutOverride,
        Qt.Key.Key_Tab,
        Qt.KeyboardModifier.NoModifier,
    )

    handled = budgeted_input.event(event)

    assert handled is True
    assert event.isAccepted()


def test_tab_navigation_moves_between_budget_fields(qapp):
    budgets = create_sample_budgets()
    for index, master_category in enumerate(budgets[0].master_categories):
        for offset, subcategory in enumerate(master_category.subcategories):
            subcategory.database_id = (index * 10) + offset + 1
    page = BudgetPage(
        budgets,
        lambda: None,
        lambda name: None,
        lambda master_category_id, name: None,
    )
    page.show()

    first_input = page.table.cellWidget(3, 1)
    next_input = page.table.cellWidget(4, 1)
    first_input.setFocus()
    first_input.focusNextPrevChild(True)
    qapp.processEvents()

    assert next_input.hasFocus()

    next_input.focusNextPrevChild(False)
    qapp.processEvents()

    assert first_input.hasFocus()

    last_bill_input = page.table.cellWidget(6, 1)
    first_spending_input = page.table.cellWidget(8, 1)
    last_bill_input.setFocus()
    last_bill_input.focusNextPrevChild(True)
    qapp.processEvents()

    assert first_spending_input.hasFocus()


def test_tab_after_budget_edit_focuses_next_rebuilt_budget_field(qapp):
    budgets = create_sample_budgets()
    for index, subcategory in enumerate(
        budgets[0].master_categories[0].subcategories,
        start=21,
    ):
        subcategory.database_id = index
    page = BudgetPage(
        budgets,
        lambda: None,
        lambda name: None,
        lambda master_category_id, name: None,
    )
    first_input = page.table.cellWidget(3, 1)
    page.show()
    first_input.setFocus()
    first_input.setText("2000.00")

    first_input.focusNextPrevChild(True)
    qapp.processEvents()

    rebuilt_next_input = page.table.cellWidget(4, 1)
    assert budgets[0].master_categories[0].subcategories[0].budgeted == (
        Decimal("2000.00")
    )
    assert rebuilt_next_input.property("budget_category_id") == 22
    assert rebuilt_next_input.property("budget_month_date") == (
        budgets[0].month_date.isoformat()
    )
    assert rebuilt_next_input.hasFocus()


def test_enter_after_budget_edit_keeps_same_rebuilt_budget_field_active(qapp):
    budgets = create_sample_budgets()
    budgets[0].master_categories[0].subcategories[0].database_id = 24
    page = BudgetPage(
        budgets,
        lambda: None,
        lambda name: None,
        lambda master_category_id, name: None,
    )
    budgeted_input = page.table.cellWidget(3, 1)
    page.show()
    budgeted_input.setFocus()
    budgeted_input.setText("2000.00")

    QApplication.sendEvent(
        budgeted_input,
        QKeyEvent(
            QKeyEvent.Type.KeyPress,
            Qt.Key.Key_Return,
            Qt.KeyboardModifier.NoModifier,
        )
    )
    qapp.processEvents()

    rebuilt_input = page.table.cellWidget(3, 1)
    assert budgets[0].master_categories[0].subcategories[0].budgeted == (
        Decimal("2000.00")
    )
    assert rebuilt_input.property("budget_category_id") == 24
    assert rebuilt_input.property("budget_month_date") == (
        budgets[0].month_date.isoformat()
    )
    assert rebuilt_input.text() == "2000.00"
    assert rebuilt_input.hasFocus()


def test_editing_budgeted_cell_replaces_current_amount():
    budgets = create_sample_budgets()
    page = BudgetPage(
        budgets,
        lambda: None,
        lambda name: None,
        lambda master_category_id, name: None,
    )
    subcategory = budgets[0].master_categories[0].subcategories[0]
    row = page.rows.index(("Monthly Bills", subcategory.name)) + 2
    budgeted_input = page.table.cellWidget(row, 1)

    budgeted_input.setText("2000.00")
    budgeted_input.editingFinished.emit()

    assert subcategory.budgeted == Decimal("2000.00")


def test_editing_budgeted_cell_reports_budget_and_subcategory():
    budgets = create_sample_budgets()
    changed_allocations = []
    page = BudgetPage(
        budgets,
        lambda: None,
        lambda name: None,
        lambda master_category_id, name: None,
        lambda budget, subcategory: changed_allocations.append((budget, subcategory)),
    )
    subcategory = budgets[0].master_categories[0].subcategories[0]
    row = page.rows.index(("Monthly Bills", subcategory.name)) + 2
    budgeted_input = page.table.cellWidget(row, 1)

    budgeted_input.setText("2000.00")
    budgeted_input.editingFinished.emit()

    assert changed_allocations == [(budgets[0], subcategory)]


def test_budget_input_for_hidden_subcategory_is_ignored():
    budgets = create_sample_budgets()
    changed_allocations = []
    page = BudgetPage(
        budgets,
        lambda: None,
        lambda name: None,
        lambda master_category_id, name: None,
        lambda budget, subcategory: changed_allocations.append((budget, subcategory)),
    )
    master_category = budgets[0].master_categories[0]
    subcategory = master_category.subcategories[0]
    row = page.rows.index((master_category.name, subcategory.name)) + 2
    budgeted_input = page.table.cellWidget(row, 1)

    budgeted_input.setText("2000.00")
    master_category.subcategories = []
    budgeted_input.editingFinished.emit()

    assert changed_allocations == []


def test_refresh_removes_stale_master_widget_from_new_subcategory_row():
    budgets = create_sample_budgets()
    page = BudgetPage(
        budgets,
        lambda: None,
        lambda name: None,
        lambda master_category_id, name: None,
    )

    for budget in budgets:
        budget.master_categories[0].subcategories.append(
            Subcategory("Other", Decimal("0.00"), Decimal("0.00"))
        )
    page.refresh()
    row = page.rows.index(("Monthly Bills", "Other")) + 2

    category_cell = page.table.cellWidget(row, 0)
    assert category_cell.objectName() == "subcategoryCell"
    assert (
        category_cell.findChild(QLabel, "subcategoryNameLabel").text()
        == "Other"
    )
