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


def rename_master_category(con, master_category_id, name):
    # Case-insensitive guard keeps visible category headings unambiguous
    row = con.execute(
        """
        UPDATE master_budget_categories
        SET name = ?
        WHERE id = ?
          AND NOT EXISTS (
              SELECT 1
              FROM master_budget_categories AS existing_category
              WHERE LOWER(existing_category.name) = LOWER(?)
                AND existing_category.id != master_budget_categories.id
          )
        RETURNING id, name, hidden
        """,
        (name, master_category_id, name),
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


def list_transaction_categories(con):
    # Parent names distinguish same-named categories in transaction dropdowns
    return con.execute(
        """
        SELECT
            budget_categories.id,
            master_budget_categories.name AS master_category_name,
            budget_categories.name AS category_name
        FROM budget_categories
        JOIN master_budget_categories
            ON master_budget_categories.id = budget_categories.master_budget_category_id
        WHERE budget_categories.hidden = FALSE
          AND master_budget_categories.hidden = FALSE
        ORDER BY master_budget_categories.id, budget_categories.id
        """
    ).fetchall()


def get_budget_category_by_name(con, master_category_id, name):
    return con.execute(
        """
        SELECT id, master_budget_category_id, name, hidden
        FROM budget_categories
        WHERE master_budget_category_id = ?
          AND LOWER(name) = LOWER(?)
        ORDER BY id
        LIMIT 1
        """,
        (master_category_id, name),
    ).fetchone()


def rename_budget_category(con, budget_category_id, name):
    # Duplicate names blocked only among siblings under same master
    row = con.execute(
        """
        UPDATE budget_categories
        SET name = ?
        WHERE id = ?
          AND NOT EXISTS (
              SELECT 1
              FROM budget_categories AS existing_category
              WHERE existing_category.master_budget_category_id
                    = budget_categories.master_budget_category_id
                AND LOWER(existing_category.name) = LOWER(?)
                AND existing_category.id != budget_categories.id
          )
        RETURNING id, master_budget_category_id, name, hidden
        """,
        (name, budget_category_id, name),
    ).fetchone()
    con.commit()
    return row


def delete_budget_category(con, budget_category_id):
    # History check happens before allocation cleanup so refusal changes nothing
    transaction_row = con.execute(
        """
        SELECT 1
        FROM transactions
        WHERE budget_category_id = ?
        LIMIT 1
        """,
        (budget_category_id,),
    ).fetchone()
    if transaction_row is not None:
        return None

    con.execute(
        """
        DELETE FROM budget_allocations
        WHERE budget_category_id = ?
        """,
        (budget_category_id,),
    )
    deleted_row = con.execute(
        """
        DELETE FROM budget_categories
        WHERE id = ?
        RETURNING id, master_budget_category_id, name, hidden
        """,
        (budget_category_id,),
    ).fetchone()
    con.commit()
    return deleted_row


def get_or_create_income_category(con):
    # Reserved hidden parent avoids user-category name collisions
    master_category = get_master_category_by_name(con, "__System__")
    if master_category is None:
        master_category = add_master_category(con, "__System__", hidden=True)

    # Stable category ID keeps income on normal transaction rows
    income_category = get_budget_category_by_name(
        con,
        master_category["id"],
        "Income",
    )
    if income_category is not None:
        return income_category
    return add_budget_category(
        con,
        master_category["id"],
        "Income",
        hidden=True,
    )
