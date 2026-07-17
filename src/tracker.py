"""Core follower-diff detection logic (pure, network-free)."""


def diff_followers(previous: set[str], current: set[str]) -> tuple[set[str], set[str]]:
    """Return (departed, gained) between two follower-id sets.

    departed = ids in `previous` but not `current` (they left your followers)
    gained   = ids in `current` but not `previous` (new followers)
    """
    return previous - current, current - previous


def is_fetch_suspect(
    fetched_count: int,
    reported_count: int,
    abs_tol: int = 3,
    rel_tol: float = 0.05,
) -> bool:
    """True when the fetched follower list is implausibly short vs the reported count.

    Guards against a throttled/partial fetch fabricating false departures.
    Fetching more than reported (count lag) is never suspect.
    """
    shortfall = reported_count - fetched_count
    if shortfall <= 0:
        return False
    return shortfall > max(abs_tol, reported_count * rel_tol)
