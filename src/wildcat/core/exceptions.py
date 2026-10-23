"""Custom exception hierarchy for Wildcat."""

class WildcatError(Exception):
    """Base class for all Wildcat errors."""

class ConnectorError(WildcatError):
    """Connector/hardware communication errors."""

class ConnectorNotOpenError(ConnectorError):
    pass

class ProtocolError(WildcatError):
    """Protocol-level errors."""

class CarError(WildcatError):
    """Vehicle-specific errors."""

class DiagnosticError(WildcatError):
    """Diagnostic operation errors."""

class ProgrammingError(WildcatError):
    """Programming/flash errors."""

class GUIError(WildcatError):
    """GUI errors."""

class SessionError(WildcatError):
    """Session errors."""

class ConfigurationError(WildcatError):
    """Configuration errors."""

__all__ = [
    "CarError",
    "ConfigurationError",
    "ConnectorError",
    "ConnectorNotOpenError",
    "DiagnosticError",
    "GUIError",
    "ProgrammingError",
    "ProtocolError",
    "SessionError",
    "WildcatError",
]
