from db import database, payees


def test_add_payee_inserts_payee_row():
    con = database.connect(":memory:")
    database.initialize_database(con)

    payee = payees.add_payee(con, "Grocery Store")

    assert payee["id"] == 1
    assert payee["name"] == "Grocery Store"
