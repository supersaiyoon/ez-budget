from datetime import date

import pandas as pd
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from budget_model import format_month_name, money_from_cents, money_to_cents
from ui.helpers import money_item


REPORT_MONTH_COUNT = 12
CASH_FLOW_MONTH_COUNT = 3
OPENING_BALANCE_PAYEE = "Opening Balance"
NET_WORTH_COLOR = "#55b89b"
INCOMING_COLOR = "#74c69d"
EXPENSE_COLOR = "#ef9a9a"
CARD_BACKGROUND = "#ffffff"
TEXT_COLOR = "#26323f"
MUTED_TEXT_COLOR = "#66788a"
GRID_COLOR = "#d8dee6"


def transaction_frame(accounts, through_date):
    rows = []
    for account in accounts:
        if account.closed:
            continue
        for transaction in account.transactions:
            try:
                transaction_date = pd.Timestamp(transaction.date)
            except (TypeError, ValueError):
                continue
            if transaction_date.date() > through_date:
                continue
            amount = transaction.incoming - transaction.outgoing
            rows.append(
                {
                    "transaction_date": transaction_date,
                    "month": transaction_date.to_period("M"),
                    "amount_cents": money_to_cents(amount),
                    "payee": transaction.payee,
                }
            )

    return pd.DataFrame(
        rows,
        columns=["transaction_date", "month", "amount_cents", "payee"],
    )


def net_worth_by_month(frame, through_date):
    current_month = pd.Period(through_date, freq="M")
    months = pd.period_range(
        end=current_month,
        periods=REPORT_MONTH_COUNT,
        freq="M",
    )
    if frame.empty:
        return pd.Series(0.0, index=months, name="net_worth")

    monthly_change = frame.groupby("month")["amount_cents"].sum()
    balance_before_range = monthly_change[monthly_change.index < months[0]].sum()
    visible_change = monthly_change.reindex(months, fill_value=0)
    return (balance_before_range + visible_change.cumsum()) / 100


def cash_flow_by_month(frame, ending_month):
    months = pd.period_range(
        end=ending_month,
        periods=CASH_FLOW_MONTH_COUNT,
        freq="M",
    )
    if frame.empty:
        return pd.DataFrame(0.0, index=months, columns=["Incoming", "Expenses"])

    activity = frame[frame["payee"] != OPENING_BALANCE_PAYEE]
    incoming = (
        activity[activity["amount_cents"] > 0]
        .groupby("month")["amount_cents"]
        .sum()
        .reindex(months, fill_value=0)
        / 100
    )
    expenses = (
        -activity[activity["amount_cents"] < 0]
        .groupby("month")["amount_cents"]
        .sum()
        .reindex(months, fill_value=0)
        / 100
    )
    return pd.DataFrame({"Incoming": incoming, "Expenses": expenses})


def currency_tick(value, _position=None):
    sign = "-" if value < 0 else ""
    return f"{sign}${abs(value):,.0f}"


class ReportsPage(QWidget):
    def __init__(
        self,
        budgets,
        accounts=None,
        current_date=None,
        monthly_totals_provider=None,
    ):
        super().__init__()
        # Fallback rows for standalone Reports views
        self.budgets = budgets
        self.accounts = accounts if accounts is not None else []
        self.current_date = current_date or date.today()
        self.current_month = pd.Period(self.current_date, freq="M")
        self.monthly_totals_provider = monthly_totals_provider
        self.selected_cash_flow_month = self.current_month
        self.earliest_cash_flow_month = self.current_month

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        title = QLabel("Reports")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        self.description = QLabel("Net worth, cash flow, and monthly budget totals")
        self.description.setObjectName("statusText")
        layout.addWidget(self.description)

        chart_layout = QHBoxLayout()
        chart_layout.setSpacing(14)

        net_worth_card = QFrame()
        net_worth_card.setObjectName("reportCard")
        net_worth_layout = QVBoxLayout(net_worth_card)
        net_worth_title = QLabel("Net Worth")
        net_worth_title.setObjectName("reportCardTitle")
        net_worth_layout.addWidget(net_worth_title)
        self.net_worth_figure = Figure(figsize=(5, 2.6), tight_layout=True)
        self.net_worth_canvas = FigureCanvasQTAgg(self.net_worth_figure)
        self.net_worth_canvas.setMinimumHeight(230)
        net_worth_layout.addWidget(self.net_worth_canvas)
        chart_layout.addWidget(net_worth_card, 1)

        cash_flow_card = QFrame()
        cash_flow_card.setObjectName("reportCard")
        cash_flow_layout = QVBoxLayout(cash_flow_card)
        cash_flow_header = QHBoxLayout()
        cash_flow_title = QLabel("Cash Flow")
        cash_flow_title.setObjectName("reportCardTitle")
        cash_flow_header.addWidget(cash_flow_title)
        cash_flow_header.addStretch()
        self.previous_month_button = QPushButton("<")
        self.previous_month_button.setObjectName("reportMonthArrow")
        self.previous_month_button.setToolTip("Previous month")
        self.previous_month_button.clicked.connect(
            lambda: self.shift_cash_flow_month(-1)
        )
        cash_flow_header.addWidget(self.previous_month_button)
        self.cash_flow_month_label = QLabel()
        self.cash_flow_month_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cash_flow_month_label.setMinimumWidth(180)
        cash_flow_header.addWidget(self.cash_flow_month_label)
        self.next_month_button = QPushButton(">")
        self.next_month_button.setObjectName("reportMonthArrow")
        self.next_month_button.setToolTip("Next month")
        self.next_month_button.clicked.connect(
            lambda: self.shift_cash_flow_month(1)
        )
        cash_flow_header.addWidget(self.next_month_button)
        cash_flow_layout.addLayout(cash_flow_header)
        self.cash_flow_figure = Figure(figsize=(5, 2.6), tight_layout=True)
        self.cash_flow_canvas = FigureCanvasQTAgg(self.cash_flow_figure)
        self.cash_flow_canvas.setMinimumHeight(230)
        cash_flow_layout.addWidget(self.cash_flow_canvas)
        chart_layout.addWidget(cash_flow_card, 1)

        layout.addLayout(chart_layout)

        # Read-only table fits month-by-month totals better than editable controls
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Month", "Income", "Budgeted", "Spent", "Remaining"])
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setMinimumHeight(190)
        layout.addWidget(self.table, 1)

        self.refresh()

    def refresh(self):
        self.transaction_data = transaction_frame(
            self.accounts,
            self.current_date,
        )
        self.update_cash_flow_bounds()
        self.draw_net_worth_chart()
        self.draw_cash_flow_chart()

        self.refresh_monthly_totals_table()

    def refresh_monthly_totals_table(self):
        if self.monthly_totals_provider is None:
            rows = [
                (
                    budget.month_name,
                    budget.monthly_income,
                    budget.total_budgeted,
                    budget.total_spent,
                    budget.total_remaining,
                )
                for budget in self.budgets
            ]
        else:
            rows = []
            for total in self.monthly_totals_provider():
                budgeted = money_from_cents(total["budgeted"])
                spent = money_from_cents(total["spent"])
                rows.append(
                    (
                        format_month_name(
                            date.fromisoformat(total["month_date"])
                        ),
                        money_from_cents(total["income"]),
                        budgeted,
                        spent,
                        budgeted - spent,
                    )
                )

        self.table.setRowCount(len(rows))
        for row, values in enumerate(rows):
            self.table.setItem(row, 0, QTableWidgetItem(values[0]))
            for column, amount in enumerate(values[1:], start=1):
                self.table.setItem(row, column, money_item(amount))

    def update_cash_flow_bounds(self):
        if self.transaction_data.empty:
            self.earliest_cash_flow_month = self.current_month
        else:
            self.earliest_cash_flow_month = self.transaction_data["month"].min()
        if self.selected_cash_flow_month < self.earliest_cash_flow_month:
            self.selected_cash_flow_month = self.earliest_cash_flow_month
        if self.selected_cash_flow_month > self.current_month:
            self.selected_cash_flow_month = self.current_month
        self.update_cash_flow_controls()

    def update_cash_flow_controls(self):
        first_month = self.selected_cash_flow_month - (CASH_FLOW_MONTH_COUNT - 1)
        self.cash_flow_month_label.setText(
            f'{first_month.strftime("%b %Y")} - '
            f'{self.selected_cash_flow_month.strftime("%b %Y")}'
        )
        self.previous_month_button.setEnabled(
            self.selected_cash_flow_month > self.earliest_cash_flow_month
        )
        self.next_month_button.setEnabled(
            self.selected_cash_flow_month < self.current_month
        )

    def shift_cash_flow_month(self, direction):
        candidate = self.selected_cash_flow_month + direction
        if candidate < self.earliest_cash_flow_month or candidate > self.current_month:
            return
        self.selected_cash_flow_month = candidate
        self.update_cash_flow_controls()
        self.draw_cash_flow_chart()

    def prepare_axes(self, figure):
        figure.clear()
        figure.set_facecolor(CARD_BACKGROUND)
        axes = figure.add_subplot(111)
        axes.set_facecolor(CARD_BACKGROUND)
        axes.tick_params(colors=MUTED_TEXT_COLOR, labelsize=8)
        for spine in axes.spines.values():
            spine.set_visible(False)
        return axes

    def draw_empty_chart(self, figure, canvas, message):
        axes = self.prepare_axes(figure)
        axes.text(
            0.5,
            0.5,
            message,
            ha="center",
            va="center",
            color=MUTED_TEXT_COLOR,
            transform=axes.transAxes,
        )
        axes.set_axis_off()
        canvas.draw_idle()

    def draw_net_worth_chart(self):
        if self.transaction_data.empty:
            self.draw_empty_chart(
                self.net_worth_figure,
                self.net_worth_canvas,
                "Add transactions to see net worth.",
            )
            return

        net_worth = net_worth_by_month(
            self.transaction_data,
            self.current_date,
        )
        axes = self.prepare_axes(self.net_worth_figure)
        positions = list(range(len(net_worth)))
        values = net_worth.astype(float).to_numpy()
        labels = [month.strftime("%b") for month in net_worth.index]
        axes.plot(positions, values, color=NET_WORTH_COLOR, linewidth=2)
        axes.margins(y=0.14)
        lower_bound, upper_bound = axes.get_ylim()
        axes.fill_between(
            positions,
            values,
            lower_bound,
            color=NET_WORTH_COLOR,
            alpha=0.16,
        )
        if lower_bound <= 0 <= upper_bound:
            axes.axhline(0, color=GRID_COLOR, linewidth=0.8)
        axes.grid(axis="y", color=GRID_COLOR, linewidth=0.6, alpha=0.8)
        axes.set_xticks(positions)
        axes.set_xticklabels(labels)
        axes.yaxis.set_major_formatter(FuncFormatter(currency_tick))
        axes.set_xlim(positions[0], positions[-1])
        self.net_worth_canvas.draw_idle()

    def draw_cash_flow_chart(self):
        cash_flow = cash_flow_by_month(
            self.transaction_data,
            self.selected_cash_flow_month,
        )
        if cash_flow.to_numpy().sum() == 0:
            self.draw_empty_chart(
                self.cash_flow_figure,
                self.cash_flow_canvas,
                "No cash flow for these months.",
            )
            return

        axes = self.prepare_axes(self.cash_flow_figure)
        plot_data = cash_flow.astype(float).copy()
        plot_data.index = [month.strftime("%b") for month in plot_data.index]
        plot_data.plot.bar(
            ax=axes,
            color=[INCOMING_COLOR, EXPENSE_COLOR],
            width=0.6,
            rot=0,
        )
        axes.margins(y=0.18)
        axes.grid(axis="y", color=GRID_COLOR, linewidth=0.6, alpha=0.8)
        axes.yaxis.set_major_formatter(FuncFormatter(currency_tick))
        axes.legend(frameon=False, fontsize=8)
        for container in axes.containers:
            for bar in container:
                value = bar.get_height()
                if value == 0:
                    continue
                axes.annotate(
                    f"${value:,.2f}",
                    (bar.get_x() + bar.get_width() / 2, value),
                    xytext=(0, 5),
                    textcoords="offset points",
                    ha="center",
                    va="bottom",
                    color=TEXT_COLOR,
                    fontsize=7,
                )
        self.cash_flow_canvas.draw_idle()
