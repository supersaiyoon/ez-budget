def add_transaction(
    con,
    account_id,
    payee_id,
    budget_category_id,
    transaction_date,
    amount,
    notes=None,
    cleared=False,
):
    row = con.execute(
        """
        INSERT INTO transactions (
            account_id,
            payee_id,
            budget_category_id,
            transaction_date,
            amount,
            notes,
            cleared
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        RETURNING
            id,
            account_id,
            payee_id,
            budget_category_id,
            transaction_date,
            amount,
            notes,
            cleared
        """,
        (
            account_id,
            payee_id,
            budget_category_id,
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
):
    # Full row update keeps persisted transaction aligned with edited model
    row = con.execute(
        """
        UPDATE transactions
        SET
            payee_id = ?,
            budget_category_id = ?,
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
            transaction_date,
            amount,
            notes,
            cleared
        """,
        (
            payee_id,
            budget_category_id,
            transaction_date,
            amount,
            notes,
            cleared,
            transaction_id,
        ),
    ).fetchone()
    con.commit()
    return row


def list_transactions(con, account_id):
    return con.execute(
        """
        SELECT
            transactions.id,
            transactions.account_id,
            transactions.budget_category_id,
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


def list_category_transaction_totals(con):
    # Signed totals preserve outgoing and incoming database direction
    return con.execute(
        """
        SELECT
            budget_category_id,
            SUM(amount) AS total_amount
        FROM transactions
        GROUP BY budget_category_id
        ORDER BY budget_category_id
        """
    ).fetchall()


def has_transactions(con):
    row = con.execute("SELECT COUNT(*) FROM transactions").fetchone()
    return row[0] > 0
