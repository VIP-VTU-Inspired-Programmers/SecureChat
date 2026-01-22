/**
 * SecureChat Trust & Safety Layer
 * -----------------------------------------------------------------------------
 * This module is designed to sit on top of the existing app.js logic.
 * It remains dormant unless explicitly loaded via <script> tag.
 */

const SecurityState = {
    SECURE: 'secure',
    CAUTION: 'caution',
    WARNING: 'warning',
    CRITICAL: 'critical'
};

class SecurityStateManager {
    constructor() {
        this.currentState = SecurityState.SECURE;
        this.trustScore = 100;

        // Element caching (lazy loaded)
        this.banner = document.getElementById('security-alert-banner');
        this.badge = document.getElementById('security-badge-container');
        this.dashboardBadge = document.getElementById('security-badge-dashboard');
        this.statusText = document.getElementById('security-status-text');
    }

    setState(newState, details = null) {
        if (this.currentState === newState) return;

        console.log(`[SecurityStateManager] Transition: ${this.currentState} -> ${newState}`);
        this.currentState = newState;
        this.updateUI(details);
    }

    updateUI(details) {
        // Re-query elements in case DOM re-rendered
        this.banner = document.getElementById('security-alert-banner');
        this.badge = document.getElementById('security-badge-container');
        this.dashboardBadge = document.getElementById('security-badge-dashboard');
        this.statusText = document.getElementById('security-status-text');

        // Reset
        if (this.banner) {
            this.banner.className = 'security-banner hidden';
            this.banner.innerHTML = '';
        }

        switch (this.currentState) {
            case SecurityState.SECURE:
                this._updateBadges('<i class="fas fa-check-circle"></i> SECURE', 'secure');
                if (this.statusText) this.statusText.innerText = "System Encrypted & Verified";
                break;

            case SecurityState.WARNING:
                this._updateBadges('<i class="fas fa-exclamation-triangle"></i> WARNING', 'warning');
                if (this.banner) {
                    this.banner.classList.remove('hidden');
                    this.banner.classList.add('warning');
                    this.banner.innerHTML = `<i class="fas fa-exclamation-triangle"></i> ${details || 'Potential risk detected.'}`;
                }
                if (this.statusText) this.statusText.innerText = details || "Potential risk detected";
                break;

            case SecurityState.CRITICAL:
                this._updateBadges('<i class="fas fa-times-circle"></i> CRITICAL', 'critical');
                if (this.banner) {
                    this.banner.classList.remove('hidden');
                    this.banner.classList.add('critical');
                    this.banner.innerHTML = `<i class="fas fa-skull-crossbones"></i> ${details || 'Integrity COMPROMISED.'}`;
                }
                if (this.statusText) this.statusText.innerText = "Encryption Compromised";
                break;
        }
    }

    _updateBadges(html, className) {
        [this.badge, this.dashboardBadge].forEach(el => {
            if (el) {
                el.innerHTML = html;
                el.className = `security-badge ${className}`;
                el.classList.remove('hidden');
            }
        });
    }
}

class TrustRuleEngine {
    constructor(stateManager) {
        this.state = stateManager;
    }

    evaluateEvent(event) {
        console.log('[TrustRuleEngine] Evaluating:', event);

        if (!event || !event.type) return;

        switch (event.type) {
            case 'DECRYPTION_FAILURE':
                this.handleDecryptionFailure(event);
                break;
            case 'KEY_CHANGED':
                this.handleKeyChange(event);
                break;
            case 'SECURITY_ALERT':
                this.handleSecurityAlert(event);
                break;
            case 'SESSION_RESET':
                this.state.setState(SecurityState.SECURE);
                break;
        }
    }

    handleDecryptionFailure(event) {
        // Simple rule: one failure = caution, multiple = warning?
        // For now, immediate warning.
        this.state.setState(SecurityState.WARNING, "Message decryption failed. Sender identity may be unverifiable.");
    }

    handleKeyChange(event) {
        this.state.setState(SecurityState.CAUTION, "Remote user's keys have changed.");
    }

    handleSecurityAlert(event) {
        const payload = event.payload;
        // payload: { level: 'WARNING' | 'CRITICAL', message: ..., score: ... }
        if (payload.level === 'CRITICAL') {
            this.state.setState(SecurityState.CRITICAL, payload.message);
        } else {
            this.state.setState(SecurityState.WARNING, payload.message);
        }
    }
}

// -----------------------------------------------------------------------------
// AUTO-WIRING (Active only if this script is loaded)
// -----------------------------------------------------------------------------
const securityStateManager = new SecurityStateManager();
const trustRuleEngine = new TrustRuleEngine(securityStateManager);

// Overwrite the placeholder hook in app.js
if (typeof handleTrustEvent !== 'undefined') {
    console.log('[TrustLayer] Hooking into core application...');
    window.handleTrustEvent = function (event) {
        trustRuleEngine.evaluateEvent(event);
    };

    // Initial UI sync
    securityStateManager.updateUI();
}
