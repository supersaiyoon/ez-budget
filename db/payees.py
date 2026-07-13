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
