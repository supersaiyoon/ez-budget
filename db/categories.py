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


def list_master_categories(con):
    return con.execute(
        """
        SELECT id, name, hidden
        FROM master_budget_categories
        WHERE hidden = FALSE
        ORDER BY id
        """
    ).fetchall()


def get_master_category_by_name(con, name):
    return con.execute(
        """
        SELECT id, name, hidden
        FROM master_budget_categories
        WHERE LOWER(name) = LOWER(?)
        ORDER BY id
        LIMIT 1
        """,
        (name,),
    ).fetchone()


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


def list_budget_categories(con, master_category_id):
    return con.execute(
        """
        SELECT id, master_budget_category_id, name, hidden
        FROM budget_categories
        WHERE master_budget_category_id = ?
          AND hidden = FALSE
        ORDER BY id
        """,
        (master_category_id,),
    ).fetchall()


def get_budget_category_by_name(con, master_category_id, name):
    return con.execute(
        """
        SELECT id, master_budget_category_id, name, hidden
        FROM budget_categories
        WHERE master_budget_category_id = ?
          AND name = ?
        ORDER BY id
        LIMIT 1
        """,
        (master_category_id, name),
    ).fetchone()
