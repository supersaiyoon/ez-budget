import sqlite3


def connect(db_path):
    con = sqlite3.connect(db_path)
    # Row objects allow name-based column access without custom wrappers.
    con.row_factory = sqlite3.Row
    # SQLite requires this per connection so relationships are actually enforced.
    con.execute("PRAGMA foreign_keys = ON")
    return con
