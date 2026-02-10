"""Exceptions for Signal integration."""


class SignalError(Exception):
    """Base exception for Signal-related errors."""
    pass


class SignalDaemonError(SignalError):
    """Exception raised when signal-cli daemon fails."""
    pass


class SignalRPCError(SignalError):
    """Exception raised when RPC call to signal-cli fails."""

    def __init__(self, message: str, code: int | None = None):
        super().__init__(message)
        self.code = code


class SignalSendError(SignalError):
    """Exception raised when sending a Signal message fails."""
    pass
