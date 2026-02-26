"""SQLite-backed session persistence for Rune.

Sessions are stored in ~/.rune/sessions.db and automatically saved
after every turn.
"""

import json
import os
import sqlite3
from datetime import datetime, timezone

from rune.harness.session import Session, Message, UsageStats

DB_PATH = os.path.expanduser("~/.rune/sessions.db")
SCHEMA_VERSION = 1

_SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sessions (
    session_id        TEXT PRIMARY KEY,
    parent_session_id TEXT REFERENCES sessions(session_id),
    working_dir       TEXT NOT NULL,
    system_prompt     TEXT NOT NULL DEFAULT '',
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL,
    turn_count        INTEGER NOT NULL DEFAULT 0,
    prompt_tokens     INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens      INTEGER NOT NULL DEFAULT 0,
    title             TEXT
);

CREATE INDEX IF NOT EXISTS idx_sessions_updated_at ON sessions(updated_at DESC);

CREATE TABLE IF NOT EXISTS messages (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id    TEXT    NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    msg_order     INTEGER NOT NULL,
    role          TEXT    NOT NULL,
    content       TEXT,
    tool_calls    TEXT,
    tool_call_id  TEXT,
    name          TEXT,
    UNIQUE(session_id, msg_order)
);

CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, msg_order);
"""


def _derive_title(session: Session) -> str | None:
    """Derive a session title from the first user message.

    Returns the first 60 characters of the first user message's content,
    with newlines stripped. Returns None if no user message exists yet.
    """
    for msg in session.messages:
        if msg.role == "user" and msg.content:
            title = msg.content.replace("\n", " ").strip()
            return title[:60]
    return None


class SessionStore:
    """SQLite-backed store for Rune sessions.

    Sessions are persisted to ~/.rune/sessions.db (or a custom path)
    and can be listed, loaded, and resumed.
    """

    def __init__(self, db_path: str = DB_PATH):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self) -> None:
        """Initialize or migrate the schema."""
        cur = self._conn.execute("PRAGMA user_version")
        version = cur.fetchone()[0]
        if version < SCHEMA_VERSION:
            self._conn.executescript(_SCHEMA_SQL)
            self._conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            self._conn.commit()
        else:
            self._conn.execute("PRAGMA foreign_keys = ON")

    def save_session(self, session: Session) -> None:
        """Upsert a session and all its messages."""
        now = datetime.now(timezone.utc).isoformat()
        title = _derive_title(session)
        created_at = session.created_at.isoformat()

        with self._conn:
            self._conn.execute(
                """
                INSERT INTO sessions (
                    session_id, parent_session_id, working_dir, system_prompt,
                    created_at, updated_at, turn_count, prompt_tokens,
                    completion_tokens, total_tokens, title
                )
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(session_id) DO UPDATE SET
                    updated_at=excluded.updated_at,
                    turn_count=excluded.turn_count,
                    prompt_tokens=excluded.prompt_tokens,
                    completion_tokens=excluded.completion_tokens,
                    total_tokens=excluded.total_tokens,
                    title=COALESCE(sessions.title, excluded.title)
                """,
                (
                    session.session_id,
                    session.parent_session_id,
                    session.working_dir,
                    session.system_prompt,
                    created_at,
                    now,
                    session.turn_count,
                    session.usage.prompt_tokens,
                    session.usage.completion_tokens,
                    session.usage.total_tokens,
                    title,
                ),
            )

            # Delete and re-insert messages (simpler than diffing)
            self._conn.execute(
                "DELETE FROM messages WHERE session_id=?", (session.session_id,)
            )
            for i, msg in enumerate(session.messages):
                self._conn.execute(
                    """
                    INSERT INTO messages (
                        session_id, msg_order, role, content,
                        tool_calls, tool_call_id, name
                    )
                    VALUES (?,?,?,?,?,?,?)
                    """,
                    (
                        session.session_id,
                        i,
                        msg.role,
                        msg.content,
                        json.dumps(msg.tool_calls) if msg.tool_calls else None,
                        msg.tool_call_id,
                        msg.name,
                    ),
                )

    def load_session(self, session_id: str) -> Session:
        """Load a session by ID.

        Raises KeyError if the session is not found.
        """
        row = self._conn.execute(
            "SELECT * FROM sessions WHERE session_id=?", (session_id,)
        ).fetchone()
        if not row:
            raise KeyError(f"Session {session_id!r} not found")

        # Reconstruct UsageStats
        usage = UsageStats(
            prompt_tokens=row["prompt_tokens"],
            completion_tokens=row["completion_tokens"],
            total_tokens=row["total_tokens"],
        )

        # Build Session without triggering __post_init__ side effects
        session = Session.__new__(Session)
        session.session_id = row["session_id"]
        session.parent_session_id = row["parent_session_id"]
        session.working_dir = row["working_dir"]
        session.system_prompt = row["system_prompt"]
        session.created_at = datetime.fromisoformat(row["created_at"])
        session.turn_count = row["turn_count"]
        session.usage = usage
        session.messages = []
        session.child_session_ids = []

        # Load child session IDs
        child_rows = self._conn.execute(
            "SELECT session_id FROM sessions WHERE parent_session_id=?",
            (session_id,),
        ).fetchall()
        session.child_session_ids = [r["session_id"] for r in child_rows]

        # Load messages
        msg_rows = self._conn.execute(
            """
            SELECT role, content, tool_calls, tool_call_id, name
            FROM messages
            WHERE session_id=?
            ORDER BY msg_order
            """,
            (session_id,),
        ).fetchall()

        for msg_row in msg_rows:
            tool_calls = None
            if msg_row["tool_calls"] is not None:
                tool_calls = json.loads(msg_row["tool_calls"])
            session.messages.append(
                Message(
                    role=msg_row["role"],
                    content=msg_row["content"],
                    tool_calls=tool_calls,
                    tool_call_id=msg_row["tool_call_id"],
                    name=msg_row["name"],
                )
            )

        return session

    def list_sessions(self, limit: int = 20) -> list[dict]:
        """Return recent sessions as dicts.

        Keys: session_id, title, working_dir, created_at, updated_at, turn_count.
        Sessions are ordered by updated_at descending.
        """
        rows = self._conn.execute(
            """
            SELECT session_id, title, working_dir, created_at, updated_at, turn_count
            FROM sessions
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def delete_session(self, session_id: str) -> None:
        """Delete a session and all its messages."""
        with self._conn:
            self._conn.execute(
                "DELETE FROM sessions WHERE session_id=?", (session_id,)
            )

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
