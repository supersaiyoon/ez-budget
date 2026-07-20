from decimal import Decimal, InvalidOperation
from dataclasses import dataclass, field
from datetime import date


@dataclass
class Subcategory:
    # Smallest budget bucket so adjustments have one clear target
    name: str
    budgeted: Decimal
    spent: Decimal
    # SQLite row identity kept for future edits
    database_id: int | None = None

    @property
    def remaining(self):
        # Negative values allowed so overspending stays visible
        return self.budgeted - self.spent


@dataclass
class MasterCategory:
    name: str
    # Default factory keeps categories from sharing one mutable list
    subcategories: list = field(default_factory=list)
    # SQLite row identity kept when model reaches UI
    database_id: int | None = None

    @property
    def budgeted(self):
        # Decimal zero seed keeps empty categories and money math predictable
        return sum((item.budgeted for item in self.subcategories), Decimal("0.00"))

    @property
    def spent(self):
        # Rollup calculated live so subcategory edits need no sync step
        return sum((item.spent for item in self.subcategories), Decimal("0.00"))

    @property
    def remaining(self):
        return self.budgeted - self.spent


@dataclass
class Budget:
    # Stored date supports month math without parsing the display label
    month_date: date
    month_name: str
    monthly_income: Decimal
    master_categories: list

    @property
    def total_budgeted(self):
        # Derived total avoids stale budget summaries after edits
        return sum((category.budgeted for category in self.master_categories), Decimal("0.00"))

    @property
    def total_spent(self):
        return sum((category.spent for category in self.master_categories), Decimal("0.00"))

    @property
    def available_to_budget(self):
        # Budgeting pool shrinks as dollars get assigned
        return self.monthly_income - self.total_budgeted

    @property
    def total_remaining(self):
        return self.total_budgeted - self.total_spent

    def apply_adjustment(self, master_name, subcategory_name, raw_value):
        # Raw text parsed here so UI and tests share one validation rule
        amount = parse_money(raw_value)
        subcategory = self.get_subcategory(master_name, subcategory_name)
        subcategory.budgeted += amount
        return amount

    def get_subcategory(self, master_name, subcategory_name):
        # Names are enough for sample data before persistent IDs exist
        for category in self.master_categories:
            if category.name != master_name:
                continue
            for subcategory in category.subcategories:
                if subcategory.name == subcategory_name:
                    return subcategory
        raise KeyError(f"Unknown category: {master_name} / {subcategory_name}")


@dataclass
class Transaction:
    date: str
    payee: str
    category: str
    notes: str
    outgoing: Decimal = Decimal("0.00")
    incoming: Decimal = Decimal("0.00")
    cleared: bool = False
    # SQLite row identity for future transaction updates
    database_id: int | None = None


def transaction_amount_in_cents(transaction):
    # Outgoing and incoming are mutually exclusive so one is always zero
    if transaction.outgoing != 0:
        cents = transaction.outgoing * 100
        return -int(cents)

    cents = transaction.incoming * 100
    return int(cents)


def transaction_amounts_from_cents(amount_in_cents):
    amount = Decimal(abs(amount_in_cents)) / Decimal("100")
    if amount_in_cents < 0:
        return amount, Decimal("0.00")
    if amount_in_cents > 0:
        return Decimal("0.00"), amount
    return Decimal("0.00"), Decimal("0.00")


def transaction_from_database_row(transaction_row):
    outgoing, incoming = transaction_amounts_from_cents(transaction_row["amount"])
    return Transaction(
        date=transaction_row["transaction_date"],
        payee=transaction_row["payee_name"],
        category=transaction_row["category_name"],
        notes=transaction_row["notes"] or "",
        outgoing=outgoing,
        incoming=incoming,
        cleared=bool(transaction_row["cleared"]),
        database_id=transaction_row["id"],
    )


@dataclass
class Account:
    name: str
    # Each account owns its own transaction list
    transactions: list = field(default_factory=list)
    # SQLite row identity for account UI and transactions
    database_id: int | None = None
    # Navigation group stored with account
    on_budget: bool = True
    closed: bool = False

    @property
    def cleared_balance(self):
        # Cleared total mirrors reconciled bank activity
        return sum(
            (transaction.incoming - transaction.outgoing for transaction in self.transactions if transaction.cleared),
            Decimal("0.00"),
        )

    @property
    def working_balance(self):
        # Working total includes pending activity for day-to-day cash view
        return sum(
            (transaction.incoming - transaction.outgoing for transaction in self.transactions),
            Decimal("0.00"),
        )


def parse_money(raw_value):
    # User-friendly formatting accepted before Decimal sees the value
    normalized = raw_value.strip().replace("$", "").replace(",", "")
    if not normalized:
        raise ValueError("Enter an amount.")

    try:
        amount = Decimal(normalized)
    except InvalidOperation as exc:
        # ValueError keeps UI handling simple and domain-focused
        raise ValueError("Use a valid number.") from exc

    # Cents precision everywhere so totals compare cleanly
    return amount.quantize(Decimal("0.01"))


def format_money(amount):
    # Manual sign handling keeps negative amounts as -$1.00
    sign = "-" if amount < 0 else ""
    absolute = abs(amount)
    return f"{sign}${absolute:,.2f}"


def create_empty_budget():
    month_date = date.today().replace(day=1)
    return Budget(
        month_date=month_date,
        month_name=format_month_name(month_date),
        monthly_income=Decimal("0.00"),
        master_categories=[],
    )


def create_sample_budget():
    # Middle sample month kept explicit as the baseline for tests and UI demos
    return Budget(
        month_date=date(2026, 5, 1),
        month_name="May 2026",
        monthly_income=Decimal("5200.00"),
        master_categories=[
            MasterCategory(
                "Monthly Bills",
                [
                    Subcategory("Mortgage", Decimal("1850.00"), Decimal("1850.00")),
                    Subcategory("Water", Decimal("95.00"), Decimal("72.35")),
                    Subcategory("Electricity", Decimal("175.00"), Decimal("126.40")),
                    Subcategory("Internet", Decimal("90.00"), Decimal("90.00")),
                ],
            ),
            MasterCategory(
                "Everyday Spending",
                [
                    Subcategory("Groceries", Decimal("650.00"), Decimal("418.22")),
                    Subcategory("Gas", Decimal("240.00"), Decimal("163.44")),
                    Subcategory("Dining Out", Decimal("250.00"), Decimal("198.18")),
                ],
            ),
            MasterCategory(
                "Savings",
                [
                    Subcategory("Emergency Fund", Decimal("500.00"), Decimal("0.00")),
                    Subcategory("Vacation", Decimal("225.00"), Decimal("0.00")),
                ],
            ),
        ],
    )


def create_month_budget(month_date, monthly_income, bill_offset=Decimal("0.00"), spending_offset=Decimal("0.00")):
    # Offsets create realistic month-to-month variation without duplicating fixtures
    return Budget(
        month_date=month_date,
        month_name=format_month_name(month_date),
        monthly_income=Decimal(monthly_income),
        master_categories=[
            MasterCategory(
                "Monthly Bills",
                [
                    Subcategory("Mortgage", Decimal("1850.00"), Decimal("1850.00")),
                    Subcategory("Water", Decimal("95.00") + bill_offset, Decimal("72.35") + bill_offset),
                    Subcategory("Electricity", Decimal("175.00") + bill_offset, Decimal("126.40") + bill_offset),
                    Subcategory("Internet", Decimal("90.00"), Decimal("90.00")),
                ],
            ),
            MasterCategory(
                "Everyday Spending",
                [
                    Subcategory("Groceries", Decimal("650.00") + spending_offset, Decimal("418.22") + spending_offset),
                    Subcategory("Gas", Decimal("240.00"), Decimal("163.44")),
                    Subcategory("Dining Out", Decimal("250.00"), Decimal("198.18")),
                ],
            ),
            MasterCategory(
                "Savings",
                [
                    Subcategory("Emergency Fund", Decimal("500.00"), Decimal("0.00")),
                    Subcategory("Vacation", Decimal("225.00"), Decimal("0.00")),
                ],
            ),
        ],
    )


def create_sample_budgets():
    # Multiple months included so scroller, reports, and comparisons have real context
    return [
        create_month_budget(date(2026, 3, 1), "5100.00", Decimal("-10.00"), Decimal("-35.00")),
        create_month_budget(date(2026, 4, 1), "5150.00", Decimal("-5.00"), Decimal("-20.00")),
        create_sample_budget(),
        create_month_budget(date(2026, 6, 1), "5300.00", Decimal("15.00"), Decimal("25.00")),
        create_month_budget(date(2026, 7, 1), "5300.00", Decimal("20.00"), Decimal("40.00")),
        create_month_budget(date(2026, 8, 1), "5400.00", Decimal("25.00"), Decimal("50.00")),
    ]


def create_sample_accounts():
    # Account fixtures mirror the two transaction pages in the main window
    return [
        Account(
            "Checking",
            [
                Transaction(
                    "2026-05-01",
                    "CSUMB Payroll",
                    "Income",
                    "May paycheck",
                    Decimal("0.00"),
                    Decimal("2600.00"),
                    True,
                ),
                Transaction(
                    "2026-05-03",
                    "Central Mortgage",
                    "Mortgage",
                    "Monthly payment",
                    Decimal("1850.00"),
                    Decimal("0.00"),
                    True,
                ),
                Transaction(
                    "2026-05-06",
                    "Grocery Market",
                    "Groceries",
                    "",
                    Decimal("142.38"),
                    Decimal("0.00"),
                    False,
                ),
            ],
        ),
        Account(
            "Credit Card",
            [
                Transaction(
                    "2026-05-04",
                    "Fuel Stop",
                    "Gas",
                    "",
                    Decimal("58.40"),
                    Decimal("0.00"),
                    True,
                ),
                Transaction(
                    "2026-05-05",
                    "Cafe Verde",
                    "Dining Out",
                    "Lunch",
                    Decimal("18.22"),
                    Decimal("0.00"),
                    False,
                ),
                Transaction(
                    "2026-05-07",
                    "Online Return",
                    "Clothing",
                    "Refund",
                    Decimal("0.00"),
                    Decimal("34.99"),
                    False,
                ),
            ],
        ),
    ]


def create_next_month_budget(previous_budget):
    # Next month inherits structure while leaving new dollars unassigned
    month_date = next_month(previous_budget.month_date)
    return Budget(
        month_date=month_date,
        month_name=format_month_name(month_date),
        monthly_income=previous_budget.monthly_income,
        master_categories=[
            MasterCategory(
                category.name,
                [
                    Subcategory(
                        subcategory.name,
                        Decimal("0.00"),
                        Decimal("0.00"),
                        database_id=subcategory.database_id,
                    )
                    for subcategory in category.subcategories
                ],
                database_id=category.database_id,
            )
            for category in previous_budget.master_categories
        ],
    )


def next_month(month_date):
    # December rollover handled directly so generated budgets stay calendar-valid
    if month_date.month == 12:
        return date(month_date.year + 1, 1, 1)
    return date(month_date.year, month_date.month + 1, 1)


def format_month_name(month_date):
    # Display label generated from date so stored month values stay consistent
    return month_date.strftime("%B %Y")
