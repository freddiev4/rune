"""Provider abstraction for LLM API clients.

Supports OpenAI and Anthropic models via their native SDKs. The model string
uses a ``provider/model-name`` format:

    openai/gpt-5.2-2025-12-11
    anthropic/claude-sonnet-4-20250514

If no provider prefix is given the default is ``openai``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any  # noqa: I001

# ---------------------------------------------------------------------------
# Normalised response types
# ---------------------------------------------------------------------------

@dataclass
class FunctionCall:
    name: str
    arguments: str  # JSON string


@dataclass
class ToolCall:
    id: str
    type: str  # "function"
    function: FunctionCall


@dataclass
class ChatMessage:
    content: str | None = None
    tool_calls: list[ToolCall] | None = None


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass
class Choice:
    message: ChatMessage = field(default_factory=ChatMessage)


@dataclass
class ChatResponse:
    choices: list[Choice] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_model_string(model: str) -> tuple[str, str]:
    """Parse ``provider/model-name`` into ``(provider, model_name)``.

    If the string has no ``/`` prefix, ``openai`` is assumed.
    """
    if "/" in model:
        provider, _, model_name = model.partition("/")
        provider = provider.lower().strip()
        model_name = model_name.strip()
        if provider not in ("openai", "anthropic"):
            raise ValueError(
                f"Unknown provider {provider!r}. Supported: openai, anthropic"
            )
        return provider, model_name
    return "openai", model


# ---------------------------------------------------------------------------
# Provider interface
# ---------------------------------------------------------------------------

class Provider:
    """Base class for LLM providers."""

    provider_name: str = ""

    def chat(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str = "auto",
        temperature: float = 0.0,
        max_completion_tokens: int = 4096,
    ) -> ChatResponse:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# OpenAI provider
# ---------------------------------------------------------------------------

class OpenAIProvider(Provider):
    provider_name = "openai"

    def __init__(self) -> None:
        from openai import OpenAI
        self.client = OpenAI()

    def chat(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str = "auto",
        temperature: float = 0.0,
        max_completion_tokens: int = 4096,
    ) -> ChatResponse:
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_completion_tokens": max_completion_tokens,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice

        resp = self.client.chat.completions.create(**kwargs)
        return self._normalise(resp)

    @staticmethod
    def _normalise(resp: Any) -> ChatResponse:
        msg = resp.choices[0].message
        tool_calls = None
        if msg.tool_calls:
            tool_calls = [
                ToolCall(
                    id=tc.id,
                    type="function",
                    function=FunctionCall(
                        name=tc.function.name,
                        arguments=tc.function.arguments,
                    ),
                )
                for tc in msg.tool_calls
            ]
        message = ChatMessage(
            content=msg.content, tool_calls=tool_calls,
        )
        return ChatResponse(
            choices=[Choice(message=message)],
            usage=Usage(
                prompt_tokens=getattr(resp.usage, "prompt_tokens", 0) or 0,
                completion_tokens=getattr(resp.usage, "completion_tokens", 0) or 0,
            ),
        )


# ---------------------------------------------------------------------------
# Anthropic provider
# ---------------------------------------------------------------------------

class AnthropicProvider(Provider):
    provider_name = "anthropic"

    def __init__(self) -> None:
        from anthropic import Anthropic
        self.client = Anthropic()

    # -- public interface --------------------------------------------------

    def chat(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str = "auto",
        temperature: float = 0.0,
        max_completion_tokens: int = 4096,
    ) -> ChatResponse:
        system_text, converted_messages = self._convert_messages(messages)
        converted_tools = self._convert_tools(tools or [])

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": converted_messages,
            "max_tokens": max_completion_tokens,
            "temperature": temperature,
        }
        if system_text:
            kwargs["system"] = system_text
        if converted_tools:
            kwargs["tools"] = converted_tools
            kwargs["tool_choice"] = {"type": tool_choice}

        resp = self.client.messages.create(**kwargs)
        return self._normalise(resp)

    # -- message conversion ------------------------------------------------

    @staticmethod
    def _convert_messages(
        messages: list[dict[str, Any]],
    ) -> tuple[str, list[dict[str, Any]]]:
        """Convert OpenAI-format messages to Anthropic format.

        Returns (system_text, messages).

        Key differences handled:
        - System messages are extracted into a single ``system`` parameter.
        - Assistant messages with ``tool_calls`` become content blocks.
        - Consecutive ``tool`` role messages are grouped into a single
          ``user`` message with ``tool_result`` content blocks.
        """
        system_parts: list[str] = []
        anthropic_msgs: list[dict[str, Any]] = []

        i = 0
        while i < len(messages):
            msg = messages[i]
            role = msg["role"]

            if role == "system":
                if msg.get("content"):
                    system_parts.append(msg["content"])
                i += 1
                continue

            if role == "user":
                anthropic_msgs.append({"role": "user", "content": msg["content"]})
                i += 1
                continue

            if role == "assistant":
                content_blocks: list[dict[str, Any]] = []
                text = msg.get("content")
                if text:
                    content_blocks.append({"type": "text", "text": text})
                if msg.get("tool_calls"):
                    for tc in msg["tool_calls"]:
                        fn = tc["function"]
                        try:
                            tool_input = json.loads(fn["arguments"])
                        except (json.JSONDecodeError, TypeError):
                            tool_input = {}
                        content_blocks.append({
                            "type": "tool_use",
                            "id": tc["id"],
                            "name": fn["name"],
                            "input": tool_input,
                        })
                if content_blocks:
                    anthropic_msgs.append({
                        "role": "assistant",
                        "content": content_blocks,
                    })
                else:
                    # Empty assistant message — include with empty text
                    anthropic_msgs.append({
                        "role": "assistant",
                        "content": [{"type": "text", "text": ""}],
                    })
                i += 1
                continue

            if role == "tool":
                # Gather consecutive tool results into one user message.
                tool_results: list[dict[str, Any]] = []
                while i < len(messages) and messages[i]["role"] == "tool":
                    tmsg = messages[i]
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tmsg["tool_call_id"],
                        "content": tmsg.get("content") or "",
                    })
                    i += 1
                anthropic_msgs.append({"role": "user", "content": tool_results})
                continue

            # Unknown role — skip.
            i += 1

        # Anthropic requires the first message to be from "user". If not,
        # insert a synthetic user turn.
        if anthropic_msgs and anthropic_msgs[0]["role"] != "user":
            anthropic_msgs.insert(0, {"role": "user", "content": "Hello."})

        # Anthropic requires strictly alternating user/assistant messages.
        # Merge consecutive same-role messages.
        merged: list[dict[str, Any]] = []
        for msg in anthropic_msgs:
            if merged and merged[-1]["role"] == msg["role"]:
                prev_content = merged[-1]["content"]
                cur_content = msg["content"]
                # Convert to list form if needed
                if isinstance(prev_content, str):
                    prev_content = [{"type": "text", "text": prev_content}]
                if isinstance(cur_content, str):
                    cur_content = [{"type": "text", "text": cur_content}]
                merged[-1]["content"] = prev_content + cur_content
            else:
                merged.append(msg)

        return "\n\n".join(system_parts), merged

    # -- tool definition conversion ----------------------------------------

    @staticmethod
    def _convert_tools(
        tools: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Convert OpenAI tool definitions to Anthropic format."""
        result = []
        for tool_def in tools:
            if tool_def.get("type") != "function":
                continue
            fn = tool_def["function"]
            result.append({
                "name": fn["name"],
                "description": fn.get("description", ""),
                "input_schema": fn.get(
                    "parameters",
                    {"type": "object", "properties": {}},
                ),
            })
        return result

    # -- response normalisation --------------------------------------------

    @staticmethod
    def _normalise(resp: Any) -> ChatResponse:
        """Convert an Anthropic response to the normalised ``ChatResponse``."""
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []

        for block in resp.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.id,
                        type="function",
                        function=FunctionCall(
                            name=block.name,
                            arguments=json.dumps(block.input),
                        ),
                    )
                )

        content = "\n".join(text_parts) if text_parts else None
        return ChatResponse(
            choices=[
                Choice(
                    message=ChatMessage(
                        content=content,
                        tool_calls=tool_calls if tool_calls else None,
                    )
                )
            ],
            usage=Usage(
                prompt_tokens=getattr(resp.usage, "input_tokens", 0) or 0,
                completion_tokens=getattr(resp.usage, "output_tokens", 0) or 0,
            ),
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def create_provider(model_string: str) -> tuple[Provider, str]:
    """Create a provider from a ``provider/model`` string.

    Returns ``(provider_instance, model_name)``.
    """
    provider_name, model_name = parse_model_string(model_string)
    if provider_name == "anthropic":
        return AnthropicProvider(), model_name
    return OpenAIProvider(), model_name
