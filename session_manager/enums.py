from enum import Enum

class SessionType(Enum):
    """
    Defines the type of session active for a user.
    """
    ACCOUNT = "account"   # Standard database-backed user account
    LOCAL = "local"       # Ephemeral session, no database persistence (future feature)

class TransportState(Enum):
    """
    Defines the current state of the client connection.
    """
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    AUTHENTICATED = "authenticated"
