import eventlet
eventlet.monkey_patch()

from flask import Flask, request, jsonify, render_template, send_from_directory, redirect, url_for
from flask_cors import CORS
import os
import json
import base64
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import secrets
import time
from extensions import db, login_manager, bcrypt, socketio
from models import User, Message
from flask_login import login_user, current_user, logout_user, login_required
from flask_socketio import emit, join_room

app = Flask(__name__, static_folder='static')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-for-now-change-this-in-env')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///chat.db')
if app.config['SQLALCHEMY_DATABASE_URI'].startswith("postgres://"):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

CORS(app)

# Initialize extensions
db.init_app(app)
login_manager.init_app(app)
bcrypt.init_app(app)
socketio.init_app(app, cors_allowed_origins="*")
login_manager.login_view = 'index'

with app.app_context():
    # Ensure instance directory (for sqlite) exists if using local sqlite
    if 'sqlite' in app.config['SQLALCHEMY_DATABASE_URI']:
        os.makedirs(app.instance_path, exist_ok=True)
    db.create_all()

# Helper functions (kept for encryption logic, but updated where needed)


def generate_rsa_key_pair():
    """Generate RSA key pair"""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )
    
    public_key = private_key.public_key()
    
    # Serialize private key
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    # Serialize public key
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    
    return {
        'private_key': private_pem.decode('utf-8'),
        'public_key': public_pem.decode('utf-8')
    }

def load_public_key_from_string(pem_string):
    """Load public key from string"""
    return serialization.load_pem_public_key(
        pem_string.encode('utf-8'),
        backend=default_backend()
    )

def load_private_key_from_string(pem_string):
    """Load private key from string"""
    return serialization.load_pem_private_key(
        pem_string.encode('utf-8'),
        password=None,
        backend=default_backend()
    )

def encrypt_with_rsa(public_key, data):
    """Encrypt data with RSA public key"""
    if isinstance(data, str):
        data = data.encode('utf-8')
    
    ciphertext = public_key.encrypt(
        data,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    
    return base64.b64encode(ciphertext).decode('utf-8')

def decrypt_with_rsa(private_key, encrypted_data):
    """Decrypt data with RSA private key"""
    if isinstance(encrypted_data, str):
        encrypted_data = base64.b64decode(encrypted_data)
    
    plaintext = private_key.decrypt(
        encrypted_data,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    
    return plaintext

def generate_aes_key():
    """Generate a random AES key"""
    return secrets.token_bytes(32)  # 256-bit key

def encrypt_with_aes(key, plaintext):
    """Encrypt data with AES"""
    if isinstance(plaintext, str):
        plaintext = plaintext.encode('utf-8')
    
    iv = secrets.token_bytes(16)  # 128-bit IV
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    
    # PKCS7 padding
    padder = lambda s: s + (16 - len(s) % 16) * bytes([16 - len(s) % 16])
    padded_data = padder(plaintext)
    
    ciphertext = encryptor.update(padded_data) + encryptor.finalize()
    
    # Return IV and ciphertext
    return {
        'iv': base64.b64encode(iv).decode('utf-8'),
        'ciphertext': base64.b64encode(ciphertext).decode('utf-8')
    }

def decrypt_with_aes(key, iv, ciphertext):
    """Decrypt data with AES"""
    if isinstance(iv, str):
        iv = base64.b64decode(iv)
    
    if isinstance(ciphertext, str):
        ciphertext = base64.b64decode(ciphertext)
    
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    
    padded_plaintext = decryptor.update(ciphertext) + decryptor.finalize()
    
    # PKCS7 unpadding
    unpadder = lambda s: s[:-s[-1]]
    plaintext = unpadder(padded_plaintext)
    
    return plaintext

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/static/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)

# Auth Routes
@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400
        
    if User.query.filter_by(username=username).first():
        return jsonify({'error': 'Username already exists'}), 400
        
    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
    
    # Generate keys automatically on registration
    keys = generate_rsa_key_pair()
    
    user = User(
        username=username, 
        password_hash=hashed_password,
        public_key=keys['public_key'],
        private_key=keys['private_key']
    )
    
    db.session.add(user)
    db.session.commit()
    
    login_user(user)
    
    return jsonify({
        'success': True, 
        'message': 'Registration successful',
        'username': username
    })

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    user = User.query.filter_by(username=username).first()
    
    if user and bcrypt.check_password_hash(user.password_hash, password):
        login_user(user)
        return jsonify({
            'success': True, 
            'message': 'Login successful',
            'username': username
        })
    else:
        return jsonify({'error': 'Invalid username or password'}), 401

@app.route('/api/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return jsonify({'success': True, 'message': 'Logged out successfully'})

@app.route('/api/check-auth', methods=['GET'])
def check_auth():
    if current_user.is_authenticated:
        return jsonify({'authenticated': True, 'username': current_user.username})
    else:
        return jsonify({'authenticated': False})

# API Routes
@app.route('/api/get-public-key/<username>', methods=['GET'])
@login_required
def api_get_public_key(username):
    user = User.query.filter_by(username=username).first()
    
    if not user or not user.public_key:
        return jsonify({'error': 'Public key not found'}), 404
    
    return jsonify({
        'success': True,
        'public_key': user.public_key
    })

@app.route('/api/encrypt-message', methods=['POST'])
@login_required
def api_encrypt_message():
    data = request.json
    recipient_username = data.get('recipient')
    message_content = data.get('message')
    
    if not recipient_username or not message_content:
        return jsonify({'error': 'Recipient and message are required'}), 400
    
    try:
        recipient = User.query.filter_by(username=recipient_username).first()
        if not recipient:
            return jsonify({'error': 'Recipient not found'}), 404
            
        # Load recipient's public key
        recipient_public_key = load_public_key_from_string(recipient.public_key)
        
        # Generate AES key for this message
        aes_key = generate_aes_key()
        
        # Encrypt message with AES
        encrypted_message = encrypt_with_aes(aes_key, message_content)
        
        # Encrypt AES key with recipient's public key
        encrypted_aes_key = encrypt_with_rsa(recipient_public_key, aes_key)
        
        # Save message to DB
        msg = Message(
            sender=current_user,
            recipient=recipient,
            content=encrypted_message['ciphertext'],
            iv=encrypted_message['iv'],
            encrypted_key=encrypted_aes_key
        )
        
        db.session.add(msg)
        db.session.commit()

        # Emit real-time event to recipient
        socketio.emit('new_message', {
            'sender': current_user.username,
            'recipient': recipient.username,
            'encrypted_message': encrypted_message['ciphertext'],
            'iv': encrypted_message['iv'],
            'encrypted_key': encrypted_aes_key,
            'timestamp': msg.timestamp
        }, room=recipient.username)

        return jsonify({
            'success': True,
            'encrypted_message': encrypted_message['ciphertext'],
            'iv': encrypted_message['iv'],
            'encrypted_key': encrypted_aes_key
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/decrypt-message', methods=['POST'])
@login_required
def api_decrypt_message():
    data = request.json
    # In the new design, we don't need to pass username, we use current_user
    # But for backward compatibility with frontend logic (which sends username), we can ignore it or verify it
    
    encrypted_message = data.get('encrypted_message')
    iv = data.get('iv')
    encrypted_key = data.get('encrypted_key')
    
    if not all([encrypted_message, iv, encrypted_key]):
        return jsonify({'error': 'Encrypted message, IV, and encrypted key are required'}), 400
    
    try:
        # Load user's private key
        print(f"Decrypting for user: {current_user.username}")
        private_key = load_private_key_from_string(current_user.private_key)
        
        # Decrypt AES key
        print(f"Decrypting AES key: {encrypted_key[:20]}...")
        aes_key = decrypt_with_rsa(private_key, encrypted_key)
        
        # Decrypt message
        print(f"Decrypting message IV: {iv}, Content: {encrypted_message[:20]}...")
        decrypted_message = decrypt_with_aes(aes_key, iv, encrypted_message)
        
        return jsonify({
            'success': True,
            'decrypted_message': decrypted_message.decode('utf-8')
        })
    except Exception as e:
        import traceback
        print("Decryption Error:")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/api/get-stored-messages/<username>', methods=['GET'])
@login_required
def api_get_stored_messages(username):
    # This endpoint was used to get messages *for* a user.
    # Now we should return messages where current_user is the recipient OR sender
    
    # If username is passed, maybe it means "messages with this user"?
    # The original logic was: get all messages where recipient is <username>
    # But the frontend calls it with current user's username.
    
    if username != current_user.username:
        return jsonify({'error': 'Unauthorized'}), 403
        
    messages = Message.query.filter(
        (Message.recipient_id == current_user.id) | (Message.sender_id == current_user.id)
    ).order_by(Message.timestamp).all()
    
    messages_data = []
    for msg in messages:
        messages_data.append({
            'sender': msg.sender.username,
            'recipient': msg.recipient.username,
            'encrypted_message': msg.content,
            'iv': msg.iv,
            'encrypted_key': msg.encrypted_key,
            'timestamp': msg.timestamp
        })

    return jsonify({
        'success': True,
        'messages': messages_data
    })

@app.route('/api/users', methods=['GET'])
@login_required
def api_get_users():
    users = User.query.all()
    user_list = [u.username for u in users]
    
    return jsonify({
        'success': True,
        'users': user_list
    })

# SocketIO Events
@socketio.on('connect')
def handle_connect():
    if current_user.is_authenticated:
        join_room(current_user.username)
        print(f"User {current_user.username} connected")

@socketio.on('send_message')
def handle_send_message(data):
    # This event can be used if we switch to full WebSocket messaging
    # For now, we are using the REST API for sending to handle encryption logic easily
    # But we can emit an event here to notify the recipient
    pass

@socketio.on('notify_recipient')
def handle_notify_recipient(data):
    # This event is called by the client after sending a message via API
    # Or we can trigger it from the API route directly (better)
    pass

# We will trigger the notification from the API route instead of a separate event
# See api_encrypt_message modification below

if __name__ == '__main__':
    socketio.run(app, debug=True, host='127.0.0.1', port=5000)
