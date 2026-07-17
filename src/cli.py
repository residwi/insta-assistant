"""CLI interface: single-run follower-diff tracker."""

import sys
import time

from instagrapi.exceptions import PleaseWaitFewMinutes, RateLimitError

from .auth import login_with_session
from .database import Database
from .tracker import (
    classify_departure,
    diff_followers,
    fetch_followers,
    is_fetch_suspect,
)


def resolve_pending(client, db, *, sleep_fn=time.sleep, out=print) -> None:
    """Retry classifying departures left unclassified by earlier runs."""
    pending = db.get_unresolved_departures()
    if not pending:
        return
    out(f"Resuming classification of {len(pending)} pending departure(s)...")
    for user_id, username in pending:
        try:
            reason = classify_departure(client, user_id, sleep_fn=sleep_fn)
            db.resolve_departure(user_id, reason)
            out(f"  @{username}: {reason}")
        except RateLimitError, PleaseWaitFewMinutes:
            out(f"  @{username}: still rate-limited, will retry next run")
            break


def check(client, db, *, sleep_fn=time.sleep, out=print) -> None:
    """Detect follower departures/gains for one run and report the delta."""
    resolve_pending(client, db, sleep_fn=sleep_fn, out=out)

    followers, reported = fetch_followers(client)
    fetch_ok = not is_fetch_suspect(len(followers), reported)
    check_id = db.create_check_record(
        total_followers=len(followers),
        reported_follower_count=reported,
        fetch_ok=fetch_ok,
    )

    if not fetch_ok:
        out(f"WARNING: fetched only {len(followers)} of ~{reported} followers — likely throttled.")
        out("Skipping diff to avoid recording false unfollowers. Try again later.")
        return

    if not db.has_follower_snapshots():
        db.save_follower_snapshot(check_id, followers)
        out(f"Baseline established: {len(followers)} followers. No diff on first run.")
        return

    previous = db.get_previous_followers()
    departed_ids, gained_ids = diff_followers(set(previous), set(followers))
    departed = [(uid, previous[uid]) for uid in departed_ids]
    gained = [(uid, followers[uid]) for uid in gained_ids]

    # Persist detection BEFORE classification so an interrupted run loses nothing.
    for uid, uname in departed:
        db.record_departure(check_id, uid, uname)
    for uid, uname in gained:
        db.record_gain(check_id, uid, uname)
    db.update_check_record(check_id, new_unfollowers_count=len(departed))
    db.save_follower_snapshot(check_id, followers)

    # Classify each departure inline (with backoff inside classify_departure).
    reasons: dict[str, str] = {}
    for uid, uname in departed:
        try:
            reasons[uid] = classify_departure(client, uid, sleep_fn=sleep_fn)
            db.resolve_departure(uid, reasons[uid])
        except RateLimitError, PleaseWaitFewMinutes:
            reasons[uid] = "unclassified"

    _report(out, departed, gained, reasons)


def _report(out, departed, gained, reasons) -> None:
    unfollowed = [n for uid, n in departed if reasons.get(uid) == "unfollowed"]
    disappeared = [n for uid, n in departed if reasons.get(uid) == "disappeared"]
    pending = [n for uid, n in departed if reasons.get(uid) == "unclassified"]
    gained_names = [n for _uid, n in gained]

    out("\nSince last check:")
    out(f"  Unfollowed you ({len(unfollowed)}): " + ", ".join(f"@{n}" for n in unfollowed))
    out(f"  Disappeared ({len(disappeared)}): " + ", ".join(f"@{n}" for n in disappeared))
    if pending:
        out(
            f"  Rate-limited, will classify next run ({len(pending)}): "
            + ", ".join(f"@{n}" for n in pending)
        )
    out(f"  New followers ({len(gained_names)}): " + ", ".join(f"@{n}" for n in gained_names))


def run() -> None:
    """Main entry point."""
    try:
        db = Database()
        client = login_with_session()
        print()
        check(client, db)
    except RateLimitError, PleaseWaitFewMinutes:
        print("\nError: Rate limit exceeded. Instagram is blocking requests. Try again later.")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)
