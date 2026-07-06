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

    page = BudgetPage(budgets, on_budget_changed)

    for _ in range(10):
        page.month_scroller.next_button.click()
        app.processEvents()

    assert page.active_index == 10
    assert page.month_scroller.active_index == 10
    assert len(budgets) >= 13
    assert change_count > 0
