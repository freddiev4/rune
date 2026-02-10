"""Signal-CLI daemon management.

Handles starting, stopping, and monitoring the signal-cli daemon process.
"""

import logging
import subprocess
import time
from typing import Optional

import httpx

from rune.integrations.signal.exceptions import SignalDaemonError

logger = logging.getLogger(__name__)


def start_signal_daemon(
    account: str,
    host: str = "localhost",
    port: int = 7583,
    timeout: int = 30
) -> subprocess.Popen:
    """
    Start signal-cli in daemon mode.

    Args:
        account: Phone number for Signal account (e.g., "+1234567890")
        host: Host to bind daemon to
        port: Port to bind daemon to
        timeout: Seconds to wait for daemon to become ready

    Returns:
        Process handle for the running daemon

    Raises:
        SignalDaemonError: If daemon fails to start or become ready
    """
    # Build command
    cmd = [
        "signal-cli",
        "-a", account,
        "daemon",
        "--http", f"{host}:{port}"
    ]

    logger.info(f"Starting signal-cli daemon: {' '.join(cmd)}")

    try:
        # Start the daemon process
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
    except FileNotFoundError:
        raise SignalDaemonError(
            "signal-cli not found. Please install it:\n"
            "  macOS: brew install signal-cli\n"
            "  Linux: https://github.com/AsamK/signal-cli/releases"
        )
    except Exception as e:
        raise SignalDaemonError(f"Failed to start signal-cli daemon: {e}")

    # Wait for daemon to become ready
    base_url = f"http://{host}:{port}"
    try:
        if not wait_for_daemon_ready(base_url, timeout):
            stop_signal_daemon(process)
            raise SignalDaemonError(
                f"Daemon failed to become ready within {timeout} seconds"
            )
    except Exception as e:
        stop_signal_daemon(process)
        raise SignalDaemonError(f"Failed to start daemon: {e}")

    logger.info(f"Signal daemon started successfully on {base_url}")
    return process


def stop_signal_daemon(process: subprocess.Popen) -> None:
    """
    Stop the signal-cli daemon gracefully.

    Args:
        process: Process handle from start_signal_daemon()
    """
    if process.poll() is None:  # Process still running
        logger.info("Stopping signal-cli daemon...")
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            logger.warning("Daemon didn't stop gracefully, forcing...")
            process.kill()
            process.wait()
        logger.info("Signal daemon stopped")


def wait_for_daemon_ready(
    base_url: str = "http://localhost:7583",
    timeout: int = 30,
    check_interval: float = 0.5
) -> bool:
    """
    Wait for signal-cli daemon to become ready.

    Polls the daemon's health endpoint until it responds or timeout is reached.

    Args:
        base_url: Base URL of the daemon
        timeout: Maximum seconds to wait
        check_interval: Seconds between checks

    Returns:
        True if daemon is ready, False if timeout reached
    """
    start_time = time.time()
    health_url = f"{base_url}/api/v1/health"

    logger.debug(f"Waiting for daemon at {health_url}")

    while time.time() - start_time < timeout:
        try:
            response = httpx.get(health_url, timeout=1.0)
            if response.status_code == 200:
                logger.debug("Daemon is ready")
                return True
        except (httpx.ConnectError, httpx.TimeoutException):
            # Daemon not ready yet, keep waiting
            pass
        except Exception as e:
            logger.debug(f"Unexpected error checking daemon health: {e}")

        time.sleep(check_interval)

    logger.warning(f"Daemon did not become ready within {timeout} seconds")
    return False


def is_daemon_running(base_url: str = "http://localhost:7583") -> bool:
    """
    Check if a signal-cli daemon is already running.

    Args:
        base_url: Base URL of the daemon

    Returns:
        True if daemon is running and responding, False otherwise
    """
    try:
        response = httpx.get(f"{base_url}/api/v1/health", timeout=2.0)
        return response.status_code == 200
    except Exception:
        return False
