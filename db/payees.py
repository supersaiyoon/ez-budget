INCOME_PAYEE_NAME = "Not needed for income"


def add_payee(con, name):
    row = con.execute(
        """
        INSERT INTO payees (name)
        VALUES (?)
        RETURNING id, name
        """,
        (name,),
    ).fetchone()
    con.commit()
    return row


def list_payees(con):
    # User list hides automatic income placeholder
    return con.execute(
        """
        SELECT id, name
        FROM payees
        WHERE name != ?
        ORDER BY LOWER(name), id
        """,
        (INCOME_PAYEE_NAME,),
    ).fetchall()


def get_payee_by_name(con, name):
    # Typed capitalization should still reuse the same persistent payee
    return con.execute(
        """
        SELECT id, name
        FROM payees
        WHERE LOWER(name) = LOWER(?)
        ORDER BY id
        LIMIT 1
        """,
        (name,),
    ).fetchone()


def get_or_create_payee(con, name):
    # Transaction entry can resolve one payee row without duplicating lookup logic
    payee = get_payee_by_name(con, name)
    if payee is not None:
        return payee
    return add_payee(con, name)


def rename_payee(con, payee_id, name):
    if not name.strip():
        return None

    # Case-insensitive guard keeps one visible row per real-world payee
    row = con.execute(
        """
        UPDATE payees
        SET name = ?
        WHERE id = ?
          AND NOT EXISTS (
              SELECT 1
              FROM payees AS existing_payee
              WHERE LOWER(existing_payee.name) = LOWER(?)
                AND existing_payee.id != payees.id
          )
        RETURNING id, name
        """,
        (name.strip(), payee_id, name.strip()),
    ).fetchone()
    con.commit()
    return row


def count_transactions_for_payee(con, payee_id):
    # Deletion flow needs to know whether reassignment is required
    row = con.execute(
        """
        SELECT COUNT(*) AS transaction_count
        FROM transactions
        WHERE payee_id = ?
        """,
        (payee_id,),
    ).fetchone()
    return row["transaction_count"]


def delete_unused_payee(con, payee_id):
    # Used payees require reassignment so transactions keep a named payee
    row = con.execute(
        """
        DELETE FROM payees
        WHERE id = ?
          AND NOT EXISTS (
              SELECT 1
              FROM transactions
              WHERE transactions.payee_id = payees.id
          )
        RETURNING id, name
        """,
        (payee_id,),
    ).fetchone()
    con.commit()
    return row


def reassign_transactions_and_delete_payee(con, payee_id, replacement_name):
    if not replacement_name.strip():
        return None

    replacement_payee = get_or_create_payee(con, replacement_name.strip())
    if replacement_payee["id"] == payee_id:
        return None

    # Transaction reassignment happens before deleting the old payee row
    con.execute(
        """
        UPDATE transactions
        SET payee_id = ?
        WHERE payee_id = ?
        """,
        (replacement_payee["id"], payee_id),
    )
    deleted_payee = con.execute(
        """
        DELETE FROM payees
        WHERE id = ?
        RETURNING id, name
        """,
        (payee_id,),
    ).fetchone()
    con.commit()
    return deleted_payee
