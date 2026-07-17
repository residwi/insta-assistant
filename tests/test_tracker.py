import pytest

from src.tracker import diff_followers, is_fetch_suspect, classify_from_exists, with_backoff


def test_diff_followers_detects_departed_and_gained():
    previous = {"a", "b", "c"}
    current = {"a", "c", "d"}
    departed, gained = diff_followers(previous, current)
    assert departed == {"b"}
    assert gained == {"d"}


def test_diff_followers_no_change():
    same = {"a", "b"}
    departed, gained = diff_followers(same, set(same))
    assert departed == set()
    assert gained == set()


def test_diff_followers_empty_previous_is_all_gains():
    departed, gained = diff_followers(set(), {"a", "b"})
    assert departed == set()
    assert gained == {"a", "b"}


def test_fetch_not_suspect_when_counts_match():
    assert is_fetch_suspect(112, 112) is False


def test_fetch_not_suspect_within_small_tolerance():
    # off by 2, under the abs_tol of 3
    assert is_fetch_suspect(110, 112) is False


def test_fetch_suspect_on_large_shortfall():
    # fetched only 97 of 112 -> throttled
    assert is_fetch_suspect(97, 112) is True


def test_fetch_not_suspect_when_fetched_exceeds_reported():
    # reported count lags behind; not a partial fetch
    assert is_fetch_suspect(115, 112) is False


def test_fetch_suspect_uses_relative_tolerance_on_large_accounts():
    # 5% of 10000 = 500; shortfall of 800 is suspect
    assert is_fetch_suspect(9200, 10000) is True
    # shortfall of 300 is within 5%
    assert is_fetch_suspect(9700, 10000) is False


def test_classify_existing_account_is_unfollowed():
    assert classify_from_exists(True) == "unfollowed"


def test_classify_missing_account_is_disappeared():
    assert classify_from_exists(False) == "disappeared"


def test_with_backoff_returns_immediately_on_success():
    sleeps = []
    result = with_backoff(lambda: "ok", sleep_fn=sleeps.append, jitter_fn=lambda a, b: 0)
    assert result == "ok"
    assert sleeps == []


def test_with_backoff_retries_then_succeeds():
    calls = {"n": 0}
    sleeps = []

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise ValueError("rate limited")
        return "done"

    result = with_backoff(
        flaky,
        retry_on=(ValueError,),
        base_delay=1.0,
        sleep_fn=sleeps.append,
        jitter_fn=lambda a, b: 0,
    )
    assert result == "done"
    assert calls["n"] == 3
    assert sleeps == [1.0, 2.0]  # 1*2^0, 1*2^1


def test_with_backoff_gives_up_after_max_retries():
    sleeps = []

    def always_fails():
        raise ValueError("nope")

    with pytest.raises(ValueError):
        with_backoff(
            always_fails,
            retry_on=(ValueError,),
            max_retries=2,
            base_delay=1.0,
            sleep_fn=sleeps.append,
            jitter_fn=lambda a, b: 0,
        )
    assert len(sleeps) == 2  # slept before retry 1 and retry 2, then raised


def test_fetch_followers_returns_map_and_reported_count():
    from src.tracker import fetch_followers
    from tests.conftest import FakeClient

    client = FakeClient(followers={"1": "alice", "2": "bob"}, reported_count=2)
    followers, reported = fetch_followers(client)
    assert followers == {"1": "alice", "2": "bob"}
    assert reported == 2


def test_classify_departure_existing_account_unfollowed():
    from src.tracker import classify_departure
    from tests.conftest import FakeClient, FakeUser

    client = FakeClient(profiles={"9": FakeUser(username="still_here")})
    assert classify_departure(client, "9", sleep_fn=lambda s: None) == "unfollowed"


def test_classify_departure_missing_account_disappeared():
    from src.tracker import classify_departure
    from tests.conftest import FakeClient

    client = FakeClient(profiles={})  # unknown id -> UserNotFound
    assert classify_departure(client, "9", sleep_fn=lambda s: None) == "disappeared"


def test_classify_departure_retries_on_rate_limit_then_succeeds():
    from instagrapi.exceptions import RateLimitError

    from src.tracker import classify_departure
    from tests.conftest import FakeClient, FakeUser

    calls = {"n": 0}

    class Flaky(FakeClient):
        def user_info(self, user_id):
            if user_id == self.user_id:
                return FakeUser(follower_count=0)
            calls["n"] += 1
            if calls["n"] < 2:
                raise RateLimitError("slow down")
            return FakeUser(username="recovered")

    client = Flaky()
    sleeps = []
    result = classify_departure(client, "9", sleep_fn=sleeps.append)
    assert result == "unfollowed"
    assert calls["n"] == 2
    assert len(sleeps) == 1
