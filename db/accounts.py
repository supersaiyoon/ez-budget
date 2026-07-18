def create_account(con, name, on_budget=True):
    row = con.execute(
        """
        INSERT INTO accounts (name, on_budget)
        VALUES (?, ?)
        RETURNING id, name, on_budget, closed
        """,
        (name, on_budget),
    ).fetchone()
    con.commit()
    return row


def list_accounts(con):
    return con.execute(
        """
        SELECT id, name, on_budget, closed
        FROM accounts
        WHERE closed = FALSE
        ORDER BY id
        """
    ).fetchall()


def get_account_by_name(con, name):
    return con.execute(
        """
        SELECT id, name, on_budget, closed
        FROM accounts
        WHERE LOWER(name) = LOWER(?)
        ORDER BY id
        LIMIT 1
        """,
        (name,),
    ).fetchone()


def has_accounts(con):
    row = con.execute("SELECT COUNT(*) FROM accounts").fetchone()
    return row[0] > 0
