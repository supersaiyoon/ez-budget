def add_transaction(con, account_id, transaction_date, amount, cleared=False):
    row = con.execute(
        """
        INSERT INTO transactions (account_id, transaction_date, amount, cleared)
        VALUES (?, ?, ?, ?)
        RETURNING id, account_id, transaction_date, amount, cleared
        """,
        (account_id, transaction_date, amount, cleared),
    ).fetchone()
    con.commit()
    return row


def list_transactions(con, account_id):
    return con.execute(
        """
        SELECT id, account_id, transaction_date, amount, cleared
        FROM transactions
        WHERE account_id = ?
        ORDER BY transaction_date, id
        """,
        (account_id,),
    ).fetchall()
