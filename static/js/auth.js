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
                    hideLoginOverlay();
                    if (typeof window.checkAuthStatus === 'function') {
                        window.checkAuthStatus();
                    }
                } else {
                    var err = document.getElementById('master-pin-error');
                    if (err) err.textContent = res.data.error || 'Incorrect PIN';
                    shakePinInput();
                    var inp = document.getElementById('master-pin-input');
                    if (inp) { inp.value = ''; inp.focus(); }
                }
            })
            .catch(function () {
                var err = document.getElementById('master-pin-error');
                if (err) err.textContent = 'Network error — please try again.';
            });
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
                var val = pinInput.value.replace(/\D/g, '').slice(0, 4);
                pinInput.value = val;
                if (val.length === 4) {
                    submitMasterLogin(val);
                }
            });
            pinInput.addEventListener('keydown', function (e) {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    var val = pinInput.value.replace(/\D/g, '').slice(0, 4);
                    if (val.length === 4) submitMasterLogin(val);
                }
            });
        }
    });
}());
