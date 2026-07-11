import sqlite3


SCHEMA_PATH = "db/schema.sql"


def connect(db_path):
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row

    # Required to enforce foreign key constraints in SQLite
    con.execute("PRAGMA foreign_keys = ON")
    return con


def initialize_database(con):
    with open(SCHEMA_PATH) as f:
        sql = f.read()

    con.executescript(sql)
    con.commit()
