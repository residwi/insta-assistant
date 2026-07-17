import pytest

from src.database import Database


@pytest.fixture
def db(tmp_path):
    """A fresh Database backed by a temp file."""
    return Database(db_path=str(tmp_path / "test.db"))


class FakeUser:
    def __init__(self, username="", follower_count=0):
        self.username = username
        self.follower_count = follower_count


class FakeClient:
    """Configurable stand-in for instagrapi.Client (no network)."""

    def __init__(self, followers=None, reported_count=None, profiles=None):
        # followers: {user_id: username}
        self._followers = followers or {}
        self.user_id = "self"
        self._reported = reported_count if reported_count is not None else len(self._followers)
        # profiles: {user_id: FakeUser | Exception}; missing id => raise UserNotFound
        self._profiles = profiles or {}

    def user_followers(self, user_id):
        return {uid: FakeUser(username=name) for uid, name in self._followers.items()}

    def user_info(self, user_id):
        if user_id == self.user_id:
            return FakeUser(follower_count=self._reported)
        from instagrapi.exceptions import UserNotFound

        val = self._profiles.get(user_id)
        if val is None:
            raise UserNotFound(user_id)
        if isinstance(val, Exception):
            raise val
        return val
