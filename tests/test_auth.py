from src.auth import login_with_session


class FakeClient:
    def __init__(self, session_valid=True):
        self._session_valid = session_valid
        self.loaded = False
        self.logged_in = False
        self.dumped = False

    def load_settings(self, path):
        self.loaded = True

    def get_timeline_feed(self):
        from instagrapi.exceptions import LoginRequired

        if not self._session_valid:
            raise LoginRequired("expired")

    def login(self, username, password, verification_code=""):
        self.logged_in = True

    def dump_settings(self, path):
        self.dumped = True


def test_valid_session_logs_in_silently_without_credentials(tmp_path):
    session = tmp_path / "session.json"
    session.write_text("{}")
    fake = FakeClient(session_valid=True)
    creds_called = {"n": 0}

    def creds():
        creds_called["n"] += 1
        return ("u", "p")

    client = login_with_session(
        session_file=str(session), client_factory=lambda: fake, credentials_fn=creds
    )
    assert client is fake
    assert fake.loaded is True
    assert fake.logged_in is False  # never logged in
    assert creds_called["n"] == 0  # never prompted


def test_expired_session_falls_back_to_credential_login(tmp_path):
    session = tmp_path / "session.json"
    session.write_text("{}")
    fake = FakeClient(session_valid=False)

    client = login_with_session(
        session_file=str(session),
        client_factory=lambda: fake,
        credentials_fn=lambda: ("u", "p"),
    )
    assert client is fake
    assert fake.logged_in is True
    assert fake.dumped is True


def test_missing_session_logs_in_with_credentials(tmp_path):
    fake = FakeClient(session_valid=True)
    login_with_session(
        session_file=str(tmp_path / "nope.json"),
        client_factory=lambda: fake,
        credentials_fn=lambda: ("u", "p"),
    )
    assert fake.logged_in is True
