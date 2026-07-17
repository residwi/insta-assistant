"""Core follower-diff detection logic (pure, network-free)."""


def diff_followers(previous: set[str], current: set[str]) -> tuple[set[str], set[str]]:
    """Return (departed, gained) between two follower-id sets.

    departed = ids in `previous` but not `current` (they left your followers)
    gained   = ids in `current` but not `previous` (new followers)
    """
    return previous - current, current - previous
