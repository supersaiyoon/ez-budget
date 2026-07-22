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
