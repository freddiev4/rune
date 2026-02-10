# Signal Integration Documentation

This folder contains all planning and documentation for adding Signal messaging support to Rune.

## Documents

### 📋 [plan.md](./plan.md)
Implementation plan including:
- Architecture decisions
- Component design
- Implementation phases
- Risk mitigation
- Success criteria
- Timeline estimates

**Start here** to understand the overall approach and strategy.

### 📚 [docs.md](./docs.md)
Comprehensive documentation including:
- Setup instructions
- Architecture overview
- Implementation details
- Usage examples
- Configuration guide
- Troubleshooting
- References

**Read this** for complete technical documentation and how-to guides.

### ✅ [todo.md](./todo.md)
Detailed task list with:
- Phase-by-phase tasks
- Testing checklist
- Documentation checklist
- Deployment checklist

**Use this** to track implementation progress.

## Quick Start

### For Users (After Implementation)
1. Install signal-cli: `brew install signal-cli`
2. Link your Signal account: `signal-cli -a +1234567890 link -n "Rune Agent"`
3. Configure Rune:
   ```bash
   export SIGNAL_ACCOUNT="+1234567890"
   export SIGNAL_RECIPIENT="+0987654321"
   export SIGNAL_ENABLED=true
   ```
4. Run your agent - it will notify you when tasks complete!

### For Developers (Implementation)
1. Read [plan.md](./plan.md) to understand the architecture
2. Follow [todo.md](./todo.md) phase by phase
3. Refer to [docs.md](./docs.md) for implementation details
4. Test thoroughly before considering each phase complete

## Overview

### What is This?
Signal integration allows Rune agents to send Signal messages when:
- Tasks complete successfully
- Errors occur
- Important milestones are reached
- Manually requested via the `signal_send` tool

### How Does It Work?

```
┌──────────────┐
│  Rune Agent  │  Task complete!
└──────┬───────┘
       │
       │ send_signal_message("+1234567890", "Done!")
       ▼
┌──────────────┐
│ Signal Tool  │  HTTP RPC (JSON-RPC 2.0)
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ signal-cli   │  Signal Protocol
│  (daemon)    │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Your Phone   │  📱 Notification!
└──────────────┘
```

### Why signal-cli?
- ✅ Official Signal protocol implementation
- ✅ Battle-tested (used by OpenClaw)
- ✅ Simple HTTP API
- ✅ Cross-platform
- ✅ Well-documented

## Implementation Status

**Current Status:** Planning Complete ✅

### Phases
- [x] **Planning** - Architecture, design, documentation
- [ ] **Phase 1:** Core Infrastructure - Daemon, client, send API
- [ ] **Phase 2:** Rune Integration - Tool definition, executor
- [ ] **Phase 3:** Configuration - Config, env vars, auto-notifications
- [ ] **Phase 4:** Polish - Error handling, tests, docs
- [ ] **Phase 5:** Advanced Features - Message receiving, rich formatting (optional)

## Key Files to Create/Modify

### New Files
```
rune/harness/signal/
├── __init__.py          # Public API
├── daemon.py            # Daemon lifecycle
├── client.py            # HTTP RPC client
└── send.py              # send_signal_message()

rune/tests/
└── test_signal.py       # Unit tests

examples/
└── signal_notify.py     # Example usage
```

### Modified Files
```
rune/harness/tools.py    # Add signal_send tool
rune/harness/agent.py    # Add Signal config
pyproject.toml           # Add httpx dependency
README.md                # Add Signal section
```

## Dependencies

### External (User Setup)
- **signal-cli** 0.13.9+ - Install via brew/apt/manual
- **Signal account** - Phone number for verification

### Python (Add to pyproject.toml)
```toml
dependencies = [
  # ... existing ...
  "httpx>=0.27.0",  # HTTP client for signal-cli RPC
]
```

## Architecture Decisions

### ✅ Use signal-cli + HTTP RPC
**Why:** Battle-tested, simple, cross-platform, official protocol

### ✅ Start with send-only
**Why:** MVP first, can add receiving later

### ✅ Support both global and per-agent daemon
**Why:** Flexibility - global is recommended but per-agent is easier for some users

### ✅ Make it optional
**Why:** Not everyone wants/needs Signal, shouldn't break existing functionality

### ✅ Add as a tool
**Why:** Consistent with Rune's architecture, agent can decide when to notify

## Timeline

**Estimated time to MVP:** 11-16 hours

- Phase 1 (Core): 4-6 hours
- Phase 2 (Integration): 2-3 hours
- Phase 3 (Config): 2-3 hours
- Phase 4 (Polish): 3-4 hours

**Advanced features:** +8-12 hours (optional)

## Resources

### Primary Reference
- **OpenClaw Signal Implementation:** https://github.com/openclaw/openclaw/tree/main/src/signal
  - This is our main reference for architecture and patterns

### Documentation
- **signal-cli:** https://github.com/AsamK/signal-cli
- **signal-cli JSON-RPC API:** https://github.com/AsamK/signal-cli/wiki/JSON-RPC-service
- **Signal Protocol:** https://signal.org/docs/

### Libraries
- **httpx:** https://www.python-httpx.org/

## Contact & Questions

If you have questions about this implementation:
1. Check [docs.md](./docs.md) for detailed explanations
2. Review [plan.md](./plan.md) for architecture decisions
3. Check the "Open Questions" section in plan.md
4. Ask the user/team for clarification

## License

Same as Rune (MIT)

---

**Last Updated:** 2026-02-09
**Status:** Planning Complete, Ready for Implementation
**Next Step:** Begin Phase 1 - Core Infrastructure
