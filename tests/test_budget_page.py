from decimal import Decimal

import pytest

from PyQt6.QtWidgets import QPushButton

from budget_model import Subcategory, create_sample_budgets, format_money
from ui.budget_page import BudgetPage


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


def test_master_category_name_is_sent_to_callback():
    added_names = []
    page = BudgetPage(
        create_sample_budgets(),
        lambda: None,
        added_names.append,
        lambda master_category_id, name: None,
    )

    page.submit_master_category_name(" Savings ")

    assert page.add_master_category_button.text() == "+"
    assert added_names == ["Savings"]


def test_master_category_error_is_shown_in_status():
    def reject_duplicate(name):
        raise ValueError("Master category already exists.")

    page = BudgetPage(
        create_sample_budgets(),
        lambda: None,
        reject_duplicate,
        lambda master_category_id, name: None,
    )

    page.submit_master_category_name("Savings")

    assert page.status.text() == "Master category already exists."


def test_subcategory_error_is_shown_in_status():
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
    assert page.status.text() == "Subcategory already exists in this master category."


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

    assert add_button.text() == "+"
    assert add_button.isEnabled() == True


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
    assert page.table.item(master_row, 2).text() == format_money(-master_category.spent)
    assert page.table.item(subcategory_row, 2).text() == format_money(-subcategory.spent)


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

    assert page.table.cellWidget(row, 0) is None
    assert page.table.item(row, 0).text().strip() == "Other"
