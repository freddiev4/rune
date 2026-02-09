# Plan: Add Anthropic Model Support

**Issue:** [#1 — Add support for Anthropic models](https://github.com/freddiev4/rune/issues/1)
**Date:** 2026-02-09
**Status:** Complete

## Goal

Enable rune to use Anthropic models (Claude) alongside OpenAI models, using native SDKs (no wrappers like litellm). Models are selected via a `provider/model-name` format.

## Design Decisions

### Provider/model string format

Models are specified as `provider/model-name`:

- `openai/gpt-5.2-2025-12-11`
- `anthropic/claude-sonnet-4-20250514`

Bare model names (no `/`) default to `openai` for backward compatibility.

### Native SDKs only

Each provider uses its own official SDK:

- `openai` Python package for OpenAI models
- `anthropic` Python package for Anthropic models

No wrapper libraries (litellm, etc.) are used.

### Provider abstraction layer

A thin `Provider` base class normalises both APIs into a common `ChatResponse` type. This keeps the agent loop provider-agnostic — it only sees normalised responses.

### Internal message format

Messages are stored in OpenAI's format internally (the existing `Session` class). The Anthropic provider converts on the fly when making API calls. This avoids changing the session/persistence layer.

## Key Challenges

1. **Message format differences** — Anthropic requires system messages as a separate parameter, tool calls as content blocks, tool results grouped into user messages, and strict user/assistant alternation.
2. **Tool definition format** — OpenAI uses `parameters` inside a `function` wrapper; Anthropic uses `input_schema` at the top level.
3. **Response normalisation** — Anthropic returns content blocks (text + tool_use); these are flattened into the normalised format the agent loop expects.

## Files Changed

| File | Change |
|------|--------|
| `rune/harness/providers.py` | New — provider abstraction with OpenAI + Anthropic implementations |
| `rune/harness/agent.py` | Replaced direct `OpenAI()` client with `create_provider()` |
| `rune/cli/main.py` | Updated `--model` flag default and help text |
| `pyproject.toml` | Added `anthropic` dependency |
