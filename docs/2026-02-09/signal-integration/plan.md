# Signal Integration - Implementation Plan

## Goal
Add Signal messaging capability to Rune so agents can send notifications when tasks complete, errors occur, or important milestones are reached.

## Architecture Decision

### Choice: signal-cli + HTTP RPC (like OpenClaw)
**Why?**
- ✅ Battle-tested: OpenClaw uses this successfully
- ✅ Mature: signal-cli is stable and well-maintained
- ✅ Simple: Just HTTP requests, no complex protocol implementation
- ✅ Cross-platform: Works on Linux, macOS, Windows
- ✅ Language-agnostic: HTTP RPC works from any language
- ✅ Official protocol: Uses libsignal (Signal's official library)

**Alternatives considered:**
- ❌ **pysignald**: Requires separate signald daemon (another dependency)
- ❌ **Direct libsignal bindings**: Complex, would need to handle encryption/protocol ourselves
- ❌ **Signal API**: Very limited, mostly for verification/2FA use cases
- ❌ **Matrix bridge**: Extra complexity, not native Signal

### Components to Build

```
rune/harness/signal/
├── __init__.py           # Public API exports
├── daemon.py            # Daemon lifecycle (start/stop/health check)
├── client.py            # HTTP RPC client (JSON-RPC 2.0)
└── send.py              # High-level send_signal_message()
```

Plus modifications to:
- `rune/harness/tools.py` - Add signal_send tool definition
- `rune/harness/agent.py` - Add Signal config, hooks for auto-notifications
- `pyproject.toml` - Add httpx dependency

## Implementation Strategy

### Phase 1: Core Infrastructure (MVP)
**Goal:** Get basic message sending working

1. **Create signal package structure**
   - Create `rune/harness/signal/` directory
   - Add `__init__.py` with public API

2. **Implement daemon manager** (`daemon.py`)
   - `start_signal_daemon()` - spawn subprocess
   - `stop_signal_daemon()` - graceful shutdown
   - `wait_for_daemon_ready()` - health check loop
   - Error monitoring thread for stderr

3. **Implement RPC client** (`client.py`)
   - `signal_rpc_request()` - JSON-RPC 2.0 requests
   - Request ID generation (uuid)
   - Error handling for RPC errors
   - Timeout support

4. **Implement send API** (`send.py`)
   - `send_signal_message()` - main public function
   - `parse_recipient()` - handle phone/group/username formats
   - Text formatting support
   - Return success/failure result

5. **Test manually**
   - Set up signal-cli locally
   - Test sending to own phone number
   - Verify message delivery

### Phase 2: Rune Integration
**Goal:** Make it available as a tool

6. **Add tool definition** (`tools.py`)
   - Define `signal_send` tool schema
   - Add to `TOOL_DEFINITIONS` list

7. **Implement tool executor** (`tools.py`)
   - Add `execute_signal_send()` method
   - Handle attachments
   - Error handling and user feedback

8. **Test tool from agent**
   ```python
   agent = Agent()
   agent.run("Send me a Signal message saying 'Hello from Rune'")
   ```

### Phase 3: Configuration & Convenience
**Goal:** Make it easy to use

9. **Add AgentConfig options** (`agent.py`)
   - `signal_enabled: bool`
   - `signal_account: str`
   - `signal_recipient: str`
   - `signal_daemon_port: int`

10. **Add environment variable support**
    - Load from `.env` file
    - `SIGNAL_ACCOUNT`, `SIGNAL_RECIPIENT`, etc.

11. **Add auto-notification hooks** (`agent.py`)
    - On task completion
    - On error/exception
    - Configurable via `signal_notify_on_complete`, `signal_notify_on_error`

### Phase 4: Polish & Documentation
**Goal:** Production-ready

12. **Error handling & retries**
    - Retry failed sends (with exponential backoff)
    - Handle daemon crashes gracefully
    - Better error messages

13. **Daemon management strategy**
    - Support global daemon (recommended)
    - Support per-agent daemon (fallback)
    - Auto-detect if daemon already running

14. **Add tests**
    - Unit tests for client.py
    - Integration tests with mock daemon
    - End-to-end test with real signal-cli

15. **Update documentation**
    - Add Signal section to main README
    - Link to detailed docs

### Phase 5: Advanced Features (Optional)
**Goal:** Full feature parity with OpenClaw

16. **Message receiving** (optional)
    - Implement SSE stream listener
    - Handle incoming messages
    - Two-way agent interaction

17. **Rich formatting** (optional)
    - Markdown support
    - Text styles (bold, italic, code)
    - Message threading/quoting

18. **Group chat support** (optional)
    - Join/leave groups
    - Group administration
    - @mentions

19. **Attachment handling** (optional)
    - Image uploads
    - File uploads
    - Voice messages

20. **Advanced configuration** (optional)
    - Message templates
    - Rate limiting
    - Message history

## Risks & Mitigations

### Risk 1: signal-cli setup complexity
**Mitigation:**
- Provide detailed setup guide
- Include troubleshooting section
- Support both QR code and SMS verification methods
- Document common issues

### Risk 2: Daemon reliability
**Mitigation:**
- Support global daemon (more stable)
- Add health check before sending
- Implement retry logic
- Graceful degradation if daemon fails

### Risk 3: Phone number requirements
**Mitigation:**
- Document clearly in README
- Explain it's a one-time setup
- Suggest using dedicated number for bots
- Mention alternatives (Matrix, Telegram) if Signal isn't suitable

### Risk 4: Platform compatibility
**Mitigation:**
- Test on macOS, Linux, Windows
- Document platform-specific issues
- Use cross-platform subprocess handling
- Provide Docker option if needed

### Risk 5: Breaking changes in signal-cli
**Mitigation:**
- Pin to specific signal-cli version in docs
- Monitor signal-cli releases
- Test with each new signal-cli version
- Have fallback to older API if needed

## Success Criteria

### Minimum Viable Product (MVP)
- ✅ Can send a Signal message from Python code
- ✅ Works with phone numbers and groups
- ✅ Available as a tool to Rune agents
- ✅ Basic error handling
- ✅ Documentation for setup

### Production Ready
- ✅ All MVP criteria
- ✅ Configurable via environment variables
- ✅ Auto-notification on task complete/error
- ✅ Comprehensive error handling and retries
- ✅ Works on macOS and Linux
- ✅ Clear troubleshooting guide
- ✅ Example usage in README

### Full Feature Parity with OpenClaw
- ✅ All Production Ready criteria
- ✅ Message receiving (two-way communication)
- ✅ Rich text formatting (markdown)
- ✅ Attachment support
- ✅ Group chat features
- ✅ Reaction support

## Timeline Estimate

**Phase 1 (Core):** 4-6 hours
- Daemon manager: 1-2 hours
- RPC client: 1-2 hours
- Send API: 1 hour
- Testing: 1 hour

**Phase 2 (Integration):** 2-3 hours
- Tool definition: 30 mins
- Tool executor: 1 hour
- Testing: 1 hour

**Phase 3 (Config):** 2-3 hours
- Config options: 1 hour
- Environment variables: 30 mins
- Auto-notifications: 1 hour
- Testing: 30 mins

**Phase 4 (Polish):** 3-4 hours
- Error handling: 1-2 hours
- Daemon strategy: 1 hour
- Tests: 1 hour
- Documentation: 1 hour

**Total MVP:** 11-16 hours
**Total Production:** 11-16 hours (MVP is production-ready)
**Total Full Feature:** +8-12 hours for advanced features

## Open Questions

1. **Daemon strategy:** Should we default to global daemon or per-agent?
   - **Decision:** Default to global (document in README), fall back to per-agent if needed
   - **Reason:** More reliable, no startup delay

2. **Configuration:** Where should Signal config live?
   - **Decision:** Multiple options - env vars, `AgentConfig`, `~/.rune/signal.yaml`
   - **Reason:** Flexibility for different use cases

3. **Error handling:** What should happen if Signal send fails?
   - **Decision:** Tool returns error result, agent sees failure, can retry
   - **Reason:** Agent should be aware and decide how to handle

4. **Permissions:** Should signal_send require approval?
   - **Decision:** Yes, by default (uses standard tool permission system)
   - **Reason:** Sending messages is an action with external effects

5. **Attachments:** How to handle file paths in sandboxed environment?
   - **Decision:** Support absolute paths, resolve relative to working directory
   - **Reason:** Consistent with other file-based tools (read_file, etc.)

6. **Testing:** How to test without real Signal account?
   - **Decision:** Mock the RPC client, provide integration test that requires manual setup
   - **Reason:** Unit tests fast/automatic, integration tests validate real behavior

## Dependencies

### External
- **signal-cli**: 0.13.9 or later
- User must have Signal account linked

### Python Packages (add to pyproject.toml)
```toml
dependencies = [
  # ... existing ...
  "httpx>=0.27.0",  # HTTP client for signal-cli RPC
]
```

## File Checklist

- [ ] `rune/harness/signal/__init__.py`
- [ ] `rune/harness/signal/daemon.py`
- [ ] `rune/harness/signal/client.py`
- [ ] `rune/harness/signal/send.py`
- [ ] `rune/harness/tools.py` (modify)
- [ ] `rune/harness/agent.py` (modify)
- [ ] `pyproject.toml` (modify)
- [ ] `docs/2026-02-09/signal-integration/docs.md` (done)
- [ ] `docs/2026-02-09/signal-integration/plan.md` (this file)
- [ ] `docs/2026-02-09/signal-integration/todo.md`
- [ ] `README.md` (update with Signal section)
- [ ] Example script: `examples/signal_notify.py`
- [ ] Tests: `rune/tests/test_signal.py`

## Next Actions

1. Review this plan with the user
2. Get approval on architecture decisions
3. Start with Phase 1 implementation
4. Iterate based on testing feedback
