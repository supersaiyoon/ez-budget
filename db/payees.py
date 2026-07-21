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
