import threading
import time

class RoomRegistry:
    """
    Thread-safe registry for managing ephemeral chat rooms.
    Designed for 'LOCAL' session mode where rooms are not stored in the DB.
    """
    def __init__(self):
        self._rooms = {}  # {room_id: {created_at, members: set()}}
        self._lock = threading.Lock()

    def create_room(self, room_id):
        with self._lock:
            if room_id in self._rooms:
                return False
            self._rooms[room_id] = {
                'created_at': time.time(),
                'members': set()
            }
            return True

    def add_member(self, room_id, user_sid):
        with self._lock:
            if room_id not in self._rooms:
                return False
            self._rooms[room_id]['members'].add(user_sid)
            return True

    def remove_member(self, room_id, user_sid):
        with self._lock:
            if room_id not in self._rooms:
                return False
            if user_sid in self._rooms[room_id]['members']:
                self._rooms[room_id]['members'].remove(user_sid)
                
            # Auto-cleanup empty rooms
            if not self._rooms[room_id]['members']:
                del self._rooms[room_id]
            return True

    def get_members(self, room_id):
        with self._lock:
            if room_id not in self._rooms:
                return []
            return list(self._rooms[room_id]['members'])

# Global registry instance (dormant)
room_registry = RoomRegistry()
