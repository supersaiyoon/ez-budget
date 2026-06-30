import sqlite3


def connect(db_path):
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row

    # Required to enforce foreign key constraints in SQLite
    con.execute("PRAGMA foreign_keys = ON")
    return con
