"""HTTP RPC client for signal-cli daemon.

Implements JSON-RPC 2.0 communication with the signal-cli HTTP API.
"""

import logging
import uuid
from typing import Any

import httpx

from rune.integrations.signal.exceptions import SignalRPCError

logger = logging.getLogger(__name__)


def signal_rpc_request(
    method: str,
    params: dict[str, Any],
    base_url: str = "http://localhost:7583",
    timeout: int = 10
) -> dict[str, Any]:
    """
    Send a JSON-RPC 2.0 request to signal-cli daemon.

    Args:
        method: RPC method name (e.g., "send", "listAccounts")
        params: Method parameters as a dictionary
        base_url: Base URL of the signal-cli daemon
        timeout: Request timeout in seconds

    Returns:
        RPC result dictionary

    Raises:
        SignalRPCError: If the RPC call fails or returns an error
    """
    # Build JSON-RPC 2.0 request
    request_id = str(uuid.uuid4())
    payload = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
        "params": params
    }

    rpc_url = f"{base_url}/api/v1/rpc"
    logger.debug(f"RPC request: {method} -> {rpc_url}")
    logger.debug(f"Params: {params}")

    try:
        response = httpx.post(
            rpc_url,
            json=payload,
            timeout=timeout
        )
        response.raise_for_status()
    except httpx.ConnectError:
        raise SignalRPCError(
            "Cannot connect to signal-cli daemon. Is it running?\n"
            "Start it with: signal-cli -a +PHONE daemon --http localhost:7583"
        )
    except httpx.TimeoutException:
        raise SignalRPCError(f"Request to signal-cli timed out after {timeout}s")
    except httpx.HTTPStatusError as e:
        raise SignalRPCError(f"HTTP error from signal-cli: {e}")
    except Exception as e:
        raise SignalRPCError(f"Failed to communicate with signal-cli: {e}")

    # Parse JSON-RPC response
    try:
        data = response.json()
    except Exception as e:
        raise SignalRPCError(f"Invalid JSON response from signal-cli: {e}")

    # Check for RPC error
    if "error" in data:
        error = data["error"]
        error_code = error.get("code", -1)
        error_message = error.get("message", "Unknown error")
        logger.error(f"RPC error {error_code}: {error_message}")
        raise SignalRPCError(error_message, code=error_code)

    # Return result
    if "result" not in data:
        raise SignalRPCError("RPC response missing 'result' field")

    logger.debug(f"RPC success: {method}")
    return data["result"]


def check_daemon_health(base_url: str = "http://localhost:7583") -> dict[str, Any]:
    """
    Check the health/status of the signal-cli daemon.

    Args:
        base_url: Base URL of the daemon

    Returns:
        Health check response

    Raises:
        SignalRPCError: If health check fails
    """
    try:
        response = httpx.get(f"{base_url}/api/v1/health", timeout=5.0)
        response.raise_for_status()
        return {"status": "ok", "status_code": response.status_code}
    except Exception as e:
        raise SignalRPCError(f"Daemon health check failed: {e}")
