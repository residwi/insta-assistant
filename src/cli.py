"""CLI interface for Instagram unfollower tracker"""

import sys

from instagrapi.exceptions import RateLimitError

from .auth import login_with_session
from .database import Database
from .marker import display_marking_summary, mark_accounts_interactive
from .tracker import (
    fetch_relationship_data,
    get_relationship_stats,
    identify_unfollowers,
    save_current_snapshot,
)


def run():
    """Main CLI entry point"""
    try:
        # Initialize database
        db = Database()

        # Authenticate
        client = login_with_session()

        # Fetch current relationship data
        print()
        following, followers = fetch_relationship_data(client)

        # Create check record
        stats = get_relationship_stats(following, followers)
        check_id = db.create_check_record(
            total_following=stats["total_following"],
            total_followers=stats["total_followers"],
        )

        # Check if this is first run
        is_first_run = not db.has_previous_snapshots()

        if is_first_run:
            # First run - establish baseline
            _handle_first_run(following, followers, db, check_id, stats)
        else:
            # Subsequent runs - detect and mark unfollowers
            _handle_subsequent_run(following, followers, db, check_id, stats)

        # Save current snapshot
        save_current_snapshot(following, followers, db, check_id)

    except RateLimitError:
        print("\nError: Rate limit exceeded")
        print("Instagram is blocking requests. Try again later.")
        sys.exit(1)

    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
        sys.exit(0)

    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


def _handle_first_run(following, followers, db, check_id, stats):
    """Handle first run - establish baseline"""
    print("\nBaseline established.")
    print(f"You follow {stats['total_following']} accounts")
    print(f"{stats['total_followers']} follow you back")
    print(f"{stats['non_followers_count']} don't follow back")
    print("\nSaved snapshot.")

    # Update check record
    db.update_check_record(
        check_id=check_id,
        non_followers_count=stats["non_followers_count"],
        new_unfollowers_count=0,
        marked_count=0,
    )


def _handle_subsequent_run(following, followers, db, check_id, stats):
    """Handle subsequent runs - detect and mark unfollowers"""
    # Identify unmarked unfollowers
    unfollowers = identify_unfollowers(following, followers, db)

    if not unfollowers:
        print("\nNo new unfollowers detected.")
        print("All non-followers already marked.")

        db.update_check_record(
            check_id=check_id,
            non_followers_count=stats["non_followers_count"],
            new_unfollowers_count=0,
            marked_count=0,
        )
        return

    # Display count
    count = len(unfollowers)
    if count == 1:
        print(f"\nDetected {count} account that doesn't follow you back:")
    else:
        print(f"\nDetected {count} accounts that don't follow you back:")

    # Interactive marking
    marking_stats = mark_accounts_interactive(unfollowers, db)

    # Display summary
    display_marking_summary(marking_stats)

    # Update check record
    total_marked = marking_stats["influencer"] + marking_stats["unfollower"]
    db.update_check_record(
        check_id=check_id,
        non_followers_count=stats["non_followers_count"],
        new_unfollowers_count=len(unfollowers),
        marked_count=total_marked,
    )

    # Check if all accounts categorized
    if marking_stats["skipped"] == 0:
        print("\nAll accounts categorized.")
