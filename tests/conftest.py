import pytest

from src.database import Database


@pytest.fixture
def db(tmp_path):
    """A fresh Database backed by a temp file."""
    return Database(db_path=str(tmp_path / "test.db"))
