#!/usr/bin/env python3
"""Quick test script for Signal integration.

Run this to verify the Signal integration is working.
"""

import sys


def test_imports():
    """Test that all Signal modules can be imported."""
    print("Testing imports...")
    try:
        from rune.integrations.signal import (
            send_signal_message,
            start_signal_daemon,
            stop_signal_daemon,
            is_daemon_running,
            SignalError,
            SignalDaemonError,
            SignalRPCError,
            SignalSendError,
        )
        print("✓ All imports successful")
        return True
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False


def test_daemon_check():
    """Test daemon health check."""
    print("\nTesting daemon check...")
    try:
        from rune.integrations.signal import is_daemon_running

        if is_daemon_running():
            print("✓ Daemon is running")
            return True
        else:
            print("⚠ Daemon is not running")
            print("\nTo start the daemon:")
            print("  signal-cli -a +YOUR_PHONE daemon --http localhost:7583")
            return False
    except Exception as e:
        print(f"✗ Daemon check failed: {e}")
        return False


def test_tool_registration():
    """Test that signal_send tool is registered."""
    print("\nTesting tool registration...")
    try:
        from rune.harness.tools import TOOL_DEFINITIONS

        tool_names = [t["function"]["name"] for t in TOOL_DEFINITIONS]
        if "signal_send" in tool_names:
            print("✓ signal_send tool is registered")
            return True
        else:
            print("✗ signal_send tool not found in TOOL_DEFINITIONS")
            return False
    except Exception as e:
        print(f"✗ Tool registration check failed: {e}")
        return False


def test_agent_config():
    """Test that AgentConfig has signal_account field."""
    print("\nTesting AgentConfig...")
    try:
        from rune import AgentConfig

        config = AgentConfig(signal_account="+1234567890")
        if config.signal_account == "+1234567890":
            print("✓ AgentConfig.signal_account works")
            return True
        else:
            print("✗ signal_account field not working correctly")
            return False
    except Exception as e:
        print(f"✗ AgentConfig test failed: {e}")
        return False


def test_send_message_dry_run():
    """Test sending a message (will fail if daemon not running)."""
    print("\nTesting message send (dry run)...")
    try:
        from rune.integrations.signal import send_signal_message, is_daemon_running

        if not is_daemon_running():
            print("⊘ Skipping (daemon not running)")
            return None

        # Try to send to invalid recipient (should fail gracefully)
        try:
            result = send_signal_message(
                to="+99999999999",  # Invalid number
                text="Test message",
                account="+1234567890"  # Replace with your number
            )
            print("⚠ Message sent (unexpected)")
            return False
        except Exception as e:
            print(f"✓ Send message API works (failed as expected: {type(e).__name__})")
            return True
    except Exception as e:
        print(f"✗ Send message test failed: {e}")
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("Signal Integration Test Suite")
    print("=" * 60)

    results = []

    # Run tests
    results.append(("Imports", test_imports()))
    results.append(("Daemon Check", test_daemon_check()))
    results.append(("Tool Registration", test_tool_registration()))
    results.append(("AgentConfig", test_agent_config()))
    results.append(("Send Message", test_send_message_dry_run()))

    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)

    passed = sum(1 for _, r in results if r is True)
    failed = sum(1 for _, r in results if r is False)
    skipped = sum(1 for _, r in results if r is None)

    for name, result in results:
        if result is True:
            status = "✓ PASS"
        elif result is False:
            status = "✗ FAIL"
        else:
            status = "⊘ SKIP"
        print(f"  {status}: {name}")

    print(f"\nTotal: {passed} passed, {failed} failed, {skipped} skipped")

    if failed > 0:
        print("\n⚠ Some tests failed. Check the output above for details.")
        sys.exit(1)
    elif passed == 0:
        print("\n⚠ No tests passed. Signal integration may not be working.")
        sys.exit(1)
    else:
        print("\n✓ Signal integration is ready!")
        sys.exit(0)


if __name__ == "__main__":
    main()
