"""High-level API for sending Signal messages.

Provides a simple interface for sending messages via signal-cli.
"""

import logging
import os
from typing import Any, Optional

from rune.integrations.signal.client import signal_rpc_request
from rune.integrations.signal.exceptions import SignalSendError

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
    base_url: str = "http://localhost:7583"
) -> dict[str, Any]:
    """
    Send a Signal message.

    Args:
        to: Recipient (phone number, group ID, or username)
        text: Message text to send
        account: Sender account (phone number). If None, uses default account.
        attachments: Optional list of file paths to attach
        base_url: URL of signal-cli daemon

    Returns:
        Result dictionary with:
          - success: bool
          - message_id: str (if successful)
          - timestamp: int (if successful)

    Raises:
        SignalSendError: If sending fails

    Examples:
        >>> send_signal_message("+1234567890", "Hello!")
        {'success': True, 'message_id': '...', 'timestamp': 1234567890}

        >>> send_signal_message(
        ...     "group:abc123",
        ...     "Meeting at 3pm",
        ...     attachments=["agenda.pdf"]
        ... )
    """
    # Parse recipient
    try:
        recipient_params = parse_recipient(to)
    except SignalSendError:
        raise
    except Exception as e:
        raise SignalSendError(f"Failed to parse recipient '{to}': {e}")

    # Build RPC parameters
    params: dict[str, Any] = {
        "message": text,
        **recipient_params
    }

    # Add account if specified
    if account:
        params["account"] = account

    # Handle attachments
    if attachments:
        validated_attachments = []
        for path in attachments:
            # Convert to absolute path
            abs_path = os.path.abspath(path)

            # Check file exists
            if not os.path.exists(abs_path):
                raise SignalSendError(f"Attachment not found: {abs_path}")

            # Check file is readable
            if not os.path.isfile(abs_path):
                raise SignalSendError(f"Attachment is not a file: {abs_path}")

            validated_attachments.append(abs_path)

        params["attachments"] = validated_attachments

    # Send via RPC
    logger.info(f"Sending Signal message to {to}")
    logger.debug(f"Message: {text[:100]}...")

    try:
        result = signal_rpc_request("send", params, base_url=base_url)
    except Exception as e:
        raise SignalSendError(f"Failed to send message: {e}")

    # Extract useful info from result
    response = {
        "success": True,
        "message_id": result.get("messageId"),
        "timestamp": result.get("timestamp")
    }

    logger.info(f"Message sent successfully (ID: {response['message_id']})")
    return response
