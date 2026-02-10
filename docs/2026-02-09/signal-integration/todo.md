# Signal Integration - Todo List

## Phase 1: Core Infrastructure (MVP)

### Setup
- [x] Install signal-cli locally for development
- [x] Link Signal account for testing
- [x] Verify signal-cli works manually
- [x] Add httpx to pyproject.toml dependencies

### Package Structure
- [x] Create `rune/integrations/signal/` directory
- [x] Create `rune/integrations/signal/__init__.py`
- [x] Add public API exports to `__init__.py`

### Daemon Manager (daemon.py)
- [x] Implement `start_signal_daemon(account, host, port)`
  - [x] Build command arguments
  - [x] Spawn subprocess with Popen
  - [x] Capture stdout/stderr
  - [x] Return process handle
- [x] Implement `stop_signal_daemon(process)`
  - [x] Send SIGTERM
  - [x] Wait for graceful shutdown
  - [x] Cleanup resources
- [x] Implement `wait_for_daemon_ready(base_url, timeout)`
  - [x] Poll health endpoint
  - [x] Retry with backoff
  - [x] Return success/failure
- [x] Add stderr monitoring (basic logging)
- [x] Add exception handling
  - [x] Handle daemon spawn failures
  - [x] Handle daemon crashes
  - [x] Provide helpful error messages

### RPC Client (client.py)
- [x] Implement `signal_rpc_request(method, params, base_url, timeout)`
  - [x] Generate unique request ID (uuid)
  - [x] Build JSON-RPC 2.0 request
  - [x] Send POST to /api/v1/rpc
  - [x] Parse JSON response
  - [x] Extract result or error
  - [x] Return result dict
- [x] Add `SignalRPCError` exception class
  - [x] Include RPC error code
  - [x] Include RPC error message
- [x] Add timeout handling
  - [x] Use httpx timeout parameter
  - [x] Raise clear timeout error
- [x] Add connection error handling
  - [x] Catch connection refused
  - [x] Suggest daemon not running
- [x] Add logging
  - [x] Log requests (debug level)
  - [x] Log responses (debug level)
  - [x] Log errors (error level)

### Send API (send.py)
- [x] Implement `parse_recipient(recipient)`
  - [x] Handle phone numbers: "+1234567890"
  - [x] Handle groups: "group:abc123"
  - [x] Handle usernames: "u:alice" or "username:alice"
  - [x] Strip "signal:" prefix if present
  - [x] Return proper RPC params dict
- [x] Implement `send_signal_message(to, text, account, attachments, base_url)`
  - [x] Parse recipient
  - [x] Build RPC params
  - [x] Add message text
  - [x] Add attachments if provided
  - [x] Call signal_rpc_request with "send" method
  - [x] Return success result with message_id
- [x] Add attachment validation
  - [x] Check files exist
  - [x] Check file sizes (basic check)
  - [x] Convert to absolute paths
- [ ] Add text formatting support (optional - future)
  - [ ] Support markdown mode
  - [ ] Support plain mode
- [x] Add error handling
  - [x] Catch RPC errors
  - [x] Catch file not found
  - [x] Return clear error messages

### Testing
- [ ] Manual test: Start daemon
- [ ] Manual test: Send to own phone number
- [ ] Manual test: Send with attachment
- [ ] Manual test: Send to group
- [ ] Manual test: Error scenarios (daemon not running, etc.)

---

## Phase 2: Rune Integration

### Tool Definition
- [x] Open `rune/harness/tools.py`
- [x] Add `signal_send` to `TOOL_DEFINITIONS` list
  - [x] Define name: "signal_send"
  - [x] Write description
  - [x] Define parameters:
    - [x] `to` (string, required)
    - [x] `message` (string, required)
    - [x] `attachments` (array of strings, optional)
- [x] Add to tool list in module docstring

### Tool Executor
- [x] Add `execute_signal_send(self, args)` to `ToolExecutor` class
  - [x] Import send_signal_message
  - [x] Extract args (to, message, attachments)
  - [x] Get account from config
  - [x] Call send_signal_message
  - [x] Return ToolResult with success message
- [x] Add error handling
  - [x] Catch exceptions
  - [x] Return ToolResult with error
  - [x] Include helpful debug info
- [x] Add validation
  - [x] Validate recipient format
  - [x] Validate message not empty
  - [x] Validate attachment paths
- [x] Update tool routing
  - [x] Add case for "signal_send" in handlers dict
  - [x] Call _execute_signal_send

### Testing
- [ ] Test tool via Agent
  ```python
  agent = Agent()
  agent.run("Send me a Signal message saying 'Test'")
  ```
- [ ] Verify tool appears in available tools
- [ ] Verify agent can call tool
- [ ] Verify message is received
- [ ] Test with attachments
- [ ] Test error handling (bad recipient, daemon down)

---

## Phase 3: Configuration & Convenience

### AgentConfig Updates
- [x] Open `rune/harness/agent.py`
- [x] Add fields to `AgentConfig` dataclass:
  - [x] `signal_account: str | None = None`
  - [ ] `signal_recipient: str | None = None` (optional - for auto-notify)
  - [ ] `signal_daemon_port: int = 7583` (optional - advanced)
  - [ ] `signal_notify_on_complete: bool = True` (optional - auto-notify)
  - [ ] `signal_notify_on_error: bool = True` (optional - auto-notify)
- [x] Pass signal config to ToolExecutor
- [ ] Add validation for config (optional - can add later)
  - [ ] If enabled, account must be set
  - [ ] Validate phone number format

### Environment Variables
- [ ] Add environment variable loading
  - [ ] `SIGNAL_ENABLED`
  - [ ] `SIGNAL_ACCOUNT`
  - [ ] `SIGNAL_RECIPIENT`
  - [ ] `SIGNAL_DAEMON_PORT`
- [ ] Load in AgentConfig.__post_init__ or from env
- [ ] Document in README
- [ ] Add example .env file

### Auto-Notifications
- [ ] Add `_send_signal_notification(self, message)` helper
  - [ ] Check if signal_enabled
  - [ ] Check if recipient set
  - [ ] Call send_signal_message
  - [ ] Handle errors gracefully (log, don't crash)
- [ ] Hook into task completion
  - [ ] Find where agent completes successfully
  - [ ] Add notification call
  - [ ] Check `signal_notify_on_complete` flag
  - [ ] Format message nicely
- [ ] Hook into error handling
  - [ ] Find exception handler
  - [ ] Add notification call
  - [ ] Check `signal_notify_on_error` flag
  - [ ] Include error details
- [ ] Add message templates
  - [ ] Template for task complete
  - [ ] Template for error
  - [ ] Allow customization

### Testing
- [ ] Test config loading from env vars
- [ ] Test auto-notification on success
- [ ] Test auto-notification on error
- [ ] Test with signal_enabled=False (no notifications)
- [ ] Test with missing recipient (should warn, not crash)

---

## Phase 4: Polish & Documentation

### Error Handling & Retries
- [ ] Add retry logic to send_signal_message
  - [ ] Retry on connection errors
  - [ ] Exponential backoff
  - [ ] Max 3 retries
  - [ ] Log each retry
- [ ] Improve error messages
  - [ ] "Daemon not running" → suggest starting daemon
  - [ ] "Account not found" → suggest linking account
  - [ ] "Recipient invalid" → explain format
- [ ] Add fallback behavior
  - [ ] If send fails, log error but don't crash agent
  - [ ] Option to queue messages for later

### Daemon Management Strategy
- [ ] Implement daemon detection
  - [ ] Check if daemon already running (health check)
  - [ ] Don't start if already running
- [ ] Add `signal_daemon_mode` config option
  - [ ] "global" - expect daemon already running
  - [ ] "auto" - start if not running, stop on shutdown
  - [ ] "manual" - never start daemon
- [ ] Update start_signal_daemon to respect mode
- [ ] Add shutdown hook to stop daemon (only if auto mode)
- [ ] Document recommended mode (global)

### Tests
- [ ] Unit tests for client.py
  - [ ] Mock httpx requests
  - [ ] Test RPC request/response parsing
  - [ ] Test error handling
- [ ] Unit tests for send.py
  - [ ] Test parse_recipient
  - [ ] Mock client calls
  - [ ] Test attachment handling
- [ ] Unit tests for daemon.py
  - [ ] Mock subprocess
  - [ ] Test start/stop
  - [ ] Test health checks
- [ ] Integration test
  - [ ] Requires signal-cli setup
  - [ ] Mark as optional/manual
  - [ ] Test end-to-end send
- [ ] Add pytest fixtures
  - [ ] Mock signal daemon
  - [ ] Mock RPC client

### Documentation Updates
- [ ] Update main README.md
  - [ ] Add "Signal Integration" section
  - [ ] Link to detailed docs
  - [ ] Show basic example
  - [ ] Document prerequisites
- [ ] Add example script
  - [ ] `examples/signal_notify.py`
  - [ ] Show manual usage
  - [ ] Show auto-notification usage
- [ ] Update CLI help
  - [ ] Add signal flags if needed
- [ ] Add troubleshooting FAQ
  - [ ] Common issues
  - [ ] How to debug
- [ ] Add architecture diagram (optional)
  - [ ] Visual representation of components

---

## Phase 5: Advanced Features (Optional)

### Message Receiving
- [ ] Implement SSE stream listener
  - [ ] Connect to /api/v1/events
  - [ ] Parse SSE format
  - [ ] Yield events
- [ ] Implement event handler
  - [ ] Handle incoming messages
  - [ ] Handle reactions
  - [ ] Handle typing indicators
- [ ] Add callback system
  - [ ] Register message handlers
  - [ ] Route to appropriate handlers
- [ ] Add to tool
  - [ ] `signal_listen` tool
  - [ ] Return incoming messages

### Rich Formatting
- [ ] Add markdown support
  - [ ] Parse markdown to Signal format
  - [ ] Bold, italic, strikethrough
  - [ ] Code blocks
- [ ] Add text styles
  - [ ] Bold: **text**
  - [ ] Italic: *text*
  - [ ] Monospace: `code`
- [ ] Add mentions
  - [ ] @username format
  - [ ] Resolve to Signal user

### Group Chat Support
- [ ] List groups
  - [ ] `list_groups()` function
  - [ ] Return group IDs and names
- [ ] Join/leave groups
  - [ ] `join_group(invite_link)`
  - [ ] `leave_group(group_id)`
- [ ] Group administration
  - [ ] Add/remove members
  - [ ] Change group settings
- [ ] @mentions in groups

### Advanced Attachments
- [ ] Support more file types
  - [ ] Images (already works)
  - [ ] Videos
  - [ ] Audio
  - [ ] Documents
- [ ] Thumbnail generation
  - [ ] For images
  - [ ] For videos
- [ ] Voice messages
  - [ ] Record voice
  - [ ] Send as voice message

### Configuration File
- [ ] Add YAML config support
  - [ ] `~/.rune/signal.yaml`
  - [ ] Load in AgentConfig
- [ ] Add message templates
  - [ ] Customizable formats
  - [ ] Variable substitution
- [ ] Add rate limiting
  - [ ] Max messages per minute
  - [ ] Throttling

---

## Testing Checklist

### Manual Testing
- [ ] Setup signal-cli on macOS
- [ ] Setup signal-cli on Linux
- [ ] Link Signal account
- [ ] Start daemon manually
- [ ] Send test message to own phone
- [ ] Send message with attachment
- [ ] Send message to group
- [ ] Test with daemon not running (error)
- [ ] Test with invalid recipient (error)

### Automated Testing
- [ ] Run unit tests
- [ ] Run integration tests (if Signal setup)
- [ ] Check test coverage
- [ ] Test on CI (if possible)

### Edge Cases
- [ ] Daemon crashes mid-send
- [ ] Network connectivity issues
- [ ] Invalid phone number format
- [ ] Large attachments (>100MB)
- [ ] Very long messages
- [ ] Special characters in message
- [ ] Unicode/emoji support
- [ ] Concurrent sends

---

## Documentation Checklist

- [x] Complete detailed docs.md
- [x] Complete implementation plan.md
- [x] Complete this todo.md
- [ ] Update main README with Signal section
- [ ] Create example scripts
- [ ] Add troubleshooting guide
- [ ] Document all config options
- [ ] Add API reference for signal functions

---

## Deployment Checklist

- [ ] Code review
- [ ] All tests passing
- [ ] Documentation complete
- [ ] Example scripts working
- [ ] Dependencies added to pyproject.toml
- [ ] Update CHANGELOG (if exists)
- [ ] Git commit and push
- [ ] Create pull request
- [ ] Update version number (if needed)

---

## Future Enhancements

- [ ] Docker image with signal-cli pre-installed
- [ ] GUI for Signal setup
- [ ] Web dashboard for message history
- [ ] Multi-account support
- [ ] Scheduled messages
- [ ] Message templates in config
- [ ] Webhook integration
- [ ] Slack-style bot commands
- [ ] Natural language processing for incoming messages
- [ ] Integration with other messaging platforms (Telegram, Discord)

---

## Notes

- Remember to test with real Signal account before considering done
- Keep security in mind - never log sensitive data
- Make error messages helpful and actionable
- Follow existing Rune code style and patterns
- Keep dependencies minimal (only httpx)
- Make it optional - don't break existing functionality
- Document everything - assume users don't know Signal/signal-cli

## Questions for User

- [ ] Do you want auto-notifications by default or opt-in?
- [ ] Should we support message receiving in MVP or later?
- [ ] Preferred daemon strategy - global or per-agent?
- [ ] Any specific message templates you want?
- [ ] Should this work with multiple Signal accounts?
