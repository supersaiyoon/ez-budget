import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from budget_model import create_sample_budgets
from ui.budget_page import BudgetPage


def test_next_month_arrow_can_generate_future_months():
    app = QApplication.instance() or QApplication([])
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
        app.processEvents()

    assert page.active_index == 10
    assert page.month_scroller.active_index == 10
    assert len(budgets) >= 13
    assert change_count > 0


def test_master_category_name_is_sent_to_callback():
    _app = QApplication.instance() or QApplication([])
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
    _app = QApplication.instance() or QApplication([])

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
    _app = QApplication.instance() or QApplication([])
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
