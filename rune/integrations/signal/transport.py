"""Transport abstraction for Signal message sending.

Decouples the Signal integration from any specific backend (signal-cli,
REST API, webhooks, etc.) so users can choose the approach that fits their
deployment.

Three built-in transports:

* **SignalCLITransport** -- talks to a local ``signal-cli`` JSON-RPC daemon
  (the original backend).
* **RESTTransport** -- talks to the ``bbernhard/signal-cli-rest-api`` Docker
  container's REST interface.  No local ``signal-cli`` install required.
* **WebhookTransport** -- POSTs a JSON payload to an arbitrary URL, enabling
  integration with n8n, Make.com, Zapier, or any custom HTTP handler.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Optional

import httpx

from rune.integrations.signal.exceptions import SignalRPCError, SignalSendError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class SignalTransport(ABC):
    """Base class for all Signal transports."""

    @abstractmethod
    def send(
        self,
        to: str,
        text: str,
        *,
        account: Optional[str] = None,
        attachments: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Send a message and return a result dict.

        The returned dict should always contain at least::

            {"success": True, "message_id": ..., "timestamp": ...}

        Raises ``SignalSendError`` on failure.
        """

    @abstractmethod
    def health_check(self) -> dict[str, Any]:
        """Return backend health information.

        Raises ``SignalRPCError`` on failure.
        """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable transport name for logging / error messages."""


# ---------------------------------------------------------------------------
# 1) signal-cli JSON-RPC daemon
# ---------------------------------------------------------------------------

class SignalCLITransport(SignalTransport):
    """Talks to a local ``signal-cli`` daemon over JSON-RPC 2.0.

    This is the original backend.  Requires ``signal-cli`` to be installed
    and running as a daemon::

        signal-cli -a +PHONE daemon --http localhost:7583
    """

    def __init__(self, base_url: str = "http://localhost:7583") -> None:
        self.base_url = base_url.rstrip("/")

    @property
    def name(self) -> str:
        return "signal-cli"

    # -- public API --------------------------------------------------------

    def send(
        self,
        to: str,
        text: str,
        *,
        account: Optional[str] = None,
        attachments: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        from rune.integrations.signal.send import parse_recipient

        recipient_params = parse_recipient(to)

        params: dict[str, Any] = {"message": text, **recipient_params}
        if account:
            params["account"] = account
        if attachments:
            params["attachments"] = attachments

        result = self._rpc("send", params)
        return {
            "success": True,
            "message_id": result.get("messageId"),
            "timestamp": result.get("timestamp"),
        }

    def health_check(self) -> dict[str, Any]:
        try:
            resp = httpx.get(f"{self.base_url}/api/v1/health", timeout=5.0)
            resp.raise_for_status()
            return {"status": "ok", "status_code": resp.status_code}
        except Exception as e:
            raise SignalRPCError(f"Daemon health check failed: {e}")

    # -- internals ---------------------------------------------------------

    def _rpc(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Thin wrapper that delegates to the existing RPC client."""
        from rune.integrations.signal.client import signal_rpc_request

        return signal_rpc_request(method, params, base_url=self.base_url)


# ---------------------------------------------------------------------------
# 2) bbernhard/signal-cli-rest-api  (Docker)
# ---------------------------------------------------------------------------

class RESTTransport(SignalTransport):
    """Talks to the ``bbernhard/signal-cli-rest-api`` Docker container.

    This is a popular community Docker image that wraps signal-cli in a
    plain REST API.  Users only need Docker -- no local Java / signal-cli
    install::

        docker run -d --name signal-api -p 8080:8080 \\
            -v $HOME/.local/share/signal-api:/home/.local/share/signal-cli \\
            -e MODE=normal \\
            bbernhard/signal-cli-rest-api

    The REST endpoints used:

    * ``POST /v2/send``     -- send a text message
    * ``GET  /v1/about``    -- health / version info
    """

    def __init__(self, base_url: str = "http://localhost:8080") -> None:
        self.base_url = base_url.rstrip("/")

    @property
    def name(self) -> str:
        return "rest"

    def send(
        self,
        to: str,
        text: str,
        *,
        account: Optional[str] = None,
        attachments: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"message": text}

        # Determine recipient type
        stripped = to.strip()
        if stripped.startswith("signal:"):
            stripped = stripped[7:]

        if stripped.startswith("group:"):
            # For the REST API v2, groups are sent via /v2/send with a
            # "recipients" list left empty and "group_id" set instead.
            # Actually, the v1/send/{number} endpoint doesn't support groups;
            # we use v2/send which accepts JSON body.
            pass  # handled below

        # Build the v2/send payload (works for all recipient types)
        if stripped.startswith("group:"):
            group_id = stripped[6:].strip()
            if not group_id:
                raise SignalSendError("Invalid group ID format")
            # The REST API expects base64-encoded group id
            payload["recipients"] = []
            payload["group_id"] = group_id
        elif stripped.startswith("username:") or stripped.startswith("u:"):
            prefix_len = 9 if stripped.startswith("username:") else 2
            username = stripped[prefix_len:].strip()
            if not username:
                raise SignalSendError("Invalid username format")
            payload["recipients"] = [username]
        elif stripped.startswith("+"):
            payload["recipients"] = [stripped]
        else:
            raise SignalSendError(
                f"Phone numbers must start with '+': {stripped}\n"
                "Supported formats:\n"
                "  - Phone: +1234567890\n"
                "  - Group: group:groupId\n"
                "  - Username: u:alice or username:alice"
            )

        # The v2/send endpoint requires the sender number
        if account:
            payload["number"] = account

        # Attachments: the REST API accepts base64-encoded attachments in
        # the JSON body.  For simplicity we read them here.
        if attachments:
            import base64
            import os

            encoded = []
            for path in attachments:
                abs_path = os.path.abspath(path)
                if not os.path.isfile(abs_path):
                    raise SignalSendError(f"Attachment not found: {abs_path}")
                with open(abs_path, "rb") as f:
                    data = base64.b64encode(f.read()).decode()
                encoded.append(data)
            payload["base64_attachments"] = encoded

        url = f"{self.base_url}/v2/send"
        logger.debug(f"REST send -> {url}")

        try:
            resp = httpx.post(url, json=payload, timeout=15)
            resp.raise_for_status()
        except httpx.ConnectError:
            raise SignalSendError(
                "Cannot connect to signal-cli-rest-api. Is the container running?\n"
                "Start it with:\n"
                "  docker run -d -p 8080:8080 bbernhard/signal-cli-rest-api"
            )
        except httpx.HTTPStatusError as e:
            raise SignalSendError(f"REST API error: {e.response.status_code} {e.response.text}")
        except Exception as e:
            raise SignalSendError(f"REST API request failed: {e}")

        try:
            data = resp.json()
        except Exception:
            data = {}

        return {
            "success": True,
            "message_id": data.get("id") or data.get("messageId"),
            "timestamp": data.get("timestamp"),
        }

    def health_check(self) -> dict[str, Any]:
        try:
            resp = httpx.get(f"{self.base_url}/v1/about", timeout=5.0)
            resp.raise_for_status()
            return {"status": "ok", **resp.json()}
        except Exception as e:
            raise SignalRPCError(f"REST API health check failed: {e}")


# ---------------------------------------------------------------------------
# 3) Webhook (generic HTTP POST)
# ---------------------------------------------------------------------------

class WebhookTransport(SignalTransport):
    """POSTs a JSON payload to any URL.

    This is the most flexible backend -- it doesn't speak Signal protocol at
    all.  Instead, it fires a webhook that an external service (n8n,
    Make.com, Zapier, a custom server, etc.) can pick up and relay to Signal
    however it likes.

    The JSON body sent to the webhook::

        {
            "to": "+1234567890",
            "message": "Hello!",
            "account": "+0987654321",   // if provided
            "attachments": ["/path"],   // if provided
            "meta": { ... }             // optional extra headers/data
        }

    Extra headers (e.g. for auth) can be passed via *headers*.
    """

    def __init__(
        self,
        webhook_url: str,
        headers: Optional[dict[str, str]] = None,
    ) -> None:
        self.webhook_url = webhook_url
        self.headers = headers or {}

    @property
    def name(self) -> str:
        return "webhook"

    def send(
        self,
        to: str,
        text: str,
        *,
        account: Optional[str] = None,
        attachments: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"to": to, "message": text}
        if account:
            payload["account"] = account
        if attachments:
            payload["attachments"] = attachments

        logger.debug(f"Webhook POST -> {self.webhook_url}")

        try:
            resp = httpx.post(
                self.webhook_url,
                json=payload,
                headers=self.headers,
                timeout=15,
            )
            resp.raise_for_status()
        except httpx.ConnectError:
            raise SignalSendError(
                f"Cannot connect to webhook URL: {self.webhook_url}"
            )
        except httpx.HTTPStatusError as e:
            raise SignalSendError(
                f"Webhook returned {e.response.status_code}: {e.response.text}"
            )
        except Exception as e:
            raise SignalSendError(f"Webhook request failed: {e}")

        # Try to parse response but don't require it
        try:
            data = resp.json()
        except Exception:
            data = {}

        return {
            "success": True,
            "message_id": data.get("message_id") or data.get("id"),
            "timestamp": data.get("timestamp"),
        }

    def health_check(self) -> dict[str, Any]:
        # Webhooks don't have a standard health endpoint.
        # We just check connectivity.
        try:
            resp = httpx.options(self.webhook_url, timeout=5.0)
            return {"status": "ok", "status_code": resp.status_code}
        except Exception as e:
            raise SignalRPCError(f"Webhook health check failed: {e}")


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def create_transport(
    backend: str = "signalcli",
    *,
    base_url: Optional[str] = None,
    webhook_url: Optional[str] = None,
    webhook_headers: Optional[dict[str, str]] = None,
) -> SignalTransport:
    """Create a transport instance from a backend name.

    Args:
        backend: One of ``"signalcli"``, ``"rest"``, or ``"webhook"``.
        base_url: Base URL for signalcli/rest backends.
        webhook_url: Target URL for the webhook backend.
        webhook_headers: Extra HTTP headers for the webhook backend.

    Returns:
        A configured :class:`SignalTransport` instance.

    Raises:
        ValueError: If the backend name is unknown or required args are missing.
    """
    backend = backend.lower().strip()

    if backend == "signalcli":
        return SignalCLITransport(base_url=base_url or "http://localhost:7583")

    if backend == "rest":
        return RESTTransport(base_url=base_url or "http://localhost:8080")

    if backend == "webhook":
        if not webhook_url:
            raise ValueError("webhook_url is required for the webhook backend")
        return WebhookTransport(webhook_url, headers=webhook_headers)

    raise ValueError(
        f"Unknown Signal backend: {backend!r}. "
        "Choose from: signalcli, rest, webhook"
    )
