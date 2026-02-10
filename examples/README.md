# Rune Examples

This directory contains example scripts demonstrating various Rune features.

## Available Examples

### signal_example.py
Demonstrates Signal messaging integration:
- Manual message sending via agent
- Task completion notifications
- Messages with attachments
- Direct API usage
- Daemon management

**Prerequisites:**
1. Install signal-cli: `brew install signal-cli`
2. Link your Signal account: `signal-cli -a +PHONE link -n "Rune"`
3. Start daemon: `signal-cli -a +PHONE daemon --http localhost:7583`

**Usage:**
```bash
python examples/signal_example.py
```

See the file for multiple examples you can uncomment and try.

## More Examples

Add more example scripts here as Rune grows!
