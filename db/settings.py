def get_setting(con, key, default=None):
    # Missing preference returns caller-provided first-run value
    row = con.execute(
        """
        SELECT value
        FROM app_settings
        WHERE key = ?
        """,
        (key,),
    ).fetchone()
    if row is None:
        return default
    return row["value"]


def set_setting(con, key, value):
    # Upsert keeps one current value for each application preference
    row = con.execute(
        """
        INSERT INTO app_settings (key, value)
        VALUES (?, ?)
        ON CONFLICT (key) DO UPDATE
        SET value = excluded.value
        RETURNING key, value
        """,
        (key, value),
    ).fetchone()
    con.commit()
    return row
