from clash_lab.database import Database


def test_database_initializes_profiles_table(tmp_path):
    db = Database(tmp_path / "test.sqlite3")
    assert db.list_profiles() == []
    profile_id = db.add_profile("test village", "emulator-5554")
    assert profile_id > 0
    assert db.list_profiles()[0]["serial"] == "emulator-5554"


def test_profile_delete(tmp_path):
    db = Database(tmp_path / "test.sqlite3")
    profile_id = db.add_profile("test village", "127.0.0.1:5555")
    db.delete_profile(profile_id)
    assert db.list_profiles() == []


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


def test_task_persistence_and_enable(tmp_path):
    db = Database(tmp_path / "test.sqlite3")
    profile_id = db.add_profile("main village", "127.0.0.1:5555")
    task_id = db.add_task(
        "screen check",
        task_type="general",
        profile_id=profile_id,
        config={"safe_mode": True},
    )
    task = db.list_tasks(profile_id)[0]
    assert task["id"] == task_id
    assert task["enabled"] == 0
    assert task["config_json"] == '{"safe_mode": true}'
    db.set_task_enabled(task_id, True)
    assert db.list_tasks(profile_id)[0]["enabled"] == 1
