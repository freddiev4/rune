"""Signal messaging integration for Rune.

This module provides Signal messaging capabilities using signal-cli.

Basic usage:
    >>> from rune.integrations.signal import send_signal_message
    >>> send_signal_message("+1234567890", "Hello from Rune!")

With daemon management:
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

__all__ = [
    # Main API
    "send_signal_message",
    # Daemon management
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
