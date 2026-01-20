# SecureChat

SecureChat is a secure, real-time messaging application built with Flask and Socket.IO. It features end-to-end encryption to ensure that your conversations remain private and secure.

##  Key Features & Improvements

We have transformed this application from a basic prototype into a robust, modern chat platform:

### 1. End-to-End Encryption 
*   **RSA-2048**: Automatically generates a public/private key pair for each user upon registration. Public keys are stored on the server, while private keys are encrypted and stored securely.
*   **AES-256**: Each message is encrypted with a unique, random AES key. This key is then encrypted with the recipient's RSA public key.
*   **Zero-Knowledge**: The server only relays encrypted data. It never sees the plaintext messages.

### 2. Real-Time Messaging ⚡
*   **WebSockets**: Replaced the old polling mechanism with **Flask-SocketIO**.
*   **Instant Delivery**: Messages appear instantly on the recipient's screen without needing to refresh the page.
*   **Live Notifications**: Get notified immediately when a new message arrives.

### 3. Modern UI/UX 
*   **Glassmorphism Design**: A premium, dark-themed interface with translucent elements and blur effects.
*   **Responsive Layout**: A seamless experience on both desktop and mobile devices.
*   **Smooth Animations**: Polished transitions for login, message sending, and notifications.

### 4. Robust Foundation 
*   **Database**: Migrated from file-based storage to **SQLite** for reliable data management.
*   **Authentication**: Secure user registration and login using **Flask-Login** and **Flask-Bcrypt**.

##  Tech Stack

*   **Backend**: Python, Flask, Flask-SocketIO, Flask-SQLAlchemy
*   **Security**: Cryptography (RSA, AES), Flask-Bcrypt
*   **Frontend**: HTML5, CSS3 (Variables, Flexbox/Grid), JavaScript (ES6+), Socket.IO Client

##  How to Run

### 1. Install Dependencies
Make sure you have Python installed. Then, install the required packages:

```bash
pip install -r requirements.txt
```

### 2. Start the Server
Run the Flask application:

```bash
python app.py
```

The app will start running at `http://127.0.0.1:5000`.

### 3. Testing with Multiple Users (IMPORTANT) ⚠️

To test the chat functionality between two users on the same computer, you **must** use a separate browser session for the second user.

1.  **User A**: Open your browser (e.g., Chrome) and go to `http://127.0.0.1:5000`. Register/Login as **User A**.
2.  **User B**: Open a **New Incognito Window** (or Private Window) and go to `http://127.0.0.1:5000`. Register/Login as **User B**.

**Why?** If you use the same browser window (even in a new tab), the session cookies will conflict, and you will be logged out of the first user. Incognito mode creates a fresh, isolated session.

##  Usage Guide

1.  **Register**: Create an account. The app will generate your encryption keys (this may take a few seconds).
2.  **Select Contact**: Choose a user from the sidebar to start chatting.
3.  **Chat**: Type and send messages. Watch them appear instantly!
4.  **Verify Security**: Click the "Lock" icon in the chat header to see the encryption details.
 

