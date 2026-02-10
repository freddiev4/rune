"""High-level API for sending Signal messages.

Provides a simple interface for sending messages via any configured
transport backend (signal-cli, REST API, or webhook).
"""

import logging
import os
from typing import Any, Optional

from rune.integrations.signal.exceptions import SignalSendError
from rune.integrations.signal.transport import SignalTransport, create_transport

logger = logging.getLogger(__name__)


def parse_recipient(recipient: str) -> dict[str, Any]:
    """
    Parse recipient string into signal-cli RPC format.

    Supports multiple formats:
      - Phone number: "+1234567890" -> {"recipient": ["+1234567890"]}
      - Group ID: "group:abc123" -> {"groupId": "abc123"}
      - Username: "u:alice" or "username:alice" -> {"username": "alice"}

    Args:
        recipient: Recipient identifier string

    Returns:
        Dictionary with appropriate RPC parameter

    Raises:
        SignalSendError: If recipient format is invalid
    """
    recipient = recipient.strip()

    # Strip "signal:" prefix if present
    if recipient.startswith("signal:"):
        recipient = recipient[7:]

    # Handle group
    if recipient.startswith("group:"):
        group_id = recipient[6:].strip()
        if not group_id:
            raise SignalSendError("Invalid group ID format")
        return {"groupId": group_id}

    # Handle username
    if recipient.startswith("username:"):
        username = recipient[9:].strip()
        if not username:
            raise SignalSendError("Invalid username format")
        return {"username": username}

    if recipient.startswith("u:"):
        username = recipient[2:].strip()
        if not username:
            raise SignalSendError("Invalid username format")
        return {"username": username}

    # Assume phone number
    if not recipient.startswith("+"):
        raise SignalSendError(
            f"Phone numbers must start with '+': {recipient}\n"
            "Supported formats:\n"
            "  - Phone: +1234567890\n"
            "  - Group: group:groupId\n"
            "  - Username: u:alice or username:alice"
        )

    return {"recipient": [recipient]}


def send_signal_message(
    to: str,
    text: str,
    *,
    account: Optional[str] = None,
    attachments: Optional[list[str]] = None,
    base_url: str = "http://localhost:7583",
    transport: Optional[SignalTransport] = None,
) -> dict[str, Any]:
    """
    Send a Signal message.

    When *transport* is provided it is used directly.  Otherwise, a default
    ``SignalCLITransport`` pointing at *base_url* is created (preserving
    backward-compatible behaviour).

    Args:
        to: Recipient (phone number, group ID, or username)
        text: Message text to send
        account: Sender account (phone number). If None, uses default account.
        attachments: Optional list of file paths to attach
        base_url: URL of signal-cli daemon (only used when *transport* is None)
        transport: An explicit :class:`SignalTransport` instance to use.

    Returns:
        Result dictionary with:
          - success: bool
          - message_id: str (if successful)
          - timestamp: int (if successful)

    Raises:
        SignalSendError: If sending fails

    Examples:
        # Default (signal-cli daemon):
        >>> send_signal_message("+1234567890", "Hello!")
        {'success': True, 'message_id': '...', 'timestamp': 1234567890}

        # Explicit transport:
        >>> from rune.integrations.signal.transport import RESTTransport
        >>> t = RESTTransport(base_url="http://localhost:8080")
        >>> send_signal_message("+1234567890", "Hello!", transport=t)
    """
    # Validate attachments up-front (applies to all transports)
    resolved_attachments: list[str] | None = None
    if attachments:
        resolved_attachments = []
        for path in attachments:
            abs_path = os.path.abspath(path)
            if not os.path.exists(abs_path):
                raise SignalSendError(f"Attachment not found: {abs_path}")
            if not os.path.isfile(abs_path):
                raise SignalSendError(f"Attachment is not a file: {abs_path}")
            resolved_attachments.append(abs_path)

    # Build or use the transport
    if transport is None:
        transport = create_transport("signalcli", base_url=base_url)

    logger.info(f"Sending Signal message to {to} via {transport.name}")
    logger.debug(f"Message: {text[:100]}...")

    try:
        return transport.send(
            to,
            text,
            account=account,
            attachments=resolved_attachments,
        )
    except SignalSendError:
        raise
    except Exception as e:
        raise SignalSendError(f"Failed to send message via {transport.name}: {e}")
