def add_transaction(
    con,
    account_id,
    payee_id,
    budget_category_id,
    transaction_date,
    amount,
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
            cleared
        )
        VALUES (?, ?, ?, ?, ?, ?)
        RETURNING
            id,
            account_id,
            payee_id,
            budget_category_id,
            transaction_date,
            amount,
            cleared
        """,
        (
            account_id,
            payee_id,
            budget_category_id,
            transaction_date,
            amount,
            cleared,
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
            transactions.transaction_date,
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
