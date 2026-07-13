def add_master_category(con, name, hidden=False):
    row = con.execute(
        """
        INSERT INTO master_budget_categories (name, hidden)
        VALUES (?, ?)
        RETURNING id, name, hidden
        """,
        (name, hidden),
    ).fetchone()
    con.commit()
    return row


def add_budget_category(con, master_category_id, name, hidden=False):
    row = con.execute(
        """
        INSERT INTO budget_categories (master_budget_category_id, name, hidden)
        VALUES (?, ?, ?)
        RETURNING id, master_budget_category_id, name, hidden
        """,
        (master_category_id, name, hidden),
    ).fetchone()
    con.commit()
    return row
