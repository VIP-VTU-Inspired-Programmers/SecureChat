// DOM Elements
const authContainer = document.getElementById('auth-container');
const appContainer = document.getElementById('app-container');
const loginBox = document.getElementById('login-box');
const registerBox = document.getElementById('register-box');
const loginForm = document.getElementById('login-form');
const registerForm = document.getElementById('register-form');
const showRegisterBtn = document.getElementById('show-register');
const showLoginBtn = document.getElementById('show-login');
const contactsList = document.getElementById('contacts-list');
const refreshContactsBtn = document.getElementById('refresh-contacts-btn');
const searchContactsInput = document.getElementById('search-contacts');
const dashboardView = document.getElementById('dashboard-view');
const chatScreen = document.getElementById('chat-screen');
const currentContactElement = document.getElementById('current-contact');
const messagesContainer = document.getElementById('messages-container');
const messageInput = document.getElementById('message-input');
const sendMessageBtn = document.getElementById('send-message-btn');
const notificationContainer = document.getElementById('notification-container');
const encryptionModal = document.getElementById('encryption-modal');
const closeModalBtn = document.getElementById('close-modal-btn');
const backToContactsBtn = document.getElementById('back-to-contacts');
const headerAvatar = document.getElementById('header-avatar');

// SocketIO
const socket = io();

// App State
const state = {
    currentUser: null,
    currentContact: null,
    contacts: [],
    messages: {},
    isAuthenticated: false,
    // [PLACEHOLDER] Security State for Trust Layer
    securityState: {
        trustScore: 100,
        verificationStatus: 'unverified',
        localSession: false
    },
    onlineUsers: new Set()
};

// [PLACEHOLDER] Trust Event Handler
// This function is reserved for future trust verification logic.
function handleTrustEvent(event) {
    console.log('[TRUST EVENT]', event);
    // Future: Update UI based on trust score
}

// Socket Events
socket.on('connect', () => {
    console.log('Connected to WebSocket server');
});

socket.on('new_message', (data) => {
    console.log('New message received:', data);
    processEncryptedMessage(data);

    if (state.currentContact !== data.sender) {
        showNotification(`New message from ${data.sender}`, 'success');
    }
});

socket.on('security_alert', (data) => {
    console.warn('[SECURITY ALERT]', data);
    showNotification(`Security Alert: ${data.message}`, 'error');

    // Pass to Trust Layer if available
    if (window.handleTrustEvent) {
        window.handleTrustEvent({
            type: 'SECURITY_ALERT',
            payload: data
        });
    }

    // Refresh dashboard to show new status
    fetchDashboardData();
});

socket.on('user_online', (data) => {
    console.log('User online:', data.username);
    state.onlineUsers.add(data.username);
    renderContacts();
    showNotification(`${data.username} is now online`, 'success');
});

// Event Listeners
document.addEventListener('DOMContentLoaded', () => {
    checkAuth();
});

// Auth Toggles
showRegisterBtn.addEventListener('click', () => {
    loginBox.classList.add('hidden');
    registerBox.classList.remove('hidden');
});

showLoginBtn.addEventListener('click', () => {
    registerBox.classList.add('hidden');
    loginBox.classList.remove('hidden');
});

// Auth Forms
loginForm.addEventListener('submit', handleLogin);
registerForm.addEventListener('submit', handleRegister);

// App Events
refreshContactsBtn.addEventListener('click', loadContacts);
searchContactsInput.addEventListener('input', filterContacts);
sendMessageBtn.addEventListener('click', sendMessage);
messageInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});
closeModalBtn.addEventListener('click', () => {
    encryptionModal.classList.add('hidden');
});

if (backToContactsBtn) {
    backToContactsBtn.addEventListener('click', () => {
        document.getElementById('chat-screen').classList.remove('active');
        state.currentContact = null;
        // On mobile, this reveals the sidebar/dashboard underneath.
        // On desktop, we might want to show dashboard again:
        if (window.innerWidth > 768) {
            const dashboardView = document.getElementById('dashboard-view');
            const chatScreen = document.getElementById('chat-screen');
            chatScreen.classList.add('hidden');
            dashboardView.classList.remove('hidden');
        }
    });
}

// Functions

async function checkAuth() {
    try {
        const response = await fetch('/api/check-auth');
        const data = await response.json();

        if (data.authenticated) {
            state.currentUser = data.username;
            state.isAuthenticated = true;
            updateUserUI(state.currentUser);
            showApp();
        } else {
            showAuth();
        }
    } catch (error) {
        console.error('Auth check failed:', error);
        showAuth();
    }
}

function showAuth() {
    authContainer.classList.remove('hidden');
    appContainer.classList.add('hidden');
}

function showApp() {
    authContainer.classList.add('hidden');
    appContainer.classList.remove('hidden');
    loadContacts();
    fetchDashboardData();
    renderEmptyState();

    // Add logout button to sidebar if not exists
    if (!document.getElementById('logout-btn')) {
        const userSection = document.querySelector('.user-section');
        userSection.innerHTML = `
            <div class="user-info">
                <span class="user-name">${state.currentUser}</span>
                <!-- [PLACEHOLDER] Local Session Indicator -->
                <span id="local-session-indicator" class="session-indicator hidden" style="display:none">
                    <i class="fas fa-wifi"></i>
                </span>
                <button id="logout-btn" class="logout-btn">Logout</button>
            </div>
            <div id="key-status" class="key-status">
                <i class="fas fa-key"></i>
                <span>Keys active</span>
            </div>
        `;
        document.getElementById('logout-btn').addEventListener('click', handleLogout);
    }
}

async function handleLogin(e) {
    e.preventDefault();
    const username = document.getElementById('login-username').value;
    const password = document.getElementById('login-password').value;

    try {
        const response = await fetch('/api/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });

        const data = await response.json();

        if (data.success) {
            state.isAuthenticated = true;
            updateUserUI(username);

            // Force socket reconnection to ensure we join the correct room
            if (socket.connected) {
                socket.disconnect();
            }
            socket.connect();

            showApp();
            showNotification('Login successful', 'success');
        } else {
            showNotification(data.error, 'error');
        }
    } catch (error) {
        showNotification('Login failed', 'error');
    }
}

async function handleRegister(e) {
    e.preventDefault();
    const username = document.getElementById('register-username').value;
    const password = document.getElementById('register-password').value;

    try {
        showNotification('Registering and generating keys...', 'success');
        const response = await fetch('/api/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });

        const data = await response.json();

        if (data.success) {
            state.isAuthenticated = true;
            updateUserUI(username);

            // Force socket reconnection
            if (socket.connected) {
                socket.disconnect();
            }
            socket.connect();

            showApp();
            showNotification('Registration successful', 'success');
        } else {
            showNotification(data.error, 'error');
        }
    } catch (error) {
        showNotification('Registration failed', 'error');
    }
}

async function handleLogout() {
    try {
        await fetch('/api/logout', { method: 'POST' });
        state.currentUser = null;
        state.isAuthenticated = false;
        state.currentContact = null;
        state.messages = {};

        // Disconnect socket
        if (socket.connected) {
            socket.disconnect();
        }

        showAuth();
    } catch (error) {
        console.error('Logout failed:', error);
    }
}

async function loadContacts() {
    try {
        const response = await fetch('/api/users');
        if (response.status === 401) {
            handleLogout();
            return;
        }
        const data = await response.json();

        if (data.success) {
            state.contacts = data.users.filter(user => user !== state.currentUser);
            renderContacts();
        }
    } catch (error) {
        showNotification(`Error loading contacts: ${error.message}`, 'error');
    }
}

function renderContacts() {
    contactsList.innerHTML = '';

    state.contacts.forEach(contact => {
        const contactElement = document.createElement('li');
        contactElement.className = 'contact-item';
        contactElement.dataset.username = contact;

        if (state.currentContact === contact) {
            contactElement.classList.add('active');
        }

        contactElement.innerHTML = `
            <div class="contact-avatar">${contact.charAt(0).toUpperCase()}</div>
            <div class="contact-info-group" style="display:flex; flex-direction:column;">
                <span class="contact-name">${contact}</span>
                <span class="contact-status ${state.onlineUsers.has(contact) ? 'online' : 'offline'}" style="font-size:0.7rem; color:var(--text-muted)">
                    ${state.onlineUsers.has(contact) ? 'Online' : 'Offline'}
                </span>
            </div>
            ${state.onlineUsers.has(contact) ? '<span class="status-dot"></span>' : ''}
        `;

        contactElement.addEventListener('click', () => {
            selectContact(contact);
        });

        contactsList.appendChild(contactElement);
    });
}

function filterContacts() {
    const searchTerm = searchContactsInput.value.toLowerCase();
    const contactItems = contactsList.querySelectorAll('.contact-item');

    contactItems.forEach(item => {
        const contactName = item.textContent.toLowerCase();
        if (contactName.includes(searchTerm)) {
            item.style.display = 'flex';
        } else {
            item.style.display = 'none';
        }
    });
}

function updateUserUI(username) {
    state.currentUser = username;
    // Update dashboard and headers
    document.querySelectorAll('.current-username-display').forEach(el => el.textContent = username);
    // Update sidebar user info
    const sidebarName = document.querySelector('.user-info .user-name');
    if (sidebarName) sidebarName.textContent = username;
}

function selectContact(contact) {
    state.currentContact = contact;
    currentContactElement.textContent = contact;

    // Update avatar
    if (headerAvatar) {
        headerAvatar.textContent = contact.charAt(0).toUpperCase();
    }

    // Update active state in list
    document.querySelectorAll('.contact-item').forEach(item => {
        item.classList.remove('active');
        if (item.dataset.username === contact) {
            item.classList.add('active');
        }
    });

    // Switch to chat screen
    if (dashboardView) dashboardView.classList.add('hidden');
    chatScreen.classList.remove('hidden');

    // For mobile: show chat area
    chatScreen.classList.add('active');

    // Clear messages container
    messagesContainer.innerHTML = '';

    // Load messages for this contact (if any)
    if (state.messages[contact]) {
        renderMessages();
    }

    // Fetch stored messages for this contact
    fetchStoredMessages();
}

async function sendMessage() {
    const messageText = messageInput.value.trim();

    if (!messageText) return;
    if (!state.currentContact) return;

    try {
        // Optimistic UI update
        const tempMessage = {
            sender: state.currentUser,
            recipient: state.currentContact,
            content: messageText,
            timestamp: new Date().toISOString(),
            pending: true
        };
        addMessageToState(tempMessage);
        renderMessages();
        messageInput.value = '';

        const response = await fetch('/api/encrypt-message', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                recipient: state.currentContact,
                message: messageText
            })
        });

        if (response.status === 401) {
            handleLogout();
            return;
        }

        const data = await response.json();

        if (data.success) {
            updateLastMessageStatus();
            renderMessages();
        } else {
            showNotification(`Error: ${data.error}`, 'error');
        }
    } catch (error) {
        showNotification(`Error: ${error.message}`, 'error');
    }
}

function addMessageToState(message) {
    const recipient = message.recipient;
    const sender = message.sender;

    // Determine who the "other" person is in this conversation
    const otherUser = sender === state.currentUser ? recipient : sender;

    if (!state.messages[otherUser]) {
        state.messages[otherUser] = [];
    }

    // Check for duplicates
    const exists = state.messages[otherUser].some(m =>
        m.timestamp === message.timestamp && m.content === message.content
    );

    if (!exists) {
        state.messages[otherUser].push(message);
        // Sort by timestamp
        state.messages[otherUser].sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
    }
}

function updateLastMessageStatus() {
    if (!state.currentContact || !state.messages[state.currentContact]) return;

    const messages = state.messages[state.currentContact];
    // Find the last pending message and mark it as sent
    for (let i = messages.length - 1; i >= 0; i--) {
        if (messages[i].pending) {
            messages[i].pending = false;
            break;
        }
    }
}

async function fetchStoredMessages() {
    if (!state.currentUser || !state.currentContact) return;

    try {
        const response = await fetch(`/api/get-stored-messages/${state.currentContact}`);
        if (response.status === 401) return;

        const data = await response.json();

        if (data.success) {
            // Process all messages
            for (const msg of data.messages) {
                await processEncryptedMessage(msg);
            }

            if (state.currentContact) {
                renderMessages();
            }
        }
    } catch (error) {
        console.error('Error fetching stored messages:', error);
    }
}

async function processEncryptedMessage(msg) {
    // Check if we already have this message decrypted
    const otherUser = msg.sender === state.currentUser ? msg.recipient : msg.sender;

    if (!state.messages[otherUser]) {
        state.messages[otherUser] = [];
    }

    const exists = state.messages[otherUser].some(m => m.timestamp === msg.timestamp);
    if (exists) return;

    try {
        // Decrypt
        const response = await fetch('/api/decrypt-message', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                encrypted_message: msg.encrypted_message,
                iv: msg.iv,
                encrypted_key: msg.encrypted_key
            })
        });

        const data = await response.json();

        if (data.success) {
            addMessageToState({
                sender: msg.sender,
                recipient: msg.recipient,
                content: data.decrypted_message,
                timestamp: msg.timestamp
            });

            if (state.currentContact === otherUser) {
                renderMessages();
            }
        }
    } catch (error) {
        console.error('Decryption failed:', error);
        // [PLACEHOLDER] Future: Report decryption failure to trust layer
        handleTrustEvent({ type: 'DECRYPTION_FAILURE', error: error.message });
    }
}

function renderMessages() {
    if (!state.currentContact || !state.messages[state.currentContact]) {
        messagesContainer.innerHTML = '';
        return;
    }

    messagesContainer.innerHTML = '';
    const messages = state.messages[state.currentContact];

    messages.forEach(message => {
        const messageElement = document.createElement('div');
        messageElement.className = `message ${message.sender === state.currentUser ? 'sent' : 'received'}`;

        let messageContent = message.content;
        if (message.pending) {
            messageContent += ' <i class="fas fa-clock" style="font-size: 0.8rem; margin-left: 5px;"></i>';
        }

        messageElement.innerHTML = `
            <div class="message-content">${messageContent}</div>
            <div class="message-time">${formatTime(message.timestamp)}</div>
        `;

        messagesContainer.appendChild(messageElement);
    });

    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function formatTime(timestamp) {
    // Handle both unix timestamp (seconds) and ISO string
    let date;
    if (typeof timestamp === 'number') {
        date = new Date(timestamp * 1000);
    } else {
        date = new Date(timestamp);
    }
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function showNotification(message, type) {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    const icon = type === 'success' ? 'check-circle' : 'exclamation-circle';

    notification.innerHTML = `
        <i class="fas fa-${icon}"></i>
        <span>${message}</span>
    `;

    notificationContainer.appendChild(notification);
    setTimeout(() => {
        notification.style.opacity = '0';
        setTimeout(() => notification.remove(), 300);
    }, 5000);
}

async function fetchDashboardData() {
    if (!state.isAuthenticated) return;

    try {
        const response = await fetch('/api/dashboard');
        if (!response.ok) throw new Error('Failed to fetch dashboard stats');

        const data = await response.json();
        console.log('[DASHBOARD] Stats:', data);

        // Update Active Sockets
        const countEl = document.getElementById('active-session-count');
        if (countEl) {
            countEl.textContent = data.active_sockets || 1;
        }

        // Update Events Summary
        const eventsEl = document.getElementById('security-events-summary');
        if (eventsEl) {
            const count = data.event_count || 0;
            eventsEl.textContent = `${count} Security Event${count !== 1 ? 's' : ''} Logged`;
        }

    } catch (error) {
        console.warn('[DASHBOARD] Could not load stats:', error);
    }
}

function renderEmptyState() {
    state.currentContact = null;
    if (dashboardView) dashboardView.classList.remove('hidden');
    if (chatScreen) chatScreen.classList.add('hidden');

    // Clear active state from contacts
    document.querySelectorAll('.contact-item').forEach(item => {
        item.classList.remove('active');
    });
}
