/**
 * auth.js — Initial session login (person-picker flow)
 *
 * On every page load:
 *  1. Check /api/check_auth — if the Flask session already has authenticated=True, show content.
 *  2. Otherwise show the person-picker overlay so the user can log in as themselves.
 *
 * The padlock button (adult/child mode) is handled separately by auth_profile.js.
 */
(function () {
    'use strict';

    var _selectedPersonId = null;
    var _selectedHasPin = false;
    var _defaultAvatarUrl = '/static/default_avatar.png';

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
        showFlex('person-picker-screen');
        hide('pin-entry-screen');
        hide('site-content');
    }

    function hideLoginOverlay() {
        hide('pin-overlay');
        show('site-content');
    }

    // -- Person picker --
    window.selectPerson = function (personId, hasPin, personName, avatarUrl) {
        _selectedPersonId = personId;
        _selectedHasPin = hasPin;

        if (!hasPin) {
            // No PIN is set — don't allow login (security: app may be internet-facing)
            if (window.showToast) {
                showToast('No PIN set for ' + personName + ' — ask an adult to add one in Settings', 'warning');
            }
            return;
        }

        var nameEl = document.getElementById('login-person-name');
        var avatarEl = document.getElementById('login-person-avatar');
        var errorEl = document.getElementById('master-pin-error');
        var inputEl = document.getElementById('master-pin-input');

        if (nameEl) nameEl.textContent = personName;
        if (avatarEl) avatarEl.src = avatarUrl || _defaultAvatarUrl;
        if (errorEl) errorEl.textContent = '';
        if (inputEl) { inputEl.value = ''; }

        hide('person-picker-screen');
        showFlex('pin-entry-screen');

        setTimeout(function () {
            var inp = document.getElementById('master-pin-input');
            if (inp) inp.focus();
        }, 80);
    };

    window.backToPersonPicker = function () {
        hide('pin-entry-screen');
        showFlex('person-picker-screen');
        var inp = document.getElementById('master-pin-input');
        if (inp) inp.value = '';
        var err = document.getElementById('master-pin-error');
        if (err) err.textContent = '';
    };

    // -- Submit person login --
    function submitPersonLogin(pin) {
        fetch('/api/person_login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ person_id: _selectedPersonId, pin: pin }),
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
                submitPersonLogin(pin);
            });
        }

        var pinInput = document.getElementById('master-pin-input');
        if (pinInput) {
            pinInput.addEventListener('input', function () {
                var val = pinInput.value.replace(/\D/g, '').slice(0, 4);
                pinInput.value = val;
                if (val.length === 4) {
                    submitPersonLogin(val);
                }
            });
            pinInput.addEventListener('keydown', function (e) {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    var val = pinInput.value.replace(/\D/g, '').slice(0, 4);
                    if (val.length === 4) submitPersonLogin(val);
                }
            });
        }

        document.querySelectorAll('.person-picker-btn:not([disabled])').forEach(function (btn) {
            btn.addEventListener('mouseenter', function () {
                btn.style.background = 'rgba(255,255,255,0.13)';
                btn.style.borderColor = 'rgba(255,255,255,0.32)';
                btn.style.transform = 'translateY(-2px)';
            });
            btn.addEventListener('mouseleave', function () {
                btn.style.background = 'rgba(255,255,255,0.06)';
                btn.style.borderColor = 'rgba(255,255,255,0.12)';
                btn.style.transform = '';
            });
        });
    });
}());
