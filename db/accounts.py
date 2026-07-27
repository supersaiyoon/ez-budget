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


def list_closed_accounts(con):
    return con.execute(
        """
        SELECT id, name, on_budget, closed
        FROM accounts
        WHERE closed = TRUE
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


def delete_account(con, account_id):
    # Transaction ownership blocks deletion so history cannot disappear silently
    row = con.execute(
        """
        DELETE FROM accounts
        WHERE id = ?
          AND NOT EXISTS (
              SELECT 1
              FROM transactions
              WHERE transactions.account_id = accounts.id
          )
        RETURNING id, name, on_budget, closed
        """,
        (account_id,),
    ).fetchone()
    con.commit()
    return row


def set_account_closed(con, account_id, closed):
    # Closed flag preserves account history while changing active navigation state
    row = con.execute(
        """
        UPDATE accounts
        SET closed = ?
        WHERE id = ?
        RETURNING id, name, on_budget, closed
        """,
        (closed, account_id),
    ).fetchone()
    con.commit()
    return row


def has_accounts(con):
    row = con.execute("SELECT COUNT(*) FROM accounts").fetchone()
    return row[0] > 0
