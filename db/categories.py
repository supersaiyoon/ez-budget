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
