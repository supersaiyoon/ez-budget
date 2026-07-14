from db import database, payees


def test_add_payee_inserts_payee_row():
    con = database.connect(":memory:")
    database.initialize_database(con)

    payee = payees.add_payee(con, "Grocery Store")

    assert payee["id"] == 1
    assert payee["name"] == "Grocery Store"


def test_get_payee_by_name_returns_matching_payee():
    con = database.connect(":memory:")
    database.initialize_database(con)
    payees.add_payee(con, "Grocery Store")
    fuel_stop = payees.add_payee(con, "Fuel Stop")

    payee = payees.get_payee_by_name(con, "Fuel Stop")

    assert payee["id"] == fuel_stop["id"]
    assert payee["name"] == "Fuel Stop"
