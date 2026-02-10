"""Signal messaging integration for Rune.

Supports multiple backends via the transport layer:

* **signalcli** -- local ``signal-cli`` JSON-RPC daemon (original)
* **rest** -- ``bbernhard/signal-cli-rest-api`` Docker container
* **webhook** -- generic HTTP POST to any URL

Basic usage (default signal-cli backend):
    >>> from rune.integrations.signal import send_signal_message
    >>> send_signal_message("+1234567890", "Hello from Rune!")

Using the REST API backend (Docker, no local signal-cli):
    >>> from rune.integrations.signal import send_signal_message
    >>> from rune.integrations.signal.transport import RESTTransport
    >>> t = RESTTransport(base_url="http://localhost:8080")
    >>> send_signal_message("+1234567890", "Hello!", transport=t)

Using a webhook backend (n8n, Make.com, custom server):
    >>> from rune.integrations.signal.transport import WebhookTransport
    >>> t = WebhookTransport("https://hooks.example.com/signal")
    >>> send_signal_message("+1234567890", "Hello!", transport=t)

With daemon management (signal-cli only):
    >>> from rune.integrations.signal import start_signal_daemon, stop_signal_daemon
    >>> daemon = start_signal_daemon(account="+1234567890")
    >>> # ... send messages ...
    >>> stop_signal_daemon(daemon)

For more details, see docs/2026-02-09/signal-integration/docs.md
"""

from rune.integrations.signal.daemon import (
    is_daemon_running,
    start_signal_daemon,
    stop_signal_daemon,
    wait_for_daemon_ready,
)
from rune.integrations.signal.exceptions import (
    SignalDaemonError,
    SignalError,
    SignalRPCError,
    SignalSendError,
)
from rune.integrations.signal.send import send_signal_message
from rune.integrations.signal.transport import (
    RESTTransport,
    SignalCLITransport,
    SignalTransport,
    WebhookTransport,
    create_transport,
)

__all__ = [
    # Main API
    "send_signal_message",
    # Transports
    "SignalTransport",
    "SignalCLITransport",
    "RESTTransport",
    "WebhookTransport",
    "create_transport",
    # Daemon management (signal-cli only)
    "start_signal_daemon",
    "stop_signal_daemon",
    "wait_for_daemon_ready",
    "is_daemon_running",
    # Exceptions
    "SignalError",
    "SignalDaemonError",
    "SignalRPCError",
    "SignalSendError",
]
