"""Interactive marking system for categorizing accounts"""

from typing import Dict, List, Optional, Tuple

from .database import Database


def mark_accounts_interactive(
    unfollowers: List[Tuple[str, str]], db: Database
) -> Dict[str, int]:
    """
    Interactive CLI to mark each unfollower account.

    Prompts user to categorize each account as:
    - (i)nfluencer: Will never appear in results again
    - (u)nfollower: Will never appear in results again
    - (s)kip: Will appear in next run

    Args:
        unfollowers: List of (user_id, username) tuples
        db: Database instance

    Returns:
        dict: Statistics {'influencer': count, 'unfollower': count, 'skipped': count}
    """
    if not unfollowers:
        return {"influencer": 0, "unfollower": 0, "skipped": 0}

    stats = {"influencer": 0, "unfollower": 0, "skipped": 0}

    for user_id, username in unfollowers:
        category = prompt_for_category(username)

        if category:
            db.mark_account(user_id, username, category)
            print(f"Marked as {category}.")
            stats[category] += 1
        else:
            print("Skipped (will appear next run).")
            stats["skipped"] += 1

    return stats


def prompt_for_category(username: str) -> Optional[str]:
    """
    Prompt user to categorize a single account.

    Args:
        username: Instagram username to display

    Returns:
        str or None: 'influencer', 'unfollower', or None (skipped)
    """
    print(f"\nAccount: @{username}")

    while True:
        choice = (
            input("Mark as (i)nfluencer, (u)nfollower, or (s)kip? ").lower().strip()
        )

        if choice == "i":
            return "influencer"

        if choice == "u":
            return "unfollower"

        if choice == "s":
            return None

        print("Invalid choice. Please enter i, u, or s.")


def display_marking_summary(stats: Dict[str, int]):
    """
    Display summary of marking session.

    Args:
        stats: Dictionary with marking statistics
    """
    total_marked = stats["influencer"] + stats["unfollower"]

    if total_marked > 0 or stats["skipped"] > 0:
        print("\nSummary:")
        print(f"- Total marked: {total_marked}")
        if stats["influencer"] > 0:
            print(f"- Influencers: {stats['influencer']}")
        if stats["unfollower"] > 0:
            print(f"- Unfollowers: {stats['unfollower']}")
        if stats["skipped"] > 0:
            print(f"- Skipped: {stats['skipped']}")
