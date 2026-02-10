# Documentation: Anthropic Model Support

## Setup

### Dependencies

The `anthropic` SDK is added as a project dependency:

```toml
# pyproject.toml
dependencies = [
  "openai>=1.0.0,<2.0.0",
  "anthropic>=0.39.0,<1.0.0",
  ...
]
```

Install with:

```bash
pip install -e .
```

### Environment Variables

Each provider reads its API key from the standard environment variable:

| Provider | Environment Variable |
|----------|---------------------|
| OpenAI | `OPENAI_API_KEY` |
| Anthropic | `ANTHROPIC_API_KEY` |

## Usage

### CLI

```bash
# OpenAI (explicit provider prefix)
rune --model openai/gpt-5.2-2025-12-11

# OpenAI (implicit — bare name defaults to openai)
rune --model gpt-4o

# Anthropic
rune --model anthropic/claude-sonnet-4-20250514
rune --model anthropic/claude-opus-4-20250514
```

### Programmatic

```python
from rune.harness.agent import Agent, AgentConfig

agent = Agent(AgentConfig(model="anthropic/claude-sonnet-4-20250514"))
```

## How It Works

### Architecture

```
CLI (--model provider/model)
    |
    v
AgentConfig.model = "anthropic/claude-sonnet-4-20250514"
    |
    v
create_provider(model_string)
    |-- parse_model_string() -> ("anthropic", "claude-sonnet-4-20250514")
    |-- AnthropicProvider() or OpenAIProvider()
    v
Provider.chat(model, messages, tools, ...)
    |-- Convert messages to provider format
    |-- Call native SDK
    |-- Normalise response -> ChatResponse
    v
Agent loop (provider-agnostic)
```

### Provider Abstraction (`rune/harness/providers.py`)

The module contains:

- **Normalised types** — `ChatResponse`, `Choice`, `ChatMessage`, `ToolCall`, `FunctionCall`, `Usage`. These mirror the OpenAI response shape so the agent loop doesn't need to change.
- **`Provider` base class** — defines the `chat()` interface.
- **`OpenAIProvider`** — thin wrapper; calls `client.chat.completions.create()` and normalises the response.
- **`AnthropicProvider`** — handles all format conversion:
  - `_convert_messages()` — extracts system messages, converts tool calls to content blocks, groups tool results, enforces alternation.
  - `_convert_tools()` — converts OpenAI tool schemas to Anthropic's `input_schema` format.
  - `_normalise()` — converts Anthropic's content-block response into the common `ChatResponse`.

### Message Format Conversion

The internal message format (OpenAI-style) is converted to Anthropic's format on each API call:

| OpenAI Format | Anthropic Format |
|--------------|-----------------|
| `{"role": "system", "content": "..."}` | Extracted into `system` parameter |
| `{"role": "assistant", "tool_calls": [...]}` | `{"role": "assistant", "content": [{"type": "tool_use", ...}]}` |
| `{"role": "tool", "tool_call_id": "..."}` | Grouped into `{"role": "user", "content": [{"type": "tool_result", ...}]}` |

### Tool Definition Conversion

| OpenAI | Anthropic |
|--------|-----------|
| `{"type": "function", "function": {"name": "...", "parameters": {...}}}` | `{"name": "...", "input_schema": {...}}` |

## References

- [Anthropic Python SDK](https://github.com/anthropics/anthropic-sdk-python)
- [Anthropic Tool Use docs](https://docs.anthropic.com/en/docs/build-with-claude/tool-use/overview)
- [Anthropic Messages API](https://docs.anthropic.com/en/api/messages)
- [OpenAI Chat Completions API](https://platform.openai.com/docs/api-reference/chat)
