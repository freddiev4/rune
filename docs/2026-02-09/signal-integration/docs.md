# Signal Integration for Rune

Complete guide for integrating Signal messaging into the Rune agent framework.

## Table of Contents
1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Installation](#installation)
4. [Architecture](#architecture)
5. [Implementation Details](#implementation-details)
6. [Usage Examples](#usage-examples)
7. [Configuration](#configuration)
8. [Troubleshooting](#troubleshooting)
9. [References](#references)

---

## Overview

This integration enables Rune agents to send Signal messages when they complete tasks, encounter errors, or reach important milestones. Based on OpenClaw's architecture, we use **signal-cli** as the underlying Signal protocol implementation and communicate with it via HTTP RPC.

### Key Features
- ✅ Send Signal messages from Python
- ✅ Asynchronous message delivery
- ✅ Support for individual and group chats
- ✅ Attachment support (images, files)
- ✅ Text formatting (markdown)
- ⚠️ Optional: Receive incoming messages (two-way communication)

### Architecture Diagram
```
┌─────────────────┐
│   Rune Agent    │
│                 │
│  Task Complete  │
└────────┬────────┘
         │
         │ send_signal_message()
         ▼
┌─────────────────┐
│  Signal Tool    │
│   (Python)      │
└────────┬────────┘
         │
         │ HTTP RPC (JSON-RPC 2.0)
         ▼
┌─────────────────┐
│  signal-cli     │
│   (daemon)      │
│                 │
│  Port: 7583     │
└────────┬────────┘
         │
         │ Signal Protocol
         ▼
┌─────────────────┐
│  Signal Server  │
│                 │
│   📱 Devices    │
└─────────────────┘
```

---

## Prerequisites

### 1. Signal-CLI Installation

**macOS (via Homebrew):**
```bash
brew install signal-cli
```

**Linux (Manual):**
```bash
# Download latest release
wget https://github.com/AsamK/signal-cli/releases/download/v0.13.9/signal-cli-0.13.9-Linux.tar.gz

# Extract
tar xf signal-cli-0.13.9-Linux.tar.gz -C /opt

# Add to PATH
echo 'export PATH=$PATH:/opt/signal-cli/bin' >> ~/.bashrc
source ~/.bashrc
```

**Verify Installation:**
```bash
signal-cli --version
# Should output: signal-cli 0.13.9 (or later)
```

### 2. Signal Account Setup

You need a phone number that can receive SMS for verification. You can use:
- Your personal phone (if you want to send from your account)
- A dedicated phone number for the bot
- A virtual number (e.g., Google Voice, Twilio)

**Important:** Once a phone number is linked to signal-cli, it CANNOT be used with Signal Desktop/Mobile unless you re-register.

---

## Installation

### Step 1: Link Signal Account

**Option A: Using QR Code (Recommended)**
```bash
# Start registration
signal-cli -a +1234567890 link -n "Rune Agent"

# This will display a QR code in your terminal
# Scan it with Signal Mobile app: Settings → Linked Devices → Link New Device
```

**Option B: Using SMS Verification**
```bash
# Request verification code
signal-cli -a +1234567890 register

# Enter the code you receive via SMS
signal-cli -a +1234567890 verify CODE_HERE
```

### Step 2: Verify Setup
```bash
# Test sending a message to yourself
signal-cli -a +1234567890 send -m "Test from signal-cli" +1234567890
```

### Step 3: Install Python Dependencies
```bash
cd rune
source .venv/bin/activate

# Add to pyproject.toml dependencies
uv add httpx  # HTTP client for signal-cli communication
```

---

## Architecture

### How OpenClaw Implements Signal

Based on research of the openclaw/openclaw repository:

#### 1. **Daemon Management** (`signal/daemon.ts`)
- Spawns signal-cli as a subprocess in daemon mode
- Command: `signal-cli daemon --http localhost:7583`
- Monitors stdout/stderr for errors
- Provides lifecycle management (start/stop)

#### 2. **HTTP Client** (`signal/client.ts`)
- Communicates via JSON-RPC 2.0 format
- Endpoints:
  - `POST /api/v1/rpc` - Send messages, get info
  - `GET /api/v1/events` - Server-Sent Events (SSE) stream
- No special libraries needed - just HTTP requests

#### 3. **Message Sending** (`signal/send.ts`)
```typescript
sendMessageSignal(to: string, text: string, opts: {
  baseUrl?: string,        // Default: http://localhost:7583
  account?: string,        // Your phone number
  mediaUrl?: string,       // Attachments
  textMode?: "markdown" | "plain"
})
```

Supports:
- Phone numbers: `+1234567890`
- Groups: `group:groupId`
- Usernames: `username:alice` or `u:alice`

#### 4. **Message Receiving** (`signal/monitor.ts`)
- Opens SSE stream to `/api/v1/events`
- Parses incoming messages/reactions
- Validates senders against allowlists
- Downloads attachments
- Sends replies back

#### 5. **Key Files in OpenClaw**
```
src/signal/
├── accounts.ts          # Account management
├── client.ts            # HTTP RPC client
├── daemon.ts            # Daemon lifecycle
├── format.ts            # Message formatting
├── identity.ts          # User identity
├── monitor.ts           # Incoming message handler
├── send.ts              # Send messages
└── sse-reconnect.ts     # SSE stream management
```

### Adapting for Rune (Python)

We'll create a simpler, focused implementation:

```
rune/harness/
├── tools.py                    # Add signal tool definition
└── signal/
    ├── __init__.py
    ├── daemon.py              # Spawn/manage signal-cli daemon
    ├── client.py              # HTTP client for RPC calls
    └── send.py                # High-level send message API
```

**Why simpler?**
- Rune only needs **sending** (not receiving) for basic use case
- Python subprocess management is simpler than TypeScript
- httpx library handles HTTP/SSE elegantly
- Can add receiving later if needed

---

## Implementation Details

### Component 1: Daemon Manager

**File:** `rune/harness/signal/daemon.py`

**Purpose:** Start and manage the signal-cli daemon process

**Key Functions:**
```python
def start_signal_daemon(
    account: str,
    host: str = "localhost",
    port: int = 7583
) -> subprocess.Popen:
    """
    Start signal-cli in daemon mode.

    Returns:
        Process handle for the daemon
    """

def stop_signal_daemon(process: subprocess.Popen) -> None:
    """Stop the daemon gracefully."""

def wait_for_daemon_ready(
    base_url: str = "http://localhost:7583",
    timeout: int = 30
) -> bool:
    """Poll daemon health endpoint until ready."""
```

**Implementation Notes:**
- Use `subprocess.Popen` with `stdout=subprocess.PIPE`
- Monitor stderr in a background thread
- Daemon command: `signal-cli -a {account} daemon --http {host}:{port}`
- Health check: `GET /api/v1/health` should return 200

### Component 2: HTTP Client

**File:** `rune/harness/signal/client.py`

**Purpose:** Low-level HTTP RPC communication with signal-cli

**Key Functions:**
```python
def signal_rpc_request(
    method: str,
    params: dict,
    base_url: str = "http://localhost:7583",
    timeout: int = 10
) -> dict:
    """
    Send JSON-RPC 2.0 request to signal-cli daemon.

    Args:
        method: RPC method name (e.g., "send", "listAccounts")
        params: Method parameters
        base_url: Daemon URL
        timeout: Request timeout in seconds

    Returns:
        RPC result dictionary

    Raises:
        SignalRPCError: If RPC returns an error
    """
```

**JSON-RPC 2.0 Format:**
```json
// Request
{
  "jsonrpc": "2.0",
  "id": "uuid-here",
  "method": "send",
  "params": {
    "message": "Hello!",
    "recipient": ["+1234567890"]
  }
}

// Response (success)
{
  "jsonrpc": "2.0",
  "id": "uuid-here",
  "result": {
    "timestamp": 1234567890,
    "messageId": "..."
  }
}

// Response (error)
{
  "jsonrpc": "2.0",
  "id": "uuid-here",
  "error": {
    "code": -1,
    "message": "Failed to send"
  }
}
```

### Component 3: High-Level Send API

**File:** `rune/harness/signal/send.py`

**Purpose:** Simple, ergonomic API for sending messages

**Key Functions:**
```python
def send_signal_message(
    to: str,
    text: str,
    *,
    account: str | None = None,
    attachments: list[str] | None = None,
    base_url: str = "http://localhost:7583"
) -> dict:
    """
    Send a Signal message.

    Args:
        to: Recipient (phone number, group ID, username)
        text: Message text
        account: Sender account (uses default if None)
        attachments: List of file paths to attach
        base_url: Daemon URL

    Returns:
        {"success": True, "message_id": "...", "timestamp": 123}

    Example:
        send_signal_message(
            to="+1234567890",
            text="Task completed successfully!",
            attachments=["/tmp/screenshot.png"]
        )
    """

def parse_recipient(recipient: str) -> dict:
    """
    Parse recipient string into signal-cli format.

    Supports:
      - Phone: "+1234567890" → {"recipient": ["+1234567890"]}
      - Group: "group:abc123" → {"groupId": "abc123"}
      - Username: "u:alice" → {"username": "alice"}
    """
```

### Component 4: Rune Tool Integration

**File:** `rune/harness/tools.py` (modify existing)

**Add new tool definition:**
```python
{
    "type": "function",
    "function": {
        "name": "signal_send",
        "description": "Send a Signal message to notify about task completion or important events.",
        "parameters": {
            "type": "object",
            "properties": {
                "to": {
                    "type": "string",
                    "description": "Recipient phone number (e.g., +1234567890) or group ID"
                },
                "message": {
                    "type": "string",
                    "description": "Message text to send"
                },
                "attachments": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of file paths to attach"
                }
            },
            "required": ["to", "message"]
        }
    }
}
```

**Add executor in ToolExecutor class:**
```python
def execute_signal_send(self, args: dict) -> ToolResult:
    """Execute the signal_send tool."""
    try:
        from rune.harness.signal.send import send_signal_message

        result = send_signal_message(
            to=args["to"],
            text=args["message"],
            attachments=args.get("attachments"),
            account=self.signal_account  # From config
        )

        return ToolResult(
            success=True,
            output=f"✓ Signal message sent to {args['to']}\n"
                   f"Message ID: {result['message_id']}"
        )
    except Exception as e:
        return ToolResult(
            success=False,
            output="",
            error=f"Failed to send Signal message: {str(e)}"
        )
```

### Component 5: Configuration

**File:** `rune/harness/agent.py` (modify)

Add Signal configuration to `AgentConfig`:
```python
@dataclass
class AgentConfig:
    # ... existing fields ...

    # Signal integration
    signal_enabled: bool = False
    signal_account: str | None = None  # Phone number
    signal_daemon_port: int = 7583
    signal_notify_on_complete: bool = True
    signal_notify_on_error: bool = True
    signal_recipient: str | None = None  # Default recipient
```

**Environment Variables:**
```bash
# .env file
SIGNAL_ACCOUNT="+1234567890"
SIGNAL_RECIPIENT="+0987654321"
SIGNAL_ENABLED=true
```

---

## Usage Examples

### Example 1: Basic Notification
```python
from rune import Agent, AgentConfig

config = AgentConfig(
    model="gpt-4o",
    signal_enabled=True,
    signal_account="+1234567890",
    signal_recipient="+0987654321"
)

agent = Agent(config=config)
result = agent.run("Analyze the codebase and create a report")

# Agent can now use the signal_send tool:
# "I've completed the analysis. Let me notify you via Signal..."
```

### Example 2: Manual Signal Sending (via tool)
```python
# Agent can call the tool directly
agent.run("""
1. Run the tests
2. If they pass, send me a Signal message with the results
""")

# The agent will execute:
# signal_send(
#     to="+1234567890",
#     message="✅ All tests passed!\n\nTotal: 42 tests\nPassed: 42\nFailed: 0"
# )
```

### Example 3: Error Notifications
```python
# In agent.py, after catching exceptions:
if config.signal_enabled and config.signal_notify_on_error:
    send_signal_message(
        to=config.signal_recipient,
        text=f"⚠️ Agent Error\n\nTask: {task}\nError: {str(error)}",
        account=config.signal_account
    )
```

### Example 4: Task Completion Hook
```python
# In agent.py, after successful task completion:
def _on_task_complete(self, task: str, result: str):
    if self.config.signal_enabled and self.config.signal_notify_on_complete:
        send_signal_message(
            to=self.config.signal_recipient,
            text=f"✅ Task Complete\n\n{task}\n\nResult:\n{result[:200]}...",
            account=self.config.signal_account
        )
```

### Example 5: With Attachments
```python
agent.run("""
1. Generate a visualization of the data
2. Save it as chart.png
3. Send it to me via Signal
""")

# Agent executes:
# signal_send(
#     to="+1234567890",
#     message="Here's the data visualization",
#     attachments=["chart.png"]
# )
```

---

## Configuration

### Global Daemon (Recommended)

Run signal-cli daemon globally (always running):

```bash
# Start daemon in background
signal-cli -a +1234567890 daemon --http localhost:7583 &

# Or use systemd (Linux)
cat > ~/.config/systemd/user/signal-cli.service <<EOF
[Unit]
Description=Signal CLI Daemon

[Service]
Type=simple
ExecStart=/usr/local/bin/signal-cli -a +1234567890 daemon --http localhost:7583
Restart=on-failure

[Install]
WantedBy=default.target
EOF

systemctl --user enable signal-cli
systemctl --user start signal-cli
```

**Pros:**
- No startup delay
- Multiple applications can use it
- More reliable

**Cons:**
- Runs continuously
- Need to manage separately

### Per-Agent Daemon (Alternative)

Let Rune start/stop the daemon:

```python
# In agent.py __init__:
if config.signal_enabled:
    from rune.harness.signal.daemon import start_signal_daemon
    self._signal_daemon = start_signal_daemon(
        account=config.signal_account,
        port=config.signal_daemon_port
    )

# In agent.py shutdown:
if hasattr(self, '_signal_daemon'):
    stop_signal_daemon(self._signal_daemon)
```

**Pros:**
- Automatic lifecycle management
- No manual setup

**Cons:**
- 5-10 second startup time
- Extra complexity

### Configuration File

**File:** `~/.rune/signal.yaml`
```yaml
# Signal configuration
account: "+1234567890"
daemon:
  host: localhost
  port: 7583
  auto_start: false  # Use global daemon

notifications:
  enabled: true
  recipient: "+0987654321"
  on_complete: true
  on_error: true
  include_attachments: true

# Optional: message templates
templates:
  task_complete: "✅ Task Complete\n\n{task}\n\nResult:\n{result}"
  error: "⚠️ Error\n\n{task}\n\nError:\n{error}"
```

---

## Troubleshooting

### Issue 1: "signal-cli: command not found"
**Solution:**
```bash
# Verify installation
which signal-cli

# If not found, reinstall:
brew install signal-cli  # macOS
# or follow manual installation steps above
```

### Issue 2: Daemon won't start
**Check:**
```bash
# Test manually
signal-cli -a +1234567890 daemon --http localhost:7583

# Common issues:
# 1. Account not registered → run link/register first
# 2. Port already in use → check: lsof -i :7583
# 3. Permission denied → check file permissions in ~/.local/share/signal-cli
```

### Issue 3: "Connection refused" errors
**Solution:**
```bash
# Check daemon is running
curl http://localhost:7583/api/v1/health

# If not responding, restart daemon
pkill -f signal-cli
signal-cli -a +1234567890 daemon --http localhost:7583
```

### Issue 4: Messages not sending
**Debug:**
```python
# Enable verbose logging in client.py
import logging
logging.basicConfig(level=logging.DEBUG)

# Test signal-cli directly
import subprocess
subprocess.run([
    "signal-cli", "-a", "+1234567890",
    "send", "-m", "test", "+0987654321"
])
```

### Issue 5: "Account not found"
**Solution:**
```bash
# List registered accounts
signal-cli listAccounts

# Re-register if needed
signal-cli -a +1234567890 link -n "Rune Agent"
```

---

## References

### Documentation
- **signal-cli GitHub**: https://github.com/AsamK/signal-cli
- **signal-cli Wiki**: https://github.com/AsamK/signal-cli/wiki
- **JSON-RPC API**: https://github.com/AsamK/signal-cli/wiki/JSON-RPC-service
- **OpenClaw Source**: https://github.com/openclaw/openclaw/tree/main/src/signal

### Libraries
- **Python httpx**: https://www.python-httpx.org/
- **signal-cli release**: https://github.com/AsamK/signal-cli/releases

### Signal Protocol
- **Signal Protocol Docs**: https://signal.org/docs/
- **libsignal (what signal-cli uses)**: https://github.com/signalapp/libsignal

### Related Projects
- **OpenClaw**: Multi-platform AI assistant with Signal support
- **signal-bot-python**: Example Python Signal bot
- **pysignald**: Alternative Python Signal library (uses signald instead of signal-cli)

### Alternatives to signal-cli
If signal-cli doesn't work, consider:
- **signald**: JSON-based Signal daemon (more stable, separate project)
- **Signal API**: Official but limited (https://signal.org/api)
- **Matrix bridge**: Use Matrix as intermediary to Signal

---

## Next Steps

1. ✅ Complete this documentation
2. ⬜ Implement `daemon.py` - daemon lifecycle management
3. ⬜ Implement `client.py` - HTTP RPC client
4. ⬜ Implement `send.py` - high-level send API
5. ⬜ Add tool definition to `tools.py`
6. ⬜ Add config options to `AgentConfig`
7. ⬜ Test with real Signal account
8. ⬜ Add error handling and retries
9. ⬜ (Optional) Add message receiving capability
10. ⬜ Update README with Signal integration docs
