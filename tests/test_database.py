def test_migrate_adds_new_columns(db):
    with db.get_connection() as conn:
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(check_history)")}
    assert "follower_count" in cols
    assert "fetch_ok" in cols


def test_follower_events_table_exists(db):
    with db.get_connection() as conn:
        names = {
            row["name"]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    assert "follower_events" in names


def test_has_follower_snapshots_false_when_empty(db):
    assert db.has_follower_snapshots() is False


def test_get_previous_followers_empty_when_no_snapshots(db):
    assert db.get_previous_followers() == {}


def test_save_and_read_back_latest_follower_snapshot(db):
    c1 = db.create_check_record(total_followers=2, reported_follower_count=2, fetch_ok=True)
    db.save_follower_snapshot(c1, {"1": "alice", "2": "bob"})
    c2 = db.create_check_record(total_followers=1, reported_follower_count=1, fetch_ok=True)
    db.save_follower_snapshot(c2, {"1": "alice"})
    # latest snapshot is c2 -> only alice
    assert db.get_previous_followers() == {"1": "alice"}
    assert db.has_follower_snapshots() is True
