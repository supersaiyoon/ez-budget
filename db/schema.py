SCHEMA_PATH = "db/schema.sql"


def initialize_database(con):
    with open(SCHEMA_PATH) as f:
        sql = f.read()

    con.executescript(sql)
    con.commit()
