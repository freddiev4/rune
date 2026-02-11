# AGENTS.md

This file is a map for AI agents working in this repository. It covers the essentials — project identity, conventions, and pointers to deeper documentation. Keep this file concise; detailed specs live closer to the code they describe.

## Project Overview

Rune is a Python-based coding agent framework with a Rich/prompt_toolkit TUI, supporting OpenAI and Anthropic models. Entry point: `rune/cli/main.py`. Core runtime: `rune/harness/`.

## Quick Reference

| What                  | Where                                         |
|-----------------------|-----------------------------------------------|
| Project config & deps | `pyproject.toml`                              |
| CLI & TUI spec        | `docs/cli.md`                                 |
| Skills system         | `docs/skills.md`                              |
| Agent skills          | `.agents/skills/`                             |
| Tests                 | `rune/tests/`                                 |
| Feature docs          | `docs/<feature>/`                             |
| CI / publish          | `.github/workflows/publish-package.yml`       |

## Code Layout

```
rune/
├── cli/            # TUI, input widget, CLI entry point
├── harness/        # Agent loop, session, tools, providers, skills, MCP, permissions
├── tests/          # pytest suite
├── agents.py       # Agent type definitions (build, plan, subagent)
└── utils.py        # Shared utilities
```

## Development Environment

- **Python**: >=3.10 (see `pyproject.toml` for exact bounds)
- **Package manager**: Always use `uv`. Work inside a virtualenv.
- **TypeScript projects**: Use `bun`.

```bash
uv venv && source .venv/bin/activate && uv pip install -e ".[dev]"
```

## Linting & Formatting

Ruff is the sole linter. Configuration lives in `pyproject.toml` under `[tool.ruff]`.

```bash
ruff check .          # lint
ruff check --fix .    # auto-fix
```

Rules enabled: `E` (pycodestyle), `F` (pyflakes), `I` (isort), `TID` (tidy-imports). Relative imports are banned — use absolute imports everywhere.

## Testing

```bash
pytest rune/tests/ -v
```

Tests live in `rune/tests/`. See `test_skills.py` (41 tests) and `test_agents_md.py` for existing coverage. Always run relevant tests before pushing.

## Git Workflow

1. Create a feature branch from `main`.
2. Commit after each logical unit of work with a descriptive message.
3. Push to remote.
4. If `gh` CLI is available, open a pull request.

## Tracking Work

For any new feature or piece of work, create a `docs/<feature>/` folder containing:

- `plan.md` — planning and design decisions
- `todo.md` — task tracking
- `docs.md` — setup, how it works, references

## Skills System

Rune uses progressive disclosure for agent skills. The skills list is always in the system prompt; full content loads on-demand when mentioned via `$skill-name` or `[$skill-name](path)`.

See `docs/skills.md` for the full design, activation methods, and API.

## Key Conventions

- **Dependencies**: Prefer stable, well-known libraries that agents can reason about. See `pyproject.toml` for current deps.
- **Imports**: Absolute only (enforced by ruff `TID` rule).
- **Agent types**: `build` (full access), `plan` (read-only), `subagent` (no nesting). Defined in `rune/agents.py`.
- **Tools**: 15 built-in tools covering file ops, shell, web, and organization. Defined in `rune/harness/tools.py`.
