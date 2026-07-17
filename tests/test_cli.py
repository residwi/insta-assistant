from src.cli import check
from tests.conftest import FakeClient, FakeUser


def _lines():
    captured = []
    return captured, captured.append


def test_first_run_establishes_baseline_without_diffing(db):
    client = FakeClient(followers={"1": "a", "2": "b"}, reported_count=2)
    out, sink = _lines()
    check(client, db, sleep_fn=lambda s: None, out=sink)
    assert db.get_previous_followers() == {"1": "a", "2": "b"}
    assert any("Baseline" in line for line in out)


def test_suspect_fetch_warns_and_skips_snapshot(db):
    # seed a good baseline first
    c = db.create_check_record(total_followers=112, reported_follower_count=112, fetch_ok=True)
    db.save_follower_snapshot(c, {str(i): f"u{i}" for i in range(112)})
    # now a throttled fetch: only 90 of reported 112
    client = FakeClient(followers={str(i): f"u{i}" for i in range(90)}, reported_count=112)
    out, sink = _lines()
    check(client, db, sleep_fn=lambda s: None, out=sink)
    # baseline snapshot unchanged (still 112 in latest good snapshot)
    assert len(db.get_previous_followers()) == 112
    assert any("throttled" in line.lower() or "skipping" in line.lower() for line in out)


def test_detects_unfollower_and_classifies(db):
    # baseline: alice + bob follow you
    c = db.create_check_record(total_followers=2, reported_follower_count=2, fetch_ok=True)
    db.save_follower_snapshot(c, {"1": "alice", "2": "bob"})
    # now bob is gone; bob's profile still exists -> unfollowed
    client = FakeClient(
        followers={"1": "alice"},
        reported_count=1,
        profiles={"2": FakeUser(username="bob")},
    )
    out, sink = _lines()
    check(client, db, sleep_fn=lambda s: None, out=sink)
    assert db.get_unresolved_departures() == []  # classified, not pending
    assert any("unfollowed" in line.lower() for line in out)
    assert db.get_previous_followers() == {"1": "alice"}  # snapshot advanced


def test_disappeared_account_classified_as_disappeared(db):
    c = db.create_check_record(total_followers=2, reported_follower_count=2, fetch_ok=True)
    db.save_follower_snapshot(c, {"1": "alice", "2": "ghost"})
    # ghost gone and profile 404s -> disappeared
    client = FakeClient(followers={"1": "alice"}, reported_count=1, profiles={})
    out, sink = _lines()
    check(client, db, sleep_fn=lambda s: None, out=sink)
    assert any("disappeared" in line.lower() for line in out)


def test_new_follower_reported(db):
    c = db.create_check_record(total_followers=1, reported_follower_count=1, fetch_ok=True)
    db.save_follower_snapshot(c, {"1": "alice"})
    client = FakeClient(followers={"1": "alice", "3": "carol"}, reported_count=2)
    out, sink = _lines()
    check(client, db, sleep_fn=lambda s: None, out=sink)
    assert any("carol" in line for line in out)
