"""Typed exceptions for Scribe."""


class ScribeError(Exception):
    """Base exception for the package."""


class ValidationError(ScribeError):
    """Raised when invalid data is supplied to the SDK."""


class ContextError(ScribeError):
    """Raised when lifecycle state is missing or inconsistent."""


class ClosedScopeError(ContextError):
    """Raised when a closed scope is used again."""


class SinkDispatchError(ScribeError):
    """Raised when every sink fails for a dispatch."""
