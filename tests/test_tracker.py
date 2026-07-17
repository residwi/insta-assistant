from src.tracker import diff_followers


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
