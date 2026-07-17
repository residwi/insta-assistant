from src.tracker import diff_followers, is_fetch_suspect, classify_from_exists


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
