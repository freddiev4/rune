"""Tests for provider reasoning/thinking support."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from rune.harness.providers import (
    AnthropicProvider,
    ChatMessage,
    ChatResponse,
    Choice,
    FunctionCall,
    OpenAIProvider,
    ReasoningConfig,
    ToolCall,
    Usage,
    create_provider,
    parse_model_string,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_openai_response(
    content: str | None = "hello",
    tool_calls: list | None = None,
) -> MagicMock:
    """Build a minimal mock that looks like an openai ChatCompletion."""
    msg = MagicMock()
    msg.content = content
    msg.tool_calls = tool_calls or []
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    resp.usage.prompt_tokens = 10
    resp.usage.completion_tokens = 5
    return resp


def _make_anthropic_block(type_: str, **kwargs: Any) -> MagicMock:
    block = MagicMock()
    block.type = type_
    for k, v in kwargs.items():
        setattr(block, k, v)
    return block


def _make_anthropic_response(blocks: list[MagicMock]) -> MagicMock:
    resp = MagicMock()
    resp.content = blocks
    resp.usage.input_tokens = 20
    resp.usage.output_tokens = 8
    return resp


# ---------------------------------------------------------------------------
# parse_model_string
# ---------------------------------------------------------------------------

class TestParseModelString:
    def test_explicit_openai(self):
        assert parse_model_string("openai/gpt-4o") == ("openai", "gpt-4o")

    def test_explicit_anthropic(self):
        assert parse_model_string("anthropic/claude-3-5-sonnet") == (
            "anthropic",
            "claude-3-5-sonnet",
        )

    def test_bare_model_defaults_to_openai(self):
        assert parse_model_string("gpt-4o") == ("openai", "gpt-4o")

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            parse_model_string("google/gemini-pro")


# ---------------------------------------------------------------------------
# ReasoningConfig
# ---------------------------------------------------------------------------

class TestReasoningConfig:
    def test_defaults(self):
        rc = ReasoningConfig()
        assert rc.effort == "medium"
        assert rc.budget_tokens == 8000

    def test_custom_values(self):
        rc = ReasoningConfig(effort="high", budget_tokens=16000)
        assert rc.effort == "high"
        assert rc.budget_tokens == 16000


# ---------------------------------------------------------------------------
# OpenAIProvider – reasoning model detection
# ---------------------------------------------------------------------------

class TestOpenAIProviderReasoningDetection:
    def setup_method(self):
        with patch("rune.harness.providers.OpenAIProvider.__init__", return_value=None):
            self.provider = OpenAIProvider.__new__(OpenAIProvider)

    @pytest.mark.parametrize("model", ["o1", "o1-mini", "o1-preview", "o3", "o3-mini", "o4-mini"])
    def test_base_o_series_detected(self, model):
        assert self.provider._is_reasoning_model(model) is True

    @pytest.mark.parametrize("model", ["o1-2024-12-17", "o3-mini-2025-01-31", "o4-mini-2025-04-16"])
    def test_dated_o_series_detected(self, model):
        assert self.provider._is_reasoning_model(model) is True

    @pytest.mark.parametrize("model", ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"])
    def test_non_o_series_not_detected(self, model):
        assert self.provider._is_reasoning_model(model) is False


# ---------------------------------------------------------------------------
# OpenAIProvider – chat() parameter passing
# ---------------------------------------------------------------------------

class TestOpenAIProviderChat:
    def setup_method(self):
        self.provider = OpenAIProvider.__new__(OpenAIProvider)
        self.provider.client = MagicMock()

    def test_standard_model_passes_temperature(self):
        mock_resp = _make_openai_response()
        self.provider.client.chat.completions.create.return_value = mock_resp

        self.provider.chat(model="gpt-4o", messages=[], temperature=0.7)

        call_kwargs = self.provider.client.chat.completions.create.call_args[1]
        assert call_kwargs["temperature"] == 0.7
        assert "reasoning_effort" not in call_kwargs

    def test_standard_model_passes_tool_choice(self):
        mock_resp = _make_openai_response()
        self.provider.client.chat.completions.create.return_value = mock_resp
        tools = [{"type": "function", "function": {"name": "f", "description": "", "parameters": {}}}]

        self.provider.chat(model="gpt-4o", messages=[], tools=tools, tool_choice="auto")

        call_kwargs = self.provider.client.chat.completions.create.call_args[1]
        assert call_kwargs["tool_choice"] == "auto"

    def test_o_series_uses_reasoning_effort(self):
        mock_resp = _make_openai_response()
        self.provider.client.chat.completions.create.return_value = mock_resp

        self.provider.chat(
            model="o3-mini",
            messages=[],
            reasoning=ReasoningConfig(effort="high"),
        )

        call_kwargs = self.provider.client.chat.completions.create.call_args[1]
        assert call_kwargs["reasoning_effort"] == "high"
        assert "temperature" not in call_kwargs

    def test_o_series_default_effort_medium(self):
        mock_resp = _make_openai_response()
        self.provider.client.chat.completions.create.return_value = mock_resp

        # No ReasoningConfig – should still pick "medium" for o-series
        self.provider.chat(model="o1", messages=[])

        call_kwargs = self.provider.client.chat.completions.create.call_args[1]
        assert call_kwargs["reasoning_effort"] == "medium"

    def test_o_series_omits_tool_choice(self):
        mock_resp = _make_openai_response()
        self.provider.client.chat.completions.create.return_value = mock_resp
        tools = [{"type": "function", "function": {"name": "f", "description": "", "parameters": {}}}]

        self.provider.chat(model="o3", messages=[], tools=tools)

        call_kwargs = self.provider.client.chat.completions.create.call_args[1]
        assert "tool_choice" not in call_kwargs

    def test_response_normalised(self):
        mock_resp = _make_openai_response(content="world")
        self.provider.client.chat.completions.create.return_value = mock_resp

        result = self.provider.chat(model="gpt-4o", messages=[])

        assert isinstance(result, ChatResponse)
        assert result.choices[0].message.content == "world"
        assert result.usage.prompt_tokens == 10
        assert result.usage.completion_tokens == 5


# ---------------------------------------------------------------------------
# AnthropicProvider – chat() parameter passing
# ---------------------------------------------------------------------------

class TestAnthropicProviderChat:
    def setup_method(self):
        self.provider = AnthropicProvider.__new__(AnthropicProvider)
        self.provider.client = MagicMock()

    def _stub_response(self, blocks=None):
        blocks = blocks or [_make_anthropic_block("text", text="ok")]
        resp = _make_anthropic_response(blocks)
        self.provider.client.messages.create.return_value = resp
        return resp

    def test_no_reasoning_passes_temperature(self):
        self._stub_response()
        self.provider.chat(model="claude-3-5-sonnet", messages=[], temperature=0.5)

        call_kwargs = self.provider.client.messages.create.call_args[1]
        assert call_kwargs["temperature"] == 0.5
        assert "thinking" not in call_kwargs

    def test_reasoning_sets_thinking_and_forces_temp1(self):
        self._stub_response()
        self.provider.chat(
            model="claude-3-7-sonnet",
            messages=[],
            reasoning=ReasoningConfig(budget_tokens=5000),
        )

        call_kwargs = self.provider.client.messages.create.call_args[1]
        assert call_kwargs["thinking"] == {"type": "enabled", "budget_tokens": 5000}
        assert call_kwargs["temperature"] == 1

    def test_reasoning_ignores_caller_temperature(self):
        """temperature kwarg should be overridden to 1 when reasoning is on."""
        self._stub_response()
        self.provider.chat(
            model="claude-3-7-sonnet",
            messages=[],
            temperature=0.0,
            reasoning=ReasoningConfig(budget_tokens=1000),
        )

        call_kwargs = self.provider.client.messages.create.call_args[1]
        assert call_kwargs["temperature"] == 1


# ---------------------------------------------------------------------------
# AnthropicProvider._normalise – thinking blocks
# ---------------------------------------------------------------------------

class TestAnthropicNormalise:
    def test_text_block_only(self):
        resp = _make_anthropic_response([
            _make_anthropic_block("text", text="answer"),
        ])
        result = AnthropicProvider._normalise(resp)
        assert result.choices[0].message.content == "answer"
        assert result.choices[0].message.thinking is None

    def test_thinking_block_extracted(self):
        resp = _make_anthropic_response([
            _make_anthropic_block("thinking", thinking="step 1", signature="sig123"),
            _make_anthropic_block("text", text="final answer"),
        ])
        result = AnthropicProvider._normalise(resp)
        msg = result.choices[0].message
        assert msg.thinking == "step 1"
        assert msg.content == "final answer"

    def test_thinking_blocks_stored_for_roundtrip(self):
        resp = _make_anthropic_response([
            _make_anthropic_block("thinking", thinking="thought", signature="s1"),
            _make_anthropic_block("text", text="done"),
        ])
        result = AnthropicProvider._normalise(resp)
        msg = result.choices[0].message
        blocks = getattr(msg, "_thinking_blocks", None)
        assert blocks is not None
        assert blocks[0] == {"type": "thinking", "thinking": "thought", "signature": "s1"}

    def test_redacted_thinking_block_preserved(self):
        resp = _make_anthropic_response([
            _make_anthropic_block("redacted_thinking", data="opaque_data"),
            _make_anthropic_block("text", text="answer"),
        ])
        result = AnthropicProvider._normalise(resp)
        msg = result.choices[0].message
        blocks = getattr(msg, "_thinking_blocks", None)
        assert blocks is not None
        assert blocks[0] == {"type": "redacted_thinking", "data": "opaque_data"}

    def test_multiple_thinking_blocks_joined(self):
        resp = _make_anthropic_response([
            _make_anthropic_block("thinking", thinking="part 1", signature="s1"),
            _make_anthropic_block("thinking", thinking="part 2", signature="s2"),
            _make_anthropic_block("text", text="result"),
        ])
        result = AnthropicProvider._normalise(resp)
        assert result.choices[0].message.thinking == "part 1\npart 2"

    def test_tool_use_block(self):
        block = _make_anthropic_block(
            "tool_use",
            id="tu_1",
            name="shell",
            input={"command": "ls"},
        )
        resp = _make_anthropic_response([block])
        result = AnthropicProvider._normalise(resp)
        msg = result.choices[0].message
        assert msg.tool_calls is not None
        assert len(msg.tool_calls) == 1
        tc = msg.tool_calls[0]
        assert tc.id == "tu_1"
        assert tc.function.name == "shell"
        assert json.loads(tc.function.arguments) == {"command": "ls"}

    def test_no_thinking_blocks_attr_absent(self):
        resp = _make_anthropic_response([
            _make_anthropic_block("text", text="plain"),
        ])
        result = AnthropicProvider._normalise(resp)
        assert not hasattr(result.choices[0].message, "_thinking_blocks")

    def test_usage_mapped(self):
        resp = _make_anthropic_response([_make_anthropic_block("text", text="")])
        result = AnthropicProvider._normalise(resp)
        assert result.usage.prompt_tokens == 20
        assert result.usage.completion_tokens == 8


# ---------------------------------------------------------------------------
# AnthropicProvider._convert_messages – thinking block round-trip
# ---------------------------------------------------------------------------

class TestAnthropicConvertMessages:
    def test_thinking_blocks_included_in_assistant_turn(self):
        messages = [
            {"role": "user", "content": "hello"},
            {
                "role": "assistant",
                "content": "I thought about it",
                "thinking_blocks": [
                    {"type": "thinking", "thinking": "my thought", "signature": "sig"}
                ],
            },
            {"role": "user", "content": "ok"},
        ]
        _, converted = AnthropicProvider._convert_messages(messages)
        # Find the assistant message
        asst = next(m for m in converted if m["role"] == "assistant")
        types = [b["type"] for b in asst["content"]]
        assert "thinking" in types
        assert "text" in types
        # thinking block comes before text
        assert types.index("thinking") < types.index("text")

    def test_no_thinking_blocks_when_absent(self):
        messages = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ]
        _, converted = AnthropicProvider._convert_messages(messages)
        asst = next(m for m in converted if m["role"] == "assistant")
        types = [b["type"] for b in asst["content"]]
        assert "thinking" not in types

    def test_tool_results_grouped(self):
        messages = [
            {"role": "user", "content": "do it"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {"id": "tc1", "type": "function", "function": {"name": "shell", "arguments": '{"command":"ls"}'}}
                ],
            },
            {"role": "tool", "content": "file.txt", "tool_call_id": "tc1", "name": "shell"},
        ]
        _, converted = AnthropicProvider._convert_messages(messages)
        # Last message should be a user message containing tool_result blocks
        last = converted[-1]
        assert last["role"] == "user"
        assert last["content"][0]["type"] == "tool_result"


# ---------------------------------------------------------------------------
# create_provider factory
# ---------------------------------------------------------------------------

class TestCreateProvider:
    def test_openai_provider(self):
        with patch.object(OpenAIProvider, "__init__", return_value=None):
            provider, model = create_provider("openai/gpt-4o")
        assert isinstance(provider, OpenAIProvider)
        assert model == "gpt-4o"

    def test_anthropic_provider(self):
        with patch.object(AnthropicProvider, "__init__", return_value=None):
            provider, model = create_provider("anthropic/claude-3-5-sonnet")
        assert isinstance(provider, AnthropicProvider)
        assert model == "claude-3-5-sonnet"

    def test_bare_model_defaults_openai(self):
        with patch.object(OpenAIProvider, "__init__", return_value=None):
            provider, model = create_provider("gpt-4o")
        assert isinstance(provider, OpenAIProvider)
        assert model == "gpt-4o"
