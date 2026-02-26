"""Tests for SQLite session storage (SessionStore)."""

import json
import pytest

from rune.harness.session import Session, Message, UsageStats
from rune.harness.store import SessionStore, _derive_title


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def store(tmp_path):
    """A SessionStore backed by a temp file (not ~/.rune/sessions.db)."""
    s = SessionStore(db_path=str(tmp_path / "test.db"))
    yield s
    s.close()


def _make_session(
    working_dir="/tmp",
    system_prompt="You are helpful.",
    parent_session_id=None,
) -> Session:
    """Create a minimal session for testing."""
    sess = Session(working_dir=working_dir, system_prompt=system_prompt)
    sess.parent_session_id = parent_session_id
    return sess


# ---------------------------------------------------------------------------
# Schema / initialization
# ---------------------------------------------------------------------------

class TestInit:
    def test_creates_db_file(self, tmp_path):
        db = tmp_path / "sub" / "sessions.db"
        s = SessionStore(db_path=str(db))
        s.close()
        assert db.exists()

    def test_idempotent_migration(self, tmp_path):
        """Opening the same DB twice doesn't raise."""
        path = str(tmp_path / "sessions.db")
        s1 = SessionStore(db_path=path)
        s1.close()
        s2 = SessionStore(db_path=path)
        s2.close()


# ---------------------------------------------------------------------------
# save_session / load_session round-trip
# ---------------------------------------------------------------------------

class TestSaveLoad:
    def test_save_and_load_basic(self, store):
        sess = _make_session()
        store.save_session(sess)

        loaded = store.load_session(sess.session_id)
        assert loaded.session_id == sess.session_id
        assert loaded.working_dir == sess.working_dir
        assert loaded.system_prompt == sess.system_prompt
        assert loaded.turn_count == sess.turn_count

    def test_load_missing_raises_key_error(self, store):
        with pytest.raises(KeyError, match="notarealid"):
            store.load_session("notarealid")

    def test_messages_round_trip(self, store):
        sess = _make_session()
        sess.add_user_message("hello")
        sess.add_assistant_message(content="hi there")
        sess.add_tool_result("tc1", "read_file", "file contents")
        store.save_session(sess)

        loaded = store.load_session(sess.session_id)
        assert len(loaded.messages) == len(sess.messages)
        assert loaded.messages[0].role == "system"
        assert loaded.messages[1].role == "user"
        assert loaded.messages[1].content == "hello"
        assert loaded.messages[2].role == "assistant"
        assert loaded.messages[2].content == "hi there"
        assert loaded.messages[3].role == "tool"
        assert loaded.messages[3].tool_call_id == "tc1"
        assert loaded.messages[3].name == "read_file"

    def test_tool_calls_serialized(self, store):
        sess = _make_session()
        tool_calls = [{"id": "tc1", "type": "function",
                       "function": {"name": "shell", "arguments": '{"cmd":"ls"}'}}]
        sess.add_assistant_message(content=None, tool_calls=tool_calls)
        store.save_session(sess)

        loaded = store.load_session(sess.session_id)
        assert loaded.messages[1].tool_calls == tool_calls

    def test_usage_stats_round_trip(self, store):
        sess = _make_session()
        sess.record_usage(prompt_tokens=100, completion_tokens=50)
        store.save_session(sess)

        loaded = store.load_session(sess.session_id)
        assert loaded.usage.prompt_tokens == 100
        assert loaded.usage.completion_tokens == 50
        assert loaded.usage.total_tokens == 150

    def test_upsert_updates_existing(self, store):
        sess = _make_session()
        store.save_session(sess)

        sess.add_user_message("updated")
        sess.record_usage(prompt_tokens=10)
        store.save_session(sess)

        loaded = store.load_session(sess.session_id)
        assert loaded.usage.prompt_tokens == 10
        # messages updated
        assert any(m.content == "updated" for m in loaded.messages)

    def test_title_preserved_on_upsert(self, store):
        """Title set from first user message is not overwritten on re-save."""
        sess = _make_session()
        sess.add_user_message("first user message")
        store.save_session(sess)

        # Save again without a user message change
        store.save_session(sess)

        loaded = store.load_session(sess.session_id)
        assert loaded.messages[1].content == "first user message"
        # Verify title in DB
        rows = store.list_sessions()
        assert rows[0]["title"] == "first user message"


# ---------------------------------------------------------------------------
# Parent-child relationships
# ---------------------------------------------------------------------------

class TestParentChild:
    def test_parent_session_id_stored(self, store):
        parent = _make_session()
        child = _make_session(parent_session_id=parent.session_id)

        store.save_session(parent)
        store.save_session(child)

        loaded_child = store.load_session(child.session_id)
        assert loaded_child.parent_session_id == parent.session_id

    def test_child_session_ids_populated_on_load(self, store):
        parent = _make_session()
        child1 = _make_session(parent_session_id=parent.session_id)
        child2 = _make_session(parent_session_id=parent.session_id)

        store.save_session(parent)
        store.save_session(child1)
        store.save_session(child2)

        loaded_parent = store.load_session(parent.session_id)
        assert set(loaded_parent.child_session_ids) == {
            child1.session_id, child2.session_id
        }

    def test_delete_parent_cascades_to_children(self, store):
        parent = _make_session()
        child = _make_session(parent_session_id=parent.session_id)

        store.save_session(parent)
        store.save_session(child)

        store.delete_session(parent.session_id)

        with pytest.raises(KeyError):
            store.load_session(parent.session_id)
        with pytest.raises(KeyError):
            store.load_session(child.session_id)


# ---------------------------------------------------------------------------
# list_sessions
# ---------------------------------------------------------------------------

class TestListSessions:
    def test_returns_empty_list_when_no_sessions(self, store):
        assert store.list_sessions() == []

    def test_returns_sessions_ordered_by_updated_at_desc(self, store):
        s1 = _make_session()
        s2 = _make_session()
        store.save_session(s1)
        store.save_session(s2)
        # Save s1 again so its updated_at is newer
        store.save_session(s1)

        rows = store.list_sessions()
        assert rows[0]["session_id"] == s1.session_id

    def test_limit_respected(self, store):
        for _ in range(5):
            store.save_session(_make_session())
        assert len(store.list_sessions(limit=3)) == 3

    def test_returned_fields(self, store):
        sess = _make_session()
        sess.add_user_message("a task")
        store.save_session(sess)

        rows = store.list_sessions()
        assert len(rows) == 1
        r = rows[0]
        assert "session_id" in r
        assert "title" in r
        assert "working_dir" in r
        assert "created_at" in r
        assert "updated_at" in r
        assert "turn_count" in r


# ---------------------------------------------------------------------------
# delete_session
# ---------------------------------------------------------------------------

class TestDeleteSession:
    def test_delete_removes_session(self, store):
        sess = _make_session()
        store.save_session(sess)
        store.delete_session(sess.session_id)

        with pytest.raises(KeyError):
            store.load_session(sess.session_id)

    def test_delete_cascades_messages(self, store):
        sess = _make_session()
        sess.add_user_message("hi")
        store.save_session(sess)
        store.delete_session(sess.session_id)

        # Messages should be gone (FK cascade)
        rows = store._conn.execute(
            "SELECT * FROM messages WHERE session_id=?", (sess.session_id,)
        ).fetchall()
        assert rows == []

    def test_delete_nonexistent_is_silent(self, store):
        store.delete_session("does-not-exist")  # should not raise


# ---------------------------------------------------------------------------
# _derive_title helper
# ---------------------------------------------------------------------------

class TestDeriveTitle:
    def test_returns_none_with_no_user_message(self):
        sess = _make_session()
        assert _derive_title(sess) is None

    def test_returns_first_user_message(self):
        sess = _make_session()
        sess.add_user_message("implement the login feature")
        assert _derive_title(sess) == "implement the login feature"

    def test_truncates_to_60_chars(self):
        sess = _make_session()
        long_msg = "a" * 100
        sess.add_user_message(long_msg)
        assert len(_derive_title(sess)) == 60

    def test_strips_newlines(self):
        sess = _make_session()
        sess.add_user_message("first line\nsecond line")
        title = _derive_title(sess)
        assert "\n" not in title

    def test_skips_system_message(self):
        sess = _make_session(system_prompt="you are helpful")
        # system message is first, no user message yet
        assert _derive_title(sess) is None
