"""Database operations for Instagram unfollower tracker"""

import sqlite3
from contextlib import contextmanager
from typing import List, Optional, Tuple


class Database:
    """SQLite database manager for tracking followers and markings"""

    def __init__(self, db_path: str = "data/tracker.db"):
        self.db_path = db_path
        self.create_tables()
        self.migrate()

    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def create_tables(self):
        """Initialize database schema"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Accounts table - stores categorization
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS accounts (
                    user_id TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    category TEXT,
                    marked_at TIMESTAMP,
                    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_category ON accounts(category)
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_username ON accounts(username)
            """
            )

            # Relationship snapshots - historical tracking
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS relationship_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    check_id INTEGER NOT NULL,
                    user_id TEXT NOT NULL,
                    username TEXT NOT NULL,
                    is_following_me BOOLEAN NOT NULL,
                    i_am_following BOOLEAN NOT NULL,
                    snapshot_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (check_id) REFERENCES check_history(id)
                )
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_check_id
                ON relationship_snapshots(check_id)
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_user_id
                ON relationship_snapshots(user_id)
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_snapshot_time
                ON relationship_snapshots(snapshot_time)
            """
            )

            # Check history - run metadata
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS check_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    check_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    total_following INTEGER NOT NULL,
                    total_followers INTEGER NOT NULL,
                    non_followers_count INTEGER,
                    new_unfollowers_count INTEGER,
                    marked_count INTEGER DEFAULT 0
                )
            """
            )

            # Follower events - departures and gains detected per check
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS follower_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    check_id INTEGER NOT NULL,
                    user_id TEXT NOT NULL,
                    username TEXT,
                    kind TEXT NOT NULL,
                    reason TEXT,
                    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    resolved_at TIMESTAMP,
                    FOREIGN KEY (check_id) REFERENCES check_history(id)
                )
            """
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_reason ON follower_events(reason)"
            )

    def migrate(self):
        """Additive migration: add new check_history columns if missing."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            existing = {row["name"] for row in cursor.execute("PRAGMA table_info(check_history)")}
            if "follower_count" not in existing:
                cursor.execute("ALTER TABLE check_history ADD COLUMN follower_count INTEGER")
            if "fetch_ok" not in existing:
                cursor.execute("ALTER TABLE check_history ADD COLUMN fetch_ok INTEGER")

    def create_check_record(
        self, total_followers: int, reported_follower_count: int, fetch_ok: bool
    ) -> int:
        """Create a new check history record and return its ID.

        total_following is legacy (following is no longer fetched) and stored as 0.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO check_history (
                    total_following, total_followers, follower_count, fetch_ok
                )
                VALUES (0, ?, ?, ?)
            """,
                (total_followers, reported_follower_count, 1 if fetch_ok else 0),
            )
            return cursor.lastrowid

    def save_follower_snapshot(self, check_id: int, followers: dict) -> None:
        """Persist the current follower set (is_following_me=1, i_am_following=0)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(
                """
                INSERT INTO relationship_snapshots (
                    check_id, user_id, username, is_following_me, i_am_following
                )
                VALUES (?, ?, ?, 1, 0)
            """,
                [(check_id, uid, uname) for uid, uname in followers.items()],
            )

    def get_previous_followers(self) -> dict:
        """Reconstruct the follower set from the most recent snapshot."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            row = cursor.execute(
                "SELECT MAX(check_id) AS c FROM relationship_snapshots"
            ).fetchone()
            latest = row["c"]
            if latest is None:
                return {}
            rows = cursor.execute(
                """
                SELECT user_id, username FROM relationship_snapshots
                WHERE check_id = ? AND is_following_me = 1
            """,
                (latest,),
            ).fetchall()
            return {r["user_id"]: r["username"] for r in rows}

    def has_follower_snapshots(self) -> bool:
        """Whether any follower snapshot exists."""
        return self.has_previous_snapshots()

    def update_check_record(self, check_id: int, new_unfollowers_count: int) -> None:
        """Update check record with the departure count."""
        with self.get_connection() as conn:
            conn.execute(
                "UPDATE check_history SET new_unfollowers_count = ? WHERE id = ?",
                (new_unfollowers_count, check_id),
            )

    def record_departure(self, check_id: int, user_id: str, username: str) -> None:
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO follower_events (check_id, user_id, username, kind, reason)
                VALUES (?, ?, ?, 'departed', 'unclassified')
            """,
                (check_id, user_id, username),
            )

    def record_gain(self, check_id: int, user_id: str, username: str) -> None:
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO follower_events (check_id, user_id, username, kind, reason)
                VALUES (?, ?, ?, 'gained', NULL)
            """,
                (check_id, user_id, username),
            )

    def resolve_departure(self, user_id: str, reason: str) -> None:
        with self.get_connection() as conn:
            conn.execute(
                """
                UPDATE follower_events
                SET reason = ?, resolved_at = CURRENT_TIMESTAMP
                WHERE id = (
                    SELECT id FROM follower_events
                    WHERE user_id = ? AND kind = 'departed' AND reason = 'unclassified'
                    ORDER BY id DESC LIMIT 1
                )
            """,
                (reason, user_id),
            )

    def get_unresolved_departures(self) -> list[tuple[str, str]]:
        with self.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT user_id, username FROM follower_events
                WHERE kind = 'departed' AND reason = 'unclassified'
                ORDER BY id
            """
            ).fetchall()
            return [(r["user_id"], r["username"]) for r in rows]

    def save_snapshot(
        self,
        check_id: int,
        user_id: str,
        username: str,
        is_following_me: bool,
        i_am_following: bool,
    ):
        """Save a relationship snapshot"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO relationship_snapshots (
                    check_id,
                    user_id,
                    username,
                    is_following_me,
                    i_am_following
                )
                VALUES (?, ?, ?, ?, ?)
            """,
                (check_id, user_id, username, is_following_me, i_am_following),
            )

    def used_to_follow_back(self, user_id: str) -> bool:
        """Check if user ever followed back historically"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT 1
                FROM relationship_snapshots
                WHERE user_id = ? AND is_following_me = 1
                LIMIT 1
            """,
                (user_id,),
            )
            return cursor.fetchone() is not None

    def is_marked(self, user_id: str) -> bool:
        """Check if user already categorized"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT 1
                FROM accounts
                WHERE user_id = ? AND category IS NOT NULL
                LIMIT 1
            """,
                (user_id,),
            )
            return cursor.fetchone() is not None

    def mark_account(self, user_id: str, username: str, category: str):
        """Save category for account"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Insert or update account
            cursor.execute(
                """
                INSERT INTO accounts (user_id, username, category, marked_at, last_updated)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    category = excluded.category,
                    marked_at = CURRENT_TIMESTAMP,
                    last_updated = CURRENT_TIMESTAMP
            """,
                (user_id, username, category),
            )

    def ensure_account_exists(self, user_id: str, username: str):
        """Ensure account exists in database (for unmarked accounts)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR IGNORE INTO accounts (user_id, username)
                VALUES (?, ?)
            """,
                (user_id, username),
            )

    def get_unmarked_unfollowers(self) -> List[Tuple[str, str]]:
        """
        Get accounts that:
        1. User is following
        2. Don't follow back
        3. Used to follow back (historical)
        4. Not marked yet
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT DISTINCT r.user_id, r.username
                FROM relationship_snapshots r
                LEFT JOIN accounts a ON r.user_id = a.user_id
                WHERE r.i_am_following = 1
                  AND r.is_following_me = 0
                  AND (a.category IS NULL OR a.category = '')
                  AND EXISTS (
                    SELECT 1 FROM relationship_snapshots r2
                    WHERE r2.user_id = r.user_id
                      AND r2.is_following_me = 1
                  )
                ORDER BY r.snapshot_time DESC
            """
            )
            return [(row["user_id"], row["username"]) for row in cursor.fetchall()]

    def has_previous_snapshots(self) -> bool:
        """Check if there are any previous snapshots"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM relationship_snapshots LIMIT 1")
            return cursor.fetchone() is not None

    def get_stats(self) -> Optional[dict]:
        """Get latest check statistics"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM check_history
                ORDER BY check_time DESC
                LIMIT 1
            """
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
