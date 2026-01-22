from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_socketio import SocketIO

db = SQLAlchemy()
login_manager = LoginManager()
bcrypt = Bcrypt()
socketio = SocketIO()

# -----------------------------------------------------------------------------
# EXTENSION POINTS FOR FUTURE LAYERS
# -----------------------------------------------------------------------------
# This section reserves space for future integration of Trust & Safety layers.
# No logic changes are currently implemented.

class EventDispatcherStub:
    """
    Placeholder for a future event bus to decouple security layers.
    Currently a no-op that logs valid events for debugging.
    """
    def __init__(self):
        self.listeners = {}

    def subscribe(self, event_type, callback):
        """Placeholder: Subscribe to a security event."""
        if event_type not in self.listeners:
            self.listeners[event_type] = []
        self.listeners[event_type].append(callback)

    def dispatch(self, event_type, payload):
        """Placeholder: Dispatch a security event."""
        # In the future, this will notify registered listeners.
        pass

# Global event dispatcher instance
event_dispatcher = EventDispatcherStub()
