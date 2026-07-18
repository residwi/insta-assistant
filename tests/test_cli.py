from instagrapi.exceptions import RateLimitError

from src.cli import check, resolve_pending
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


def test_report_no_changes_prints_no_change_message(db):
    """When there are no departures and no gains, report a single 'No changes' line."""
    c = db.create_check_record(total_followers=2, reported_follower_count=2, fetch_ok=True)
    db.save_follower_snapshot(c, {"1": "alice", "2": "bob"})
    # same followers as before — no diff
    client = FakeClient(followers={"1": "alice", "2": "bob"}, reported_count=2)
    out, sink = _lines()
    check(client, db, sleep_fn=lambda s: None, out=sink)
    full = "\n".join(out)
    assert "No changes since last check." in full
    # must not print dangling zero-count lines like "Unfollowed you (0): "
    assert "Unfollowed you (0)" not in full
    assert "New followers (0)" not in full


def test_report_zero_count_categories_suppressed_when_some_have_entries(db):
    """Zero-count categories should not appear even when other categories have entries."""
    c = db.create_check_record(total_followers=2, reported_follower_count=2, fetch_ok=True)
    db.save_follower_snapshot(c, {"1": "alice", "2": "bob"})
    # bob left; profile still exists -> unfollowed; carol joined
    client = FakeClient(
        followers={"1": "alice", "3": "carol"},
        reported_count=2,
        profiles={"2": FakeUser(username="bob")},
    )
    out, sink = _lines()
    check(client, db, sleep_fn=lambda s: None, out=sink)
    full = "\n".join(out)
    # unfollowed line must appear (has entry)
    assert "unfollowed" in full.lower()
    # new followers line must appear (carol)
    assert "carol" in full
    # disappeared line should NOT appear (no disappeared entries)
    assert "Disappeared (0)" not in full


# ---------------------------------------------------------------------------
# FIX 7: resume-invariant regression tests
# ---------------------------------------------------------------------------


def test_check_rate_limited_departure_stays_unresolved_and_snapshot_advances(db):
    """(7a) When classify_departure exhausts backoff with RateLimitError, the departure
    remains in get_unresolved_departures(), the run completes, and the snapshot advances."""
    c = db.create_check_record(total_followers=2, reported_follower_count=2, fetch_ok=True)
    db.save_follower_snapshot(c, {"1": "alice", "2": "bob"})

    # bob is gone; user_info("2") always raises RateLimitError -> exhausts backoff
    client = FakeClient(
        followers={"1": "alice"},
        reported_count=1,
        profiles={"2": RateLimitError("rate limit")},
    )
    out, sink = _lines()
    # Must not raise — run completes normally
    check(client, db, sleep_fn=lambda s: None, out=sink)

    # Departure recorded but not classified — still in unresolved list
    unresolved = db.get_unresolved_departures()
    assert ("2", "bob") in unresolved, "bob's departure must remain unclassified"

    # Snapshot must have advanced to the new follower set (only alice)
    assert db.get_previous_followers() == {"1": "alice"}, "snapshot must advance despite rate limit"


def test_resolve_pending_rate_limited_breaks_cleanly_and_leaves_unresolved(db):
    """(7b) resolve_pending with a rate-limited lookup breaks cleanly (no exception escapes)
    and leaves the departure still unresolved in the db."""
    # Seed an unclassified departure directly via record_departure
    seed_id = db.create_check_record(total_followers=1, reported_follower_count=1, fetch_ok=True)
    db.record_departure(seed_id, "99", "ghost")

    assert db.get_unresolved_departures() == [("99", "ghost")]

    # user_info("99") always raises RateLimitError -> exhausts backoff in classify_departure
    client = FakeClient(
        followers={},
        reported_count=0,
        profiles={"99": RateLimitError("rate limit")},
    )
    out, sink = _lines()
    # Must not raise
    resolve_pending(client, db, sleep_fn=lambda s: None, out=sink)

    # Departure must remain unresolved
    assert db.get_unresolved_departures() == [("99", "ghost")], "departure must stay unresolved"
