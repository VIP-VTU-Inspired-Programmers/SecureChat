from extensions import db, login_manager
from flask_login import UserMixin
from datetime import datetime

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password_hash = db.Column(db.String(60), nullable=False)
    public_key = db.Column(db.Text, nullable=True)
    private_key = db.Column(db.Text, nullable=True) # Encrypted with user's password (conceptually, or just stored for now)
    
    # Relationships
    sent_messages = db.relationship('Message', foreign_keys='Message.sender_id', backref='sender', lazy=True)
    received_messages = db.relationship('Message', foreign_keys='Message.recipient_id', backref='recipient', lazy=True)

    def __repr__(self):
        return f"User('{self.username}')"

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False) # Encrypted content
    iv = db.Column(db.String(50), nullable=False)
    encrypted_key = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.Float, nullable=False, default=datetime.utcnow().timestamp)
    is_read = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f"Message('{self.sender_id}', '{self.recipient_id}', '{self.timestamp}')"
