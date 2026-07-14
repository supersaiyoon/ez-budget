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
    return con.execute(
        """
        SELECT id, name
        FROM payees
        WHERE name = ?
        ORDER BY id
        LIMIT 1
        """,
        (name,),
    ).fetchone()
