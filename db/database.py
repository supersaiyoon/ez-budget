import sqlite3
import sys
from pathlib import Path


def resource_path(*parts):
    # PyInstaller extracts bundled files under sys._MEIPASS at runtime
    base_path = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base_path.joinpath(*parts)


SCHEMA_PATH = resource_path("db", "schema.sql")


def connect(db_path):
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row

    # Required to enforce foreign key constraints in SQLite
    con.execute("PRAGMA foreign_keys = ON")
    return con


def initialize_database(con):
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        sql = f.read()

    con.executescript(sql)
    con.commit()
