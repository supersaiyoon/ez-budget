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
