def add_budget_month(con, month_date, monthly_income=0):
    # Integer cents keep persisted income aligned with transaction storage
    row = con.execute(
        """
        INSERT INTO budget_months (month_date, monthly_income)
        VALUES (?, ?)
        RETURNING id, month_date, monthly_income
        """,
        (month_date, monthly_income),
    ).fetchone()
    con.commit()
    return row


def get_budget_month_by_date(con, month_date):
    # Exact month-start date identifies one persisted planning period
    return con.execute(
        """
        SELECT id, month_date, monthly_income
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
