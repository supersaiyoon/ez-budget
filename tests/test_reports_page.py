from datetime import date
from decimal import Decimal

import pytest

from budget_model import Budget, MasterCategory, Subcategory
from ui.reports_page import ReportsPage


# Every test in this module creates Qt widgets and requires shared application
pytestmark = pytest.mark.usefixtures("qapp")


def test_reports_page_displays_monthly_budget_totals():
    budget = Budget(
        date(2026, 7, 1),
        "July 2026",
        Decimal("3000.00"),
        [
            MasterCategory(
                "Monthly Bills",
                [
                    Subcategory(
                        "Rent",
                        Decimal("1850.00"),
                        Decimal("1200.00"),
                    )
                ],
            )
        ],
    )

    page = ReportsPage([budget])

    assert page.description.text() == "Monthly budget totals"
    assert page.table.item(0, 0).text() == "July 2026"
    assert page.table.item(0, 1).text() == "$3,000.00"
    assert page.table.item(0, 2).text() == "$1,850.00"
    assert page.table.item(0, 3).text() == "$1,200.00"
    assert page.table.item(0, 4).text() == "$650.00"
