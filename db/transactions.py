def add_transaction(
    con,
    account_id,
    payee_id,
    budget_category_id,
    transaction_date,
    amount,
    notes=None,
    cleared=False,
    income_month_date=None,
):
    # Optional target month leaves ordinary spending inserts unchanged
    row = con.execute(
        """
        INSERT INTO transactions (
            account_id,
            payee_id,
            budget_category_id,
            income_month_date,
            transaction_date,
            amount,
            notes,
            cleared
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        RETURNING
            id,
            account_id,
            payee_id,
            budget_category_id,
            income_month_date,
            transaction_date,
            amount,
            notes,
            cleared
        """,
        (
            account_id,
            payee_id,
            budget_category_id,
            income_month_date,
            transaction_date,
            amount,
            notes,
            cleared,
        ),
    ).fetchone()
    con.commit()
    return row


def update_transaction(
    con,
    transaction_id,
    payee_id,
    budget_category_id,
    transaction_date,
    amount,
    notes=None,
    cleared=False,
    income_month_date=None,
):
    # Optional income target stays aligned with other editable values
    row = con.execute(
        """
        UPDATE transactions
        SET
            payee_id = ?,
            budget_category_id = ?,
            income_month_date = ?,
            transaction_date = ?,
            amount = ?,
            notes = ?,
            cleared = ?
        WHERE id = ?
        RETURNING
            id,
            account_id,
            payee_id,
            budget_category_id,
            income_month_date,
            transaction_date,
            amount,
            notes,
            cleared
        """,
        (
            payee_id,
            budget_category_id,
            income_month_date,
            transaction_date,
            amount,
            notes,
            cleared,
            transaction_id,
        ),
    ).fetchone()
    con.commit()
    return row


def delete_transaction(con, transaction_id):
    # Stable row ID limits deletion to one persisted transaction
    row = con.execute(
        """
        DELETE FROM transactions
        WHERE id = ?
        RETURNING id, account_id
        """,
        (transaction_id,),
    ).fetchone()
    con.commit()
    return row


def list_transactions(con, account_id):
    # Account rows retain category relationship and optional income assignment
    return con.execute(
        """
        SELECT
            transactions.id,
            transactions.account_id,
            transactions.budget_category_id,
            transactions.income_month_date,
            transactions.transaction_date,
            transactions.notes,
            transactions.amount,
            transactions.cleared,
            payees.name AS payee_name,
            budget_categories.name AS category_name
        FROM transactions
        JOIN payees ON payees.id = transactions.payee_id
        JOIN budget_categories
            ON budget_categories.id = transactions.budget_category_id
        WHERE transactions.account_id = ?
        ORDER BY transactions.transaction_date, transactions.id
        """,
        (account_id,),
    ).fetchall()


def list_category_transaction_totals(con, start_date, end_date):
    # Only Budget-account outgoing transactions count as category spending
    return con.execute(
        """
        SELECT
            transactions.budget_category_id,
            SUM(transactions.amount) AS total_amount
        FROM transactions
        JOIN accounts ON accounts.id = transactions.account_id
        JOIN budget_categories
          ON budget_categories.id = transactions.budget_category_id
        WHERE transactions.transaction_date BETWEEN ? AND ?
          AND accounts.on_budget = TRUE
          AND transactions.income_month_date IS NULL
          AND transactions.amount < 0
        GROUP BY transactions.budget_category_id
        ORDER BY transactions.budget_category_id
        """,
        (start_date, end_date),
    ).fetchall()


def get_monthly_income_total(con, income_month_date):
    # Assigned month separates budget timing from account transaction date
    row = con.execute(
        """
        SELECT COALESCE(SUM(transactions.amount), 0) AS total_income
        FROM transactions
        JOIN accounts ON accounts.id = transactions.account_id
        WHERE transactions.income_month_date = ?
          AND accounts.on_budget = TRUE
          AND transactions.amount > 0
        """,
        (income_month_date,),
    ).fetchone()
    return row["total_income"]


def has_transactions(con):
    row = con.execute("SELECT COUNT(*) FROM transactions").fetchone()
    return row[0] > 0
