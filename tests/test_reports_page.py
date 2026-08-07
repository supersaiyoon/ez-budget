from datetime import date
from decimal import Decimal

import pytest

from budget_model import Account, Budget, MasterCategory, Subcategory, Transaction
from ui.reports_page import (
    ReportsPage,
    cash_flow_by_month,
    net_worth_by_month,
    transaction_frame,
)


# Every test in this module creates Qt widgets and requires shared application
pytestmark = pytest.mark.usefixtures("qapp")


def report_transaction(transaction_date, payee, outgoing="0", incoming="0"):
    return Transaction(
        transaction_date,
        payee,
        "Category",
        "",
        outgoing=Decimal(outgoing),
        incoming=Decimal(incoming),
    )


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

    assert page.description.text() == (
        "Net worth, cash flow, and monthly budget totals"
    )
    assert len(page.net_worth_figure.axes) == 1
    assert len(page.cash_flow_figure.axes) == 1
    assert page.table.item(0, 0).text() == "July 2026"
    assert page.table.item(0, 1).text() == "$3,000.00"
    assert page.table.item(0, 2).text() == "$1,850.00"
    assert page.table.item(0, 3).text() == "$1,200.00"
    assert page.table.item(0, 4).text() == "$650.00"


def test_report_data_tracks_net_worth_and_cash_flow_rules():
    active_account = Account(
        "Checking",
        transactions=[
            report_transaction("2025-01-15", "Opening Balance", incoming="1000"),
            report_transaction("2025-10-02", "Employer", incoming="100"),
            report_transaction("2025-11-03", "Store", outgoing="200"),
            report_transaction("2026-07-01", "Opening Balance", incoming="400"),
            report_transaction("2026-07-05", "Employer", incoming="300"),
            report_transaction("2026-07-06", "Store", outgoing="50"),
        ],
    )
    off_budget_account = Account(
        "Savings",
        transactions=[
            report_transaction("2026-06-10", "Interest", incoming="500")
        ],
        on_budget=False,
    )
    closed_account = Account(
        "Old Checking",
        transactions=[
            report_transaction("2026-07-07", "Employer", incoming="999")
        ],
        closed=True,
    )
    through_date = date(2026, 7, 15)

    frame = transaction_frame(
        [active_account, off_budget_account, closed_account],
        through_date,
    )
    net_worth = net_worth_by_month(frame, through_date)
    cash_flow = cash_flow_by_month(frame, net_worth.index[-1])

    assert len(net_worth) == 12
    assert net_worth.index[0].strftime("%Y-%m") == "2025-08"
    assert net_worth.loc["2025-10"] == 1100
    assert net_worth.loc["2025-11"] == 900
    assert net_worth.loc["2026-06"] == 1400
    assert net_worth.loc["2026-07"] == 2050
    assert [month.strftime("%Y-%m") for month in cash_flow.index] == [
        "2026-05",
        "2026-06",
        "2026-07",
    ]
    assert cash_flow.loc["2026-06", "Incoming"] == 500
    assert cash_flow.loc["2026-07", "Incoming"] == 300
    assert cash_flow.loc["2026-07", "Expenses"] == 50


def test_cash_flow_navigation_uses_saved_month_boundaries():
    account = Account(
        "Checking",
        transactions=[
            report_transaction("2026-05-10", "Employer", incoming="100"),
            report_transaction("2026-07-10", "Store", outgoing="25"),
        ],
    )
    page = ReportsPage([], [account], current_date=date(2026, 7, 15))

    assert page.cash_flow_month_label.text() == "May 2026 - Jul 2026"
    assert page.next_month_button.isEnabled() is False
    assert page.previous_month_button.isEnabled() is True

    page.shift_cash_flow_month(-1)
    page.refresh()

    assert page.cash_flow_month_label.text() == "Apr 2026 - Jun 2026"
    assert page.selected_cash_flow_month.strftime("%Y-%m") == "2026-06"

    page.shift_cash_flow_month(-1)

    assert page.cash_flow_month_label.text() == "Mar 2026 - May 2026"
    assert page.previous_month_button.isEnabled() is False
