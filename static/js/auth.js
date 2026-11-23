/**
 * auth.js — Initial session login (master PIN flow)
 *
 * On every page load:
 *  1. Check /api/check_auth — if the Flask session already has authenticated=True, show content.
 *  2. Otherwise show the master PIN overlay.
 *
 * The padlock button (adult/child mode) is handled separately by auth_profile.js.
 */
(function () {
    'use strict';
    var lockoutTimer = null;
    var pinLocked = false;
    var autoSubmitTimer = null;
    var PIN_MAX = 64;

    // -- DOM helpers --
    function show(id) {
        var el = document.getElementById(id);
        if (el) el.style.display = '';
    }
    function hide(id) {
        var el = document.getElementById(id);
        if (el) el.style.display = 'none';
    }
    function showFlex(id) {
        var el = document.getElementById(id);
        if (el) el.style.display = 'flex';
    }

    // -- Show / hide the login overlay --
    function showLoginOverlay() {
        showFlex('pin-overlay');
        hide('site-content');
        setTimeout(function () {
            var inp = document.getElementById('master-pin-input');
            if (inp) inp.focus();
        }, 80);
    }

    function hideLoginOverlay() {
        hide('pin-overlay');
        show('site-content');
    }

    // -- Submit master PIN login --
    function submitMasterLogin(pin) {
        if (pinLocked) return;
        fetch('/api/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pin: pin }),
        })
            .then(function (r) {
                return r.json().then(function (d) { return { ok: r.ok, data: d }; });
            })
            .then(function (res) {
                if (res.ok && res.data.success) {
                    clearMasterPinLockout();
                    // The logged-out response is only the PIN shell. Reload so the
                    // real page, which is rendered after the session exists, loads.
                    if (document.body && document.body.getAttribute('data-login-shell') === '1') {
                        window.location.reload();
                        return;
                    }
                    hideLoginOverlay();
                    if (typeof window.checkAuthStatus === 'function') {
                        window.checkAuthStatus();
                    }
                } else {
                    var err = document.getElementById('master-pin-error');
                    if (res.data && res.data.retry_after) {
                        startMasterPinLockout(res.data.retry_after);
                    } else {
                        if (err) err.textContent = (res.data && res.data.error) || 'Incorrect PIN';
                        shakePinInput();
                        var inp = document.getElementById('master-pin-input');
                        if (inp) { inp.value = ''; inp.focus(); }
                    }
                }
            })
            .catch(function () {
                var err = document.getElementById('master-pin-error');
                if (err) err.textContent = 'Network error — please try again.';
            });
    }

    function clearMasterPinLockout() {
        if (lockoutTimer) {
            clearInterval(lockoutTimer);
            lockoutTimer = null;
        }
        pinLocked = false;
        var inp = document.getElementById('master-pin-input');
        if (inp) inp.disabled = false;
    }

    function startMasterPinLockout(seconds) {
        pinLocked = true;
        var inp = document.getElementById('master-pin-input');
        var err = document.getElementById('master-pin-error');
        if (inp) {
            inp.value = '';
            inp.disabled = true;
        }
        if (lockoutTimer) clearInterval(lockoutTimer);
        var remaining = Math.max(1, Number(seconds) || 1);
        function tick() {
            if (remaining > 0) {
                if (err) err.textContent = 'Too many attempts. Try again in ' + remaining + 's.';
                remaining -= 1;
                return;
            }
            clearMasterPinLockout();
            if (err) err.textContent = '';
            if (inp) inp.focus();
        }
        tick();
        lockoutTimer = setInterval(tick, 1000);
    }

    function shakePinInput() {
        var inp = document.getElementById('master-pin-input');
        if (!inp) return;
        inp.classList.remove('pin-shake');
        void inp.offsetWidth;
        inp.classList.add('pin-shake');
    }

    // -- Initialise on DOM ready --
    document.addEventListener('DOMContentLoaded', function () {
        var pinOverlay = document.getElementById('pin-overlay');
        var siteContent = document.getElementById('site-content');
        if (!pinOverlay || !siteContent) return;

        fetch('/api/check_auth')
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.authenticated) {
                    if (document.body && document.body.getAttribute('data-login-shell') === '1') {
                        window.location.reload();
                        return;
                    }
                    hideLoginOverlay();
                } else {
                    showLoginOverlay();
                }
            })
            .catch(function () {
                showLoginOverlay();
            });

        function readMasterPin() {
            var inp = document.getElementById('master-pin-input');
            return (inp ? inp.value : '').replace(/[\r\n]/g, '').slice(0, PIN_MAX);
        }

        var submitBtn = document.getElementById('master-pin-submit');
        if (submitBtn) {
            submitBtn.addEventListener('click', function () {
                if (pinLocked) return;
                var pin = readMasterPin();
                var err = document.getElementById('master-pin-error');
                if (pin.length < 4) {
                    if (err) err.textContent = 'Enter at least 4 characters.';
                    return;
                }
                submitMasterLogin(pin);
            });
        }

        var pinInput = document.getElementById('master-pin-input');
        if (pinInput) {
            pinInput.maxLength = PIN_MAX;
            pinInput.removeAttribute('pattern');
            pinInput.addEventListener('input', function () {
                if (pinLocked) return;
                if (autoSubmitTimer) {
                    clearTimeout(autoSubmitTimer);
                    autoSubmitTimer = null;
                }
                var val = pinInput.value.replace(/[\r\n]/g, '').slice(0, PIN_MAX);
                if (pinInput.value !== val) pinInput.value = val;
                var shortPin = /^\d{0,4}$/.test(val);
                pinInput.style.width = shortPin ? '' : '220px';
                pinInput.style.letterSpacing = shortPin ? '' : 'normal';
                pinInput.style.fontSize = shortPin ? '' : '1.15em';
                // A 4-digit PIN still unlocks on its own. The short wait lets a
                // longer PIN or passphrase keep being typed.
                if (/^\d{4}$/.test(val)) {
                    autoSubmitTimer = setTimeout(function () {
                        autoSubmitTimer = null;
                        if (!pinLocked && pinInput.value === val) submitMasterLogin(val);
                    }, 350);
                }
            });
            pinInput.addEventListener('keydown', function (e) {
                if (pinLocked) {
                    e.preventDefault();
                    return;
                }
                if (e.key === 'Enter') {
                    e.preventDefault();
                    if (autoSubmitTimer) {
                        clearTimeout(autoSubmitTimer);
                        autoSubmitTimer = null;
                    }
                    var val = readMasterPin();
                    if (val.length >= 4) submitMasterLogin(val);
                }
            });
        }
    });
}());
