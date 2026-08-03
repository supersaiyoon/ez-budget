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
    migrate_database(con)
    con.commit()


def migrate_database(con):
    # Existing project databases need ordering columns without a full migration tool
    ensure_column(
        con,
        "master_budget_categories",
        "display_order",
        "INT NOT NULL DEFAULT 0",
    )
    ensure_column(
        con,
        "budget_categories",
        "display_order",
        "INT NOT NULL DEFAULT 0",
    )
    con.execute(
        """
        UPDATE master_budget_categories
        SET display_order = id
        WHERE display_order = 0
        """
    )
    con.execute(
        """
        UPDATE budget_categories
        SET display_order = id
        WHERE display_order = 0
        """
    )


def ensure_column(con, table_name, column_name, column_definition):
    # PRAGMA metadata keeps repeat initialization idempotent
    columns = {
        column["name"]
        for column in con.execute(f"PRAGMA table_info({table_name})")
    }
    if column_name in columns:
        return

    con.execute(
        f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
    )
