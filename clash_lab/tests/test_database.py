from clash_lab.database import Database


def test_database_initializes_profiles_table(tmp_path):
    db = Database(tmp_path / "test.sqlite3")
    assert db.list_profiles() == []
    profile_id = db.add_profile("test village", "emulator-5554")
    assert profile_id > 0
    assert db.list_profiles()[0]["serial"] == "emulator-5554"


def test_settings_round_trip(tmp_path):
    db = Database(tmp_path / "test.sqlite3")
    db.set_setting("ui", {"language": "ar", "rtl": True})
    assert db.get_setting("ui") == {"language": "ar", "rtl": True}


def test_log_writes_rows(tmp_path):
    db = Database(tmp_path / "test.sqlite3")
    db.log("info", "startup")
    with db.connect() as conn:
        row = conn.execute("SELECT level, message FROM logs").fetchone()
    assert tuple(row) == ("INFO", "startup")
