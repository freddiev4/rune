# Todo: Anthropic Model Support

## Completed

- [x] Create `rune/harness/providers.py` with provider abstraction (OpenAI + Anthropic)
- [x] Add `anthropic` dependency to `pyproject.toml`
- [x] Update `rune/harness/agent.py` to use provider abstraction instead of direct OpenAI client
- [x] Update `rune/cli/main.py` for `provider/model` format in `--model` flag
- [x] Verify TUI header displays `provider/model` string
- [x] Install dependencies and verify imports
- [x] Run linter (`ruff check`) on new/changed files
- [x] Run existing test suite (61 passed)
- [x] Commit and push to feature branch

## Future Considerations

- [ ] Add streaming support for Anthropic (currently uses non-streaming `messages.create`)
- [ ] Add `/model` slash command to switch models at runtime in the TUI
- [ ] Add model validation (check if model name is valid before first API call)
- [ ] Add provider-specific error handling (rate limits, auth errors)
- [ ] Support for additional providers (e.g. Google, Mistral) using the same pattern
