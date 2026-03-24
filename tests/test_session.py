"""Tests for Session and Message, including thinking_blocks support."""

from __future__ import annotations

import json
import os
import tempfile

import pytest

from rune.harness.session import Message, Session, UsageStats


# ---------------------------------------------------------------------------
# Message
# ---------------------------------------------------------------------------

class TestMessage:
    def test_basic_to_api_format(self):
        msg = Message(role="user", content="hello")
        d = msg.to_api_format()
        assert d == {"role": "user", "content": "hello"}

    def test_tool_calls_included(self):
        tc = [{"id": "tc1", "type": "function", "function": {"name": "f", "arguments": "{}"}}]
        msg = Message(role="assistant", content=None, tool_calls=tc)
        d = msg.to_api_format()
        assert d["tool_calls"] == tc

    def test_thinking_blocks_included(self):
        blocks = [{"type": "thinking", "thinking": "step", "signature": "sig"}]
        msg = Message(role="assistant", content="answer", thinking_blocks=blocks)
        d = msg.to_api_format()
        assert d["thinking_blocks"] == blocks

    def test_thinking_blocks_omitted_when_none(self):
        msg = Message(role="assistant", content="answer")
        d = msg.to_api_format()
        assert "thinking_blocks" not in d

    def test_tool_result_format(self):
        msg = Message(role="tool", content="result", tool_call_id="tc1", name="shell")
        d = msg.to_api_format()
        assert d["role"] == "tool"
        assert d["tool_call_id"] == "tc1"
        assert d["name"] == "shell"


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------

class TestSession:
    def _make_session(self, system_prompt="You are helpful."):
        return Session(working_dir="/tmp", system_prompt=system_prompt)

    def test_system_prompt_added_on_init(self):
        s = self._make_session("sys")
        assert s.messages[0].role == "system"
        assert s.messages[0].content == "sys"

    def test_add_user_message(self):
        s = self._make_session()
        s.add_user_message("hi")
        assert s.messages[-1].role == "user"
        assert s.messages[-1].content == "hi"
        assert s.turn_count == 1

    def test_add_assistant_message(self):
        s = self._make_session()
        s.add_assistant_message(content="hello")
        msg = s.messages[-1]
        assert msg.role == "assistant"
        assert msg.content == "hello"
        assert msg.thinking_blocks is None

    def test_add_assistant_message_with_thinking_blocks(self):
        s = self._make_session()
        blocks = [{"type": "thinking", "thinking": "reasoning", "signature": "sig"}]
        s.add_assistant_message(content="answer", thinking_blocks=blocks)
        msg = s.messages[-1]
        assert msg.thinking_blocks == blocks

    def test_add_tool_result(self):
        s = self._make_session()
        s.add_tool_result(tool_call_id="tc1", name="shell", result="output")
        msg = s.messages[-1]
        assert msg.role == "tool"
        assert msg.tool_call_id == "tc1"
        assert msg.content == "output"

    def test_get_api_messages_includes_thinking_blocks(self):
        s = self._make_session()
        blocks = [{"type": "thinking", "thinking": "t", "signature": "s"}]
        s.add_user_message("q")
        s.add_assistant_message(content="a", thinking_blocks=blocks)
        api_msgs = s.get_api_messages()
        asst = next(m for m in api_msgs if m["role"] == "assistant")
        assert asst["thinking_blocks"] == blocks

    def test_record_usage(self):
        s = self._make_session()
        s.record_usage(prompt_tokens=10, completion_tokens=5)
        assert s.usage.prompt_tokens == 10
        assert s.usage.completion_tokens == 5
        assert s.usage.total_tokens == 15

    def test_needs_compaction(self):
        s = self._make_session()
        assert not s.needs_compaction(max_messages=5)
        for i in range(6):
            s.add_user_message(f"msg {i}")
        assert s.needs_compaction(max_messages=5)

    def test_compact_keeps_system_and_recent(self):
        s = self._make_session("sys")
        for i in range(20):
            s.add_user_message(f"msg {i}")
        s.compact("summary of work")
        assert s.messages[0].role == "system"
        # compaction marker present
        assert any("summary of work" in (m.content or "") for m in s.messages)
        # at most system + compaction + 10 recent
        assert len(s.messages) <= 12

    def test_fork_creates_child(self):
        s = self._make_session()
        child = s.fork(system_prompt="child sys")
        assert child.parent_session_id == s.session_id
        assert child.session_id in s.child_session_ids
        assert child.messages[0].content == "child sys"

    def test_undo_last_exchange(self):
        s = self._make_session()
        s.add_user_message("first")
        s.add_assistant_message("response")
        s.add_user_message("second")
        removed = s.undo_last_exchange()
        assert removed is True
        assert s.messages[-1].role == "assistant"

    def test_clear_keeps_system_prompt(self):
        s = self._make_session("sys")
        s.add_user_message("hi")
        s.clear()
        assert len(s.messages) == 1
        assert s.messages[0].role == "system"
        assert s.turn_count == 0


# ---------------------------------------------------------------------------
# Session persistence (save/load round-trip)
# ---------------------------------------------------------------------------

class TestSessionPersistence:
    def test_save_load_roundtrip(self):
        s = Session(working_dir="/tmp", system_prompt="sys")
        s.add_user_message("hello")
        blocks = [{"type": "thinking", "thinking": "thought", "signature": "sig"}]
        s.add_assistant_message(content="world", thinking_blocks=blocks)
        s.record_usage(prompt_tokens=5, completion_tokens=3)

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name

        try:
            s.save(path)
            loaded = Session.load(path)

            assert loaded.session_id == s.session_id
            assert loaded.turn_count == s.turn_count
            assert loaded.usage.prompt_tokens == 5
            assert loaded.usage.completion_tokens == 3

            asst = next(m for m in loaded.messages if m.role == "assistant")
            assert asst.thinking_blocks == blocks
        finally:
            os.unlink(path)

    def test_load_without_thinking_blocks_field(self):
        """Older sessions without thinking_blocks should load fine."""
        data = {
            "session_id": "abc",
            "parent_session_id": None,
            "child_session_ids": [],
            "working_dir": "/tmp",
            "system_prompt": "sys",
            "messages": [
                {"role": "user", "content": "hi"},
                {"role": "assistant", "content": "hello"},
            ],
            "created_at": "2025-01-01T00:00:00",
            "turn_count": 1,
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }
        with tempfile.NamedTemporaryFile(
            suffix=".json", mode="w", delete=False
        ) as f:
            json.dump(data, f)
            path = f.name

        try:
            loaded = Session.load(path)
            asst = next(m for m in loaded.messages if m.role == "assistant")
            assert asst.thinking_blocks is None
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# UsageStats
# ---------------------------------------------------------------------------

class TestUsageStats:
    def test_add_accumulates(self):
        u = UsageStats()
        u.add(10, 5)
        u.add(3, 2)
        assert u.prompt_tokens == 13
        assert u.completion_tokens == 7
        assert u.total_tokens == 20

    def test_to_dict(self):
        u = UsageStats(prompt_tokens=1, completion_tokens=2, total_tokens=3)
        assert u.to_dict() == {
            "prompt_tokens": 1,
            "completion_tokens": 2,
            "total_tokens": 3,
        }
