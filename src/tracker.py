"""Core follower-diff detection logic (pure, network-free)."""

import random
import time
from collections.abc import Callable
from typing import TypeVar

from instagrapi.exceptions import PleaseWaitFewMinutes, RateLimitError

T = TypeVar("T")


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


def classify_from_exists(exists: bool) -> str:
    """Map account existence to a departure reason.

    A still-existing account that left your followers = 'unfollowed'.
    A gone account (deactivated/deleted/banned) = 'disappeared'.
    """
    return "unfollowed" if exists else "disappeared"


def with_backoff(
    fn: Callable[[], T],
    *,
    max_retries: int = 5,
    base_delay: float = 60.0,
    max_delay: float = 900.0,
    sleep_fn: Callable[[float], None] = time.sleep,
    jitter_fn: Callable[[float, float], float] = random.uniform,
    retry_on: tuple[type[Exception], ...] = (RateLimitError, PleaseWaitFewMinutes),
) -> T:
    """Call fn(), retrying on rate-limit exceptions with exponential backoff + jitter.

    Re-raises the last exception once max_retries is exhausted.
    """
    attempt = 0
    while True:
        try:
            return fn()
        except retry_on:
            if attempt >= max_retries:
                raise
            delay = min(base_delay * (2**attempt), max_delay) + jitter_fn(0, base_delay)
            sleep_fn(delay)
            attempt += 1
