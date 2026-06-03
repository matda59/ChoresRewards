/**
 * auth_profile.js — Adult/child mode management
 *
 * Always starts in child mode (restricted). The padlock button lets any
 * person with is_admin=True enter their personal PIN (or the master PIN)
 * to elevate to adult mode. Tap the padlock again to lock back to child mode.
 */

(function () {
    'use strict';

    // ── State ─────────────────────────────────────────────────────────────────
    let _adultMode = false;
    let _adultName = null;    let _lockoutTimer = null;
    let _pinLocked = false;
    // ── DOM helpers ───────────────────────────────────────────────────────────
    function getEl(id) { return document.getElementById(id); }

    function setAdultMode(isAdult, name) {
        _adultMode = isAdult;
        _adultName = name || null;

        const root = document.documentElement;
        if (isAdult) {
            root.classList.add('adult-mode');
            root.classList.remove('child-mode');
        } else {
            root.classList.add('child-mode');
            root.classList.remove('adult-mode');
        }

        updateLockButton();
    }

    function updateLockButton() {
        const btn = getEl('adult-lock-btn');
        if (!btn) return;
        if (_adultMode) {
            btn.innerHTML = '<i class="fas fa-lock-open"></i><span class="lock-label">' + (_adultName || 'Adult') + '</span>';
            btn.title = 'Tap to lock (switch to child mode)';
            btn.classList.add('unlocked');
            btn.classList.remove('locked');
        } else {
            btn.innerHTML = '<i class="fas fa-lock"></i>';
            btn.title = 'Tap to unlock adult mode';
            btn.classList.remove('unlocked');
            btn.classList.add('locked');
        }
    }

    // ── PIN overlay ───────────────────────────────────────────────────────────
    function showPinOverlay() {
        const overlay = getEl('adult-pin-overlay');
        if (!overlay) return;
        getEl('adult-pin-input').value = '';
        getEl('adult-pin-error').textContent = '';
        overlay.style.display = 'flex';
        setTimeout(function () { getEl('adult-pin-input').focus(); }, 80);
    }

    function hidePinOverlay() {
        const overlay = getEl('adult-pin-overlay');
        if (overlay) overlay.style.display = 'none';
        // Cancel any running lockout countdown when the overlay is dismissed
        if (_lockoutTimer) { clearInterval(_lockoutTimer); _lockoutTimer = null; }
        _pinLocked = false;
        const input = getEl('adult-pin-input');
        if (input) input.disabled = false;
    }

    function startLockoutCountdown(seconds) {
        _pinLocked = true;
        const input = getEl('adult-pin-input');
        const errorEl = getEl('adult-pin-error');
        if (input) { input.disabled = true; input.value = ''; }
        if (_lockoutTimer) clearInterval(_lockoutTimer);
        let remaining = seconds;
        function tick() {
            if (remaining > 0) {
                if (errorEl) errorEl.textContent = '\uD83D\uDD12 Locked out. Try again in ' + remaining + 's.';
                remaining--;
            } else {
                clearInterval(_lockoutTimer);
                _lockoutTimer = null;
                _pinLocked = false;
                if (input) { input.disabled = false; input.focus(); }
                if (errorEl) errorEl.textContent = '';
            }
        }
        tick();
        _lockoutTimer = setInterval(tick, 1000);
    }

    function shakePinBox() {
        const box = getEl('adult-pin-box');
        if (!box) return;
        box.classList.remove('pin-shake');
        void box.offsetWidth; // reflow
        box.classList.add('pin-shake');
    }

    // ── API calls ─────────────────────────────────────────────────────────────
    function checkAuthStatus() {
        fetch('/api/auth_status')
            .then(function (r) { return r.json(); })
            .then(function (data) {
                setAdultMode(data.adult_mode, data.adult_name);
            })
            .catch(function () {
                setAdultMode(false, null);
            });
    }

    function attemptAdultLogin(pin) {
        fetch('/api/adult_login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pin: pin }),
        })
            .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, data: d }; }); })
            .then(function (res) {
                if (res.ok && res.data.success) {
                    hidePinOverlay();
                    setAdultMode(true, res.data.adult_name);
                    if (typeof showToast === 'function') {
                        showToast('Unlocked — adult mode active', 'success');
                    }
                } else {
                    if (res.data.retry_after) {
                        startLockoutCountdown(res.data.retry_after);
                    } else {
                        getEl('adult-pin-error').textContent = res.data.error || 'Incorrect PIN';
                        shakePinBox();
                        getEl('adult-pin-input').value = '';
                        getEl('adult-pin-input').focus();
                    }
                }
            })
            .catch(function () {
                getEl('adult-pin-error').textContent = 'Network error, please try again.';
                shakePinBox();
            });
    }

    function doAdultLogout() {
        fetch('/api/adult_logout', { method: 'POST' })
            .then(function () {
                setAdultMode(false, null);
                if (typeof showToast === 'function') {
                    showToast('Locked — child mode active', 'info');
                }
            })
            .catch(function () {
                setAdultMode(false, null);
            });
    }

    // ── Exported helpers for other scripts ───────────────────────────────────
    window.isAdultMode = function () { return _adultMode; };
    window.checkAuthStatus = checkAuthStatus;

    // ── Initialise on DOM ready ───────────────────────────────────────────────
    document.addEventListener('DOMContentLoaded', function () {
        checkAuthStatus();

        // Padlock button
        const lockBtn = getEl('adult-lock-btn');
        if (lockBtn) {
            lockBtn.addEventListener('click', function () {
                if (_adultMode) {
                    doAdultLogout();
                } else {
                    showPinOverlay();
                }
            });
        }

        // PIN overlay: digit input auto-submit at 4 chars
        const pinInput = getEl('adult-pin-input');
        if (pinInput) {
            pinInput.addEventListener('input', function () {
                if (_pinLocked) return;
                const val = pinInput.value.replace(/\D/g, '').slice(0, 4);
                pinInput.value = val;
                if (val.length === 4) {
                    attemptAdultLogin(val);
                }
            });
        }

        // PIN overlay: Enter key
        const pinForm = getEl('adult-pin-form');
        if (pinForm) {
            pinForm.addEventListener('submit', function (e) {
                e.preventDefault();
                if (_pinLocked) return;
                const val = (getEl('adult-pin-input').value || '').replace(/\D/g, '').slice(0, 4);
                if (val.length === 4) {
                    attemptAdultLogin(val);
                }
            });
        }

        // Close overlay on backdrop click
        const overlay = getEl('adult-pin-overlay');
        if (overlay) {
            overlay.addEventListener('click', function (e) {
                if (e.target === overlay) hidePinOverlay();
            });
        }

        // Close on Escape
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') hidePinOverlay();
        });
    });
})();
