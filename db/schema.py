from pathlib import Path


MIGRATIONS_DIR = Path(__file__).with_name("migrations")


def initialize_database(con, migrations_dir=MIGRATIONS_DIR):
    # Create database tables from SQL migration files
    for migration_path in sorted(migrations_dir.glob("*.sql")):
        sql = migration_path.read_text(encoding="utf-8")
        con.executescript(sql)
    con.commit()
