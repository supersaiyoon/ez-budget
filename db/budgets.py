def add_budget_month(con, month_date):
    # Month row anchors category allocations without duplicating income totals
    row = con.execute(
        """
        INSERT INTO budget_months (month_date)
        VALUES (?)
        RETURNING id, month_date
        """,
        (month_date,),
    ).fetchone()
    con.commit()
    return row


def get_budget_month_by_date(con, month_date):
    # Exact month-start date identifies one persisted planning period
    return con.execute(
        """
        SELECT id, month_date
        FROM budget_months
        WHERE month_date = ?
        """,
        (month_date,),
    ).fetchone()


def get_or_create_budget_month(con, month_date):
    # Startup can resolve one month row without duplicating lookup logic
    budget_month = get_budget_month_by_date(con, month_date)
    if budget_month is not None:
        return budget_month
    return add_budget_month(con, month_date)


def add_budget_allocation(
    con,
    budget_month_id,
    budget_category_id,
    amount,
):
    # Integer cents keep allocations exact across months
    row = con.execute(
        """
        INSERT INTO budget_allocations (
            budget_month_id,
            budget_category_id,
            amount
        )
        VALUES (?, ?, ?)
        RETURNING id, budget_month_id, budget_category_id, amount
        """,
        (budget_month_id, budget_category_id, amount),
    ).fetchone()
    con.commit()
    return row


def list_budget_allocations(con, budget_month_id):
    # Month scope keeps allocations separate across planning periods
    return con.execute(
        """
        SELECT id, budget_month_id, budget_category_id, amount
        FROM budget_allocations
        WHERE budget_month_id = ?
        ORDER BY id
        """,
        (budget_month_id,),
    ).fetchall()


def update_budget_allocation(
    con,
    budget_month_id,
    budget_category_id,
    amount,
):
    # Month and category pair identifies one existing allocation
    row = con.execute(
        """
        UPDATE budget_allocations
        SET amount = ?
        WHERE budget_month_id = ?
          AND budget_category_id = ?
        RETURNING id, budget_month_id, budget_category_id, amount
        """,
        (amount, budget_month_id, budget_category_id),
    ).fetchone()
    con.commit()
    return row


def set_budget_allocation(
    con,
    budget_month_id,
    budget_category_id,
    amount,
):
    # Existing row keeps stable identity across budget edits
    allocation = update_budget_allocation(
        con,
        budget_month_id,
        budget_category_id,
        amount,
    )
    if allocation is not None:
        return allocation
    return add_budget_allocation(
        con,
        budget_month_id,
        budget_category_id,
        amount,
    )


def list_monthly_totals(con, through_month):
    # Historical rows independent from Budget scroller state
    return con.execute(
        """
        SELECT
            budget_months.month_date,
            COALESCE((
                SELECT SUM(transactions.amount)
                FROM transactions
                JOIN accounts ON accounts.id = transactions.account_id
                WHERE transactions.income_month_date = budget_months.month_date
                  AND accounts.on_budget = TRUE
                  AND transactions.amount > 0
            ), 0) AS income,
            COALESCE((
                SELECT SUM(budget_allocations.amount)
                FROM budget_allocations
                WHERE budget_allocations.budget_month_id = budget_months.id
            ), 0) AS budgeted,
            COALESCE((
                SELECT -SUM(transactions.amount)
                FROM transactions
                JOIN accounts ON accounts.id = transactions.account_id
                JOIN budget_categories
                  ON budget_categories.id = transactions.budget_category_id
                WHERE transactions.transaction_date
                      BETWEEN budget_months.month_date
                          AND date(budget_months.month_date, '+1 month', '-1 day')
                  AND accounts.on_budget = TRUE
                  AND transactions.income_month_date IS NULL
                  AND transactions.amount < 0
            ), 0) AS spent
        FROM budget_months
        WHERE budget_months.month_date <= ?
        ORDER BY budget_months.month_date DESC
        """,
        (through_month,),
    ).fetchall()
