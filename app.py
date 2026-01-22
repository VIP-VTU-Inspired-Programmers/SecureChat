from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
from flask_login import login_user, current_user, logout_user, login_required
from flask_socketio import emit, join_room
import os
import base64
import secrets

from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

from extensions import db, login_manager, bcrypt, socketio, event_dispatcher
from models import User, Message
from session_manager.core import session_manager


# -----------------------------------------------------------------------------
# APP SETUP
# -----------------------------------------------------------------------------
app = Flask(__name__, static_folder="static",template_folder="templates",static_url_path="/static")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-key-change-this")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", "sqlite:///chat.db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

CORS(app)

db.init_app(app)
login_manager.init_app(app)
bcrypt.init_app(app)
socketio.init_app(app, async_mode="threading", cors_allowed_origins="*")
login_manager.login_view = "index"

with app.app_context():
    db.create_all()


# -----------------------------------------------------------------------------
# CRYPTO HELPERS
# -----------------------------------------------------------------------------
def generate_rsa_key_pair():
    private_key = rsa.generate_private_key(
        public_exponent=65537, key_size=2048, backend=default_backend()
    )
    public_key = private_key.public_key()

    return {
        "private_key": private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode(),
        "public_key": public_key.public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode(),
    }


def load_public_key(pem):
    return serialization.load_pem_public_key(pem.encode(), backend=default_backend())


def load_private_key(pem):
    return serialization.load_pem_private_key(
        pem.encode(), password=None, backend=default_backend()
    )


def generate_aes_key():
    return secrets.token_bytes(32)


def encrypt_with_aes(key, plaintext):
    if isinstance(plaintext, str):
        plaintext = plaintext.encode()

    iv = secrets.token_bytes(16)
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()

    pad_len = 16 - len(plaintext) % 16
    padded = plaintext + bytes([pad_len] * pad_len)

    encrypted = encryptor.update(padded) + encryptor.finalize()
    return {
        "iv": base64.b64encode(iv).decode(),
        "ciphertext": base64.b64encode(encrypted).decode(),
    }


def decrypt_with_aes(key, iv, ciphertext):
    iv = base64.b64decode(iv)
    ciphertext = base64.b64decode(ciphertext)

    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()
    return padded[:-padded[-1]]


# -----------------------------------------------------------------------------
# SECURITY EVENT DISPATCHER (SAFE)
# -----------------------------------------------------------------------------
def emit_crypto_event(event_type, payload):
    """
    Dispatches security events safely. 
    Failures here should NEVER crash the application or block authentication.
    """
    try:
        event_dispatcher.dispatch(event_type, payload)
    except Exception as e:
        print(f"[SECURITY] Warning: Dispatcher error for {event_type}: {e}")

    # 🔒 IMPORTANT: Never break auth flow
    try:
        if event_type == "SESSION_STARTED":
            session_manager.register_logical_session(
                payload.get("username"), payload
            )
        elif event_type == "DECRYPT_FAILED":
            session_manager.report_security_incident(
                payload.get("username"), payload.get("error")
            )
    except Exception as e:
        print(f"[SECURITY] Warning: SessionManager hook failed for {event_type}: {e}")


# -----------------------------------------------------------------------------
# ROUTES
# -----------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/static/<path:path>")
def serve_static(path):
    return send_from_directory("static", path)


# -----------------------------------------------------------------------------
# AUTH
# -----------------------------------------------------------------------------
@app.route("/api/register", methods=["POST"])
def register():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify(error="Missing credentials"), 400

    if User.query.filter_by(username=username).first():
        return jsonify(error="User exists"), 400

    keys = generate_rsa_key_pair()
    user = User(
        username=username,
        password_hash=bcrypt.generate_password_hash(password).decode(),
        public_key=keys["public_key"],
        private_key=keys["private_key"],
    )

    db.session.add(user)
    db.session.commit()
    login_user(user)

    emit_crypto_event("KEY_CREATED", {"username": username})
    return jsonify(success=True, username=username)


@app.route("/api/login", methods=["POST"])
def login():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    user = User.query.filter_by(username=username).first()

    if user and bcrypt.check_password_hash(user.password_hash, password):
        login_user(user)

        print(f"[LOGIN] Success: {username}")
        emit_crypto_event("SESSION_STARTED", {"username": username, "via": "login"})

        return jsonify(success=True, username=username)

    print(f"[LOGIN] Failed for {username}")
    return jsonify(error="Invalid credentials"), 401


@app.route("/api/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return jsonify(success=True)


@app.route("/api/dashboard", methods=["GET"])
@login_required
def dashboard_stats():
    stats = session_manager.get_dashboard_stats(current_user.id)
    return jsonify(stats)


@app.route("/api/security-status", methods=["GET"])
@login_required
def security_status():
    """
    Detailed security status for the user.
    """
    stats = session_manager.get_dashboard_stats(current_user.id)
    return jsonify(stats) # Reuse logic for now, can be specialized later


@app.route("/api/users", methods=["GET"])
@login_required
def get_users():
    users = User.query.all()
    user_list = [user.username for user in users]
    return jsonify(success=True, users=user_list)


# -----------------------------------------------------------------------------
# CHAT API
# -----------------------------------------------------------------------------
@app.route("/api/encrypt-message", methods=["POST"])
@login_required
def encrypt_message():
    data = request.json
    recipient = User.query.filter_by(username=data.get("recipient")).first()

    if not recipient:
        return jsonify(error="Recipient not found"), 404

    aes_key = generate_aes_key()
    encrypted = encrypt_with_aes(aes_key, data.get("message"))

    encrypted_key = recipient.public_key
    encrypted_key = serialization.load_pem_public_key(
        encrypted_key.encode(), backend=default_backend()
    ).encrypt(
        aes_key,
        padding.OAEP(
            mgf=padding.MGF1(hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )

    encrypted_key = base64.b64encode(encrypted_key).decode()

    msg = Message(
        sender=current_user,
        recipient=recipient,
        content=encrypted["ciphertext"],
        iv=encrypted["iv"],
        encrypted_key=encrypted_key,
    )

    db.session.add(msg)
    db.session.commit()

    socketio.emit(
        "new_message",
        {
            "sender": current_user.username,
            "encrypted_message": encrypted["ciphertext"],
            "iv": encrypted["iv"],
            "encrypted_key": encrypted_key,
        },
        room=recipient.username,
    )

    # Sync to sender's other sessions
    socketio.emit(
        "new_message",
        {
            "sender": current_user.username,
            "encrypted_message": encrypted["ciphertext"],
            "iv": encrypted["iv"],
            "encrypted_key": encrypted_key,
        },
        room=current_user.username,
    )

    return jsonify(success=True)


@app.route("/api/decrypt-message", methods=["POST"])
@login_required
def decrypt_message():
    data = request.json

    try:
        private_key = load_private_key(current_user.private_key)
        aes_key = private_key.decrypt(
            base64.b64decode(data["encrypted_key"]),
            padding.OAEP(
                mgf=padding.MGF1(hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )

        plaintext = decrypt_with_aes(
            aes_key, data["iv"], data["encrypted_message"]
        )

        emit_crypto_event("DECRYPT_SUCCESS", {"username": current_user.username})
        return jsonify(success=True, decrypted_message=plaintext.decode())

    except Exception as e:
        emit_crypto_event(
            "DECRYPT_FAILED",
            {"username": current_user.username, "error": str(e)},
        )
        return jsonify(error="Decryption failed"), 500


# -----------------------------------------------------------------------------
# SOCKETS
# -----------------------------------------------------------------------------
@socketio.on("connect")
def on_connect(auth=None):
    if not current_user.is_authenticated:
        return False

    join_room(current_user.username)

    try:
        risk_score = session_manager.register_session(current_user.id, request.sid)
        # Toned down threshold to avoid false alarms vs annoying alerts
        if risk_score < 40:
            emit("security_alert", {
                "level": "CRITICAL",
                "message": "Multiple active sessions detected. Verify your account activity.",
                "score": risk_score
            }, room=current_user.username)
    except Exception as e:
        print(f"[SESSION] register_session failed: {e}")

    emit_crypto_event("SESSION_STARTED", {"username": current_user.username, "via": "socket"})

    # Notify others that user is online
    socketio.emit("user_online", {"username": current_user.username})


@app.route("/api/get-stored-messages/<username>", methods=["GET"])
@login_required
def get_stored_messages(username):
    other_user = User.query.filter_by(username=username).first()
    if not other_user:
        return jsonify(error="User not found"), 404

    # Fetch messages between current_user and other_user
    messages = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.recipient_id == other_user.id)) |
        ((Message.sender_id == other_user.id) & (Message.recipient_id == current_user.id))
    ).order_by(Message.timestamp).all()

    # Format for frontend
    msg_list = []
    for msg in messages:
        msg_list.append({
            "sender": msg.sender.username,
            "recipient": msg.recipient.username,
            "encrypted_message": msg.content,
            "iv": msg.iv,
            "encrypted_key": msg.encrypted_key,
            "timestamp": msg.timestamp
        })

    return jsonify(success=True, messages=msg_list)


# -----------------------------------------------------------------------------
# RUN
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    socketio.run(app, host="127.0.0.1", port=5000, debug=False)
 
