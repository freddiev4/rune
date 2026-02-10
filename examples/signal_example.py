"""Example: Using Signal messaging with Rune.

This example shows how to use the Signal integration to send
notifications from your Rune agent.

Prerequisites:
    1. Install signal-cli: brew install signal-cli
    2. Link your Signal account: signal-cli -a +YOUR_PHONE link -n "Rune Agent"
    3. Start the daemon: signal-cli -a +YOUR_PHONE daemon --http localhost:7583

Usage:
    python examples/signal_example.py
"""

import os
from rune import Agent, AgentConfig


def example_manual_send():
    """Example 1: Manually send a Signal message using the tool."""
    print("Example 1: Manual Signal sending\n")

    # Configure agent with Signal account
    config = AgentConfig(
        model="gpt-4o",
        signal_account="+1234567890",  # Replace with your Signal number
        auto_approve_tools=True
    )

    agent = Agent(config=config)

    # Ask agent to send a Signal message
    result = agent.run(
        "Send me a Signal message at +0987654321 saying "
        "'Hello from Rune! This is a test message.'"
    )

    print(f"\nAgent response:\n{result}")


def example_task_notification():
    """Example 2: Agent sends notification after completing a task."""
    print("\nExample 2: Task completion notification\n")

    config = AgentConfig(
        model="gpt-4o",
        signal_account="+1234567890",
        auto_approve_tools=True
    )

    agent = Agent(config=config)

    # Ask agent to do a task and notify when done
    result = agent.run(
        "Create a file called 'test.txt' with the content 'Hello, World!', "
        "then send me a Signal message at +0987654321 confirming it's done."
    )

    print(f"\nAgent response:\n{result}")


def example_with_attachment():
    """Example 3: Send a Signal message with an attachment."""
    print("\nExample 3: Message with attachment\n")

    config = AgentConfig(
        model="gpt-4o",
        signal_account="+1234567890",
        auto_approve_tools=True
    )

    agent = Agent(config=config)

    # Ask agent to create a file and send it via Signal
    result = agent.run(
        "Create a file called 'report.txt' with some sample data, "
        "then send it to me via Signal at +0987654321 with the message "
        "'Here is your report'."
    )

    print(f"\nAgent response:\n{result}")


def example_direct_api():
    """Example 4: Use Signal API directly (without agent)."""
    print("\nExample 4: Direct API usage\n")

    from rune.integrations.signal import send_signal_message

    try:
        result = send_signal_message(
            to="+0987654321",  # Recipient
            text="Hello from Rune! This is a direct API call.",
            account="+1234567890"  # Your Signal account
        )

        print(f"✓ Message sent successfully!")
        print(f"Message ID: {result['message_id']}")
        print(f"Timestamp: {result['timestamp']}")

    except Exception as e:
        print(f"✗ Failed to send message: {e}")


def example_daemon_management():
    """Example 5: Start and stop daemon programmatically."""
    print("\nExample 5: Daemon management\n")

    from rune.integrations.signal import (
        start_signal_daemon,
        stop_signal_daemon,
        is_daemon_running,
        send_signal_message
    )

    account = "+1234567890"  # Your Signal account

    # Check if daemon is already running
    if is_daemon_running():
        print("✓ Daemon is already running")
    else:
        print("Starting daemon...")
        daemon = start_signal_daemon(account=account)
        print("✓ Daemon started")

        try:
            # Send a message
            result = send_signal_message(
                to="+0987654321",
                text="Test message with managed daemon",
                account=account
            )
            print(f"✓ Message sent: {result['message_id']}")

        finally:
            # Clean up
            print("Stopping daemon...")
            stop_signal_daemon(daemon)
            print("✓ Daemon stopped")


def main():
    """Run examples."""
    print("=" * 60)
    print("Rune Signal Integration Examples")
    print("=" * 60)

    # Check if Signal daemon is running
    from rune.integrations.signal import is_daemon_running

    if not is_daemon_running():
        print("\n⚠️  WARNING: Signal daemon is not running!")
        print("\nPlease start it with:")
        print("  signal-cli -a +YOUR_PHONE daemon --http localhost:7583")
        print("\nOr run example 5 to start it programmatically.")
        return

    print("\n✓ Signal daemon is running\n")

    # Run examples (uncomment the ones you want to try)
    # example_manual_send()
    # example_task_notification()
    # example_with_attachment()
    # example_direct_api()
    # example_daemon_management()

    print("\nNote: Edit this file to configure your phone numbers and uncomment examples.")


if __name__ == "__main__":
    # Set environment variables (optional - can also pass to AgentConfig)
    # os.environ["SIGNAL_ACCOUNT"] = "+1234567890"

    main()
