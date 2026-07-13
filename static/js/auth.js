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
                    hideLoginOverlay();
                } else {
                    showLoginOverlay();
                }
            })
            .catch(function () {
                showLoginOverlay();
            });

        var submitBtn = document.getElementById('master-pin-submit');
        if (submitBtn) {
            submitBtn.addEventListener('click', function () {
                if (pinLocked) return;
                var inp = document.getElementById('master-pin-input');
                var pin = (inp ? inp.value : '').replace(/\D/g, '').slice(0, 4);
                var err = document.getElementById('master-pin-error');
                if (pin.length !== 4) {
                    if (err) err.textContent = 'Please enter a 4-digit PIN.';
                    return;
                }
                submitMasterLogin(pin);
            });
        }

        var pinInput = document.getElementById('master-pin-input');
        if (pinInput) {
            pinInput.addEventListener('input', function () {
                if (pinLocked) return;
                var val = pinInput.value.replace(/\D/g, '').slice(0, 4);
                pinInput.value = val;
                if (val.length === 4) {
                    submitMasterLogin(val);
                }
            });
            pinInput.addEventListener('keydown', function (e) {
                if (pinLocked) {
                    e.preventDefault();
                    return;
                }
                if (e.key === 'Enter') {
                    e.preventDefault();
                    var val = pinInput.value.replace(/\D/g, '').slice(0, 4);
                    if (val.length === 4) submitMasterLogin(val);
                }
            });
        }
    });
}());
