import json
from .enums import SessionType
# We avoid importing models/extensions directly to prevent circular imports 
# until this module is actively wired up.

class SessionManager:
    """
    Manages user session lifecycle, bridging the gap between 
    Flask-Login (User model) and Socket.IO (ephemeral connections).
    """

    def __init__(self):
        # Structure: {user_id: {sid: {start: time, last_active: time, ip: ...}}}
        self.active_sessions = {} 
        self.security_events = [] 
        # Tuning parameters
        self.MAX_CONCURRENT_SESSIONS = 3
        self.INCIDENT_WEIGHT = 10

    def resolve_session_type(self, user):
        """
        Determines if a user is in ACCOUNT or LOCAL mode based on metadata.
        """
        if not user.is_authenticated:
            return None
            
        if hasattr(user, 'session_metadata') and user.session_metadata:
            try:
                metadata = json.loads(user.session_metadata)
                if metadata.get('mode') == 'local':
                    return SessionType.LOCAL
            except:
                pass
        return SessionType.ACCOUNT

    def register_session(self, user_id, sid, metadata=None):
        """
        Records a new session start with metadata.
        """
        import time
        if user_id not in self.active_sessions:
            self.active_sessions[user_id] = {}
        
        self.active_sessions[user_id][sid] = {
            "start": time.time(),
            "last_active": time.time(),
            "metadata": metadata or {}
        }
        print(f"[SessionManager] Registered socket {sid} for user {user_id}")
        return self._analyze_risk(user_id)

    def terminate_session(self, sid):
        """
        Cleanup on disconnect.
        """
        for user_id, sessions in self.active_sessions.items():
            if sid in sessions:
                del sessions[sid]
                print(f"[SessionManager] Terminated socket {sid} for user {user_id}")
                # Clean up user entry if empty? Maybe keep for history? 
                # For now, keep user key to avoid constant create/delete
                break

    def register_logical_session(self, username, data):
        """
        Registers a logical session event (e.g. login).
        """
        self.security_events.append({
            "timestamp": "now",
            "user": username,
            "type": "LOGIN",
            "details": data
        })

    def report_security_incident(self, username, error_details):
        """
        Report a security incident to the Trust Layer.
        """
        self.security_events.append({
            "timestamp": "now",
            "user": username,
            "type": "SECURITY_INCIDENT",
            "details": error_details
        })
        print(f"[SessionManager] Security Incident for {username}: {error_details}")
        # In a real app, we'd look up user_id from username to trigger risk calc immediately

    def _analyze_risk(self, user_id):
        """
        Internal risk calculator. Returns (score, status).
        Score 0-100 (0=High Risk, 100=Secure).
        """
        score = 100
        active_count = len(self.active_sessions.get(user_id, {}))
        
        # Deduct for concurrent sessions
        if active_count > 1:
            score -= (active_count - 1) * 10
        
        if active_count > self.MAX_CONCURRENT_SESSIONS:
            score -= 50
            
        # Deduct for recent incidents (simple check for now)
        # Note: mapping username to user_id is tricky here without DB access, 
        # so we skip specific incident counting for this MVP step.
        
        return max(0, score)

    def get_dashboard_stats(self, user_id):
        """
        Returns stats for the dashboard API.
        """
        sessions = self.active_sessions.get(user_id, {})
        active_socket_count = len(sessions)
        risk_score = self._analyze_risk(user_id)
        
        security_status = "SECURE"
        if risk_score < 50:
            security_status = "CRITICAL"
        elif risk_score < 80:
            security_status = "WARNING"

        return {
            "active_sockets": active_socket_count,
            "security_status": security_status,
            "trust_score": risk_score,
            "event_count": len(self.security_events)
        }

# Global instance (dormant)
session_manager = SessionManager()
