from db import categories, database


def test_add_master_category_inserts_master_category_row():
    con = database.connect(":memory:")
    database.initialize_database(con)

    category = categories.add_master_category(con, "Monthly Bills")

    assert category["id"] == 1
    assert category["name"] == "Monthly Bills"
    assert category["hidden"] == False
