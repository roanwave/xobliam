"""SQLite cache layer for email metadata."""

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Generator, Optional


def get_cache_path() -> Path:
    """Get the path for the SQLite cache database."""
    cache_dir = Path(os.getenv("CACHE_DIR", "./data"))
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / "xobliam_cache.db"


class MessageCache:
    """SQLite-based cache for email messages."""

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize the message cache.

        Args:
            db_path: Path to the SQLite database. Uses default if not provided.
        """
        self.db_path = db_path or get_cache_path()
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the database schema."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    message_id TEXT PRIMARY KEY,
                    thread_id TEXT,
                    date TEXT,
                    sender TEXT,
                    recipients TEXT,
                    subject TEXT,
                    labels TEXT,
                    is_unread INTEGER,
                    has_attachments INTEGER,
                    snippet TEXT,
                    fetched_at TEXT
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS labels (
                    label_id TEXT PRIMARY KEY,
                    name TEXT,
                    type TEXT,
                    messages_total INTEGER,
                    messages_unread INTEGER,
                    fetched_at TEXT
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_date
                ON messages(date)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_sender
                ON messages(sender)
            """)

            conn.commit()

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Get a database connection with context management."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def cache_messages(self, messages: list[dict[str, Any]]) -> int:
        """
        Cache a list of messages.

        Args:
            messages: List of message dictionaries.

        Returns:
            Number of messages cached.
        """
        fetched_at = datetime.utcnow().isoformat()

        with self._get_connection() as conn:
            for msg in messages:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO messages
                    (message_id, thread_id, date, sender, recipients, subject,
                     labels, is_unread, has_attachments, snippet, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        msg.get("message_id"),
                        msg.get("thread_id"),
                        msg.get("date"),
                        msg.get("sender"),
                        msg.get("recipients"),
                        msg.get("subject"),
                        json.dumps(msg.get("labels", [])),
                        1 if msg.get("is_unread") else 0,
                        1 if msg.get("has_attachments") else 0,
                        msg.get("snippet"),
                        fetched_at,
                    ),
                )

            conn.execute(
                """
                INSERT OR REPLACE INTO cache_metadata (key, value)
                VALUES ('last_fetch', ?)
                """,
                (fetched_at,),
            )

            conn.commit()

        return len(messages)

    def get_cached_messages(
        self, since_days: Optional[int] = None
    ) -> list[dict[str, Any]]:
        """
        Get cached messages.

        Args:
            since_days: Only return messages from the last N days.

        Returns:
            List of message dictionaries.
        """
        with self._get_connection() as conn:
            if since_days:
                cutoff = (datetime.utcnow() - timedelta(days=since_days)).isoformat()
                cursor = conn.execute(
                    """
                    SELECT * FROM messages
                    WHERE date >= ?
                    ORDER BY date DESC
                    """,
                    (cutoff,),
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT * FROM messages
                    ORDER BY date DESC
                    """
                )

            messages = []
            for row in cursor:
                msg = dict(row)
                msg["labels"] = json.loads(msg["labels"])
                msg["is_unread"] = bool(msg["is_unread"])
                msg["has_attachments"] = bool(msg["has_attachments"])
                messages.append(msg)

            return messages

    def get_message(self, message_id: str) -> Optional[dict[str, Any]]:
        """
        Get a single cached message.

        Args:
            message_id: The message ID to retrieve.

        Returns:
            Message dictionary or None if not found.
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM messages WHERE message_id = ?", (message_id,)
            )
            row = cursor.fetchone()

            if row:
                msg = dict(row)
                msg["labels"] = json.loads(msg["labels"])
                msg["is_unread"] = bool(msg["is_unread"])
                msg["has_attachments"] = bool(msg["has_attachments"])
                return msg

            return None

    def cache_labels(self, labels: list[dict[str, Any]]) -> int:
        """
        Cache label information.

        Args:
            labels: List of label dictionaries.

        Returns:
            Number of labels cached.
        """
        fetched_at = datetime.utcnow().isoformat()

        with self._get_connection() as conn:
            for label in labels:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO labels
                    (label_id, name, type, messages_total, messages_unread, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        label.get("id"),
                        label.get("name"),
                        label.get("type"),
                        label.get("messagesTotal", 0),
                        label.get("messagesUnread", 0),
                        fetched_at,
                    ),
                )
            conn.commit()

        return len(labels)

    def get_cached_labels(self) -> list[dict[str, Any]]:
        """
        Get cached labels.

        Returns:
            List of label dictionaries.
        """
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM labels ORDER BY name")
            return [dict(row) for row in cursor]

    def get_label_id_to_name_map(self) -> dict[str, str]:
        """
        Get a mapping of label IDs to human-readable names.

        Returns:
            Dictionary mapping label_id to name.
        """
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT label_id, name FROM labels")
            return {row["label_id"]: row["name"] for row in cursor}

    def is_fresh(self, max_age_hours: int = 1) -> bool:
        """
        Check if cache is fresh enough.

        Args:
            max_age_hours: Maximum age in hours for cache to be considered fresh.

        Returns:
            True if cache is fresh, False otherwise.
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT value FROM cache_metadata WHERE key = 'last_fetch'"
            )
            row = cursor.fetchone()

            if not row:
                return False

            try:
                last_fetch = datetime.fromisoformat(row["value"])
                age = datetime.utcnow() - last_fetch
                return age < timedelta(hours=max_age_hours)
            except (ValueError, TypeError):
                return False

    def get_message_count(self) -> int:
        """Get the total number of cached messages."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) as count FROM messages")
            row = cursor.fetchone()
            return row["count"] if row else 0

    def clear(self) -> None:
        """Clear all cached data."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM messages")
            conn.execute("DELETE FROM labels")
            conn.execute("DELETE FROM cache_metadata")
            conn.commit()

    def clear_labels(self) -> None:
        """Clear only the labels table."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM labels")
            conn.commit()

    def clear_messages(self) -> None:
        """Clear only the messages table."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM messages")
            conn.commit()

    def delete_messages(self, message_ids: list[str]) -> int:
        """
        Delete messages from cache.

        Args:
            message_ids: List of message IDs to delete.

        Returns:
            Number of messages deleted.
        """
        with self._get_connection() as conn:
            placeholders = ",".join("?" * len(message_ids))
            cursor = conn.execute(
                f"DELETE FROM messages WHERE message_id IN ({placeholders})",
                message_ids,
            )
            conn.commit()
            return cursor.rowcount
