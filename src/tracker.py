"""Core unfollower detection logic"""

from typing import Dict, List, Tuple

from instagrapi import Client
from instagrapi.types import UserShort

from .database import Database


def fetch_relationship_data(
    client: Client,
) -> Tuple[Dict[str, UserShort], Dict[str, UserShort]]:
    """
    Fetch following and followers lists from Instagram.

    Args:
        client: Authenticated Instagram client

    Returns:
        tuple: (following_dict, followers_dict)
            - following_dict: {user_id: UserShort}
            - followers_dict: {user_id: UserShort}
    """
    print("Fetching following list...", end=" ", flush=True)
    following = client.user_following(client.user_id)
    print(f"({len(following)} accounts)")

    print("Fetching followers list...", end=" ", flush=True)
    followers = client.user_followers(client.user_id)
    print(f"({len(followers)} accounts)")

    return following, followers


def identify_unfollowers(
    following: Dict[str, UserShort], followers: Dict[str, UserShort], db: Database
) -> List[Tuple[str, str]]:
    """
    Find accounts that:
    1. User is following
    2. Don't follow back (based on current fetch)
    3. Not already marked

    Args:
        following: Dict of accounts user is following
        followers: Dict of accounts following user
        db: Database instance

    Returns:
        List of (user_id, username) tuples for unmarked non-followers
    """
    # Find non-followers (accounts user follows but don't follow back)
    non_followers = {
        user_id: user for user_id, user in following.items() if user_id not in followers
    }

    # Filter to only unmarked accounts
    unfollowers = []
    for user_id, user in non_followers.items():
        # Ensure account exists in database
        db.ensure_account_exists(user_id, user.username)

        # Only show if not already marked
        if not db.is_marked(user_id):
            unfollowers.append((user_id, user.username))

    return unfollowers


def save_current_snapshot(
    following: Dict[str, UserShort],
    followers: Dict[str, UserShort],
    db: Database,
    check_id: int,
):
    """
    Save current relationship snapshot to database.

    Creates a complete snapshot of all following/follower relationships
    for historical tracking.

    Args:
        following: Dict of accounts user is following
        followers: Dict of accounts following user
        db: Database instance
        check_id: Check history record ID
    """
    # Get all unique user IDs
    all_user_ids = set(following.keys()) | set(followers.keys())

    # Save snapshot for each user
    for user_id in all_user_ids:
        # Get username (prefer following, fallback to followers)
        username = (
            following[user_id].username
            if user_id in following
            else followers[user_id].username
        )

        is_following_me = user_id in followers
        i_am_following = user_id in following

        db.save_snapshot(
            check_id=check_id,
            user_id=user_id,
            username=username,
            is_following_me=is_following_me,
            i_am_following=i_am_following,
        )


def get_relationship_stats(
    following: Dict[str, UserShort], followers: Dict[str, UserShort]
) -> Dict[str, int]:
    """
    Calculate relationship statistics.

    Args:
        following: Dict of accounts user is following
        followers: Dict of accounts following user

    Returns:
        dict: Statistics about relationships
    """
    non_followers = set(following.keys()) - set(followers.keys())

    return {
        "total_following": len(following),
        "total_followers": len(followers),
        "follow_back_count": len(following) - len(non_followers),
        "non_followers_count": len(non_followers),
    }
