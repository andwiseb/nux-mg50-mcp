class NuxError(RuntimeError):
    """Base error exposed as a useful MCP/CLI message."""


class BridgeError(NuxError):
    """The native macOS accessibility bridge failed."""


class ControlNotFound(NuxError):
    """A requested NUX Audio control could not be found."""


class ValidationError(NuxError):
    """A tone request is invalid or unsafe to apply."""
