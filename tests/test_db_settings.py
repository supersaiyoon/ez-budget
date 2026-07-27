from db import settings


def test_get_setting_returns_default_when_key_is_missing(con):
    value = settings.get_setting(
        con,
        "closed_accounts_expanded",
        default="true",
    )

    assert value == "true"


def test_set_setting_inserts_and_updates_one_value(con):
    created = settings.set_setting(
        con,
        "closed_accounts_expanded",
        "false",
    )
    updated = settings.set_setting(
        con,
        "closed_accounts_expanded",
        "true",
    )

    assert created["value"] == "false"
    assert updated["value"] == "true"
    assert settings.get_setting(con, "closed_accounts_expanded") == "true"
    assert con.execute("SELECT COUNT(*) FROM app_settings").fetchone()[0] == 1
