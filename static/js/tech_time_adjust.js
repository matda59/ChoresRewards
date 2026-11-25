// Adjust weekend tech time from a kid card.
// The card button used to call adjustTechTime(id, {{ name|tojson }}) inside a
// double-quoted onclick. tojson emits double quotes, so the attribute ended at
// the name and the click threw before anything opened. This file listens for
// the button instead, and uses an on-page form because window.prompt does not
// open on the fridge tablet.
(function (root, factory) {
    const api = factory();
    if (typeof module === 'object' && module.exports) {
        module.exports = api;
    }
    root.TechTimeAdjust = api;
    if (typeof document !== 'undefined') {
        const start = function () { api.install(document); };
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', start);
        } else {
            start();
        }
    }
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
    function parseMinuteDelta(raw) {
        const text = String(raw == null ? '' : raw).trim();
        if (!/^-?\d+$/.test(text)) {
            return { ok: false, error: 'Enter a whole number of minutes. Use a minus to subtract.' };
        }
        const minutes = parseInt(text, 10);
        if (minutes === 0) {
            return { ok: false, error: 'Enter minutes to add or subtract, other than zero.' };
        }
        if (Math.abs(minutes) > 100000) {
            return { ok: false, error: 'That is too many minutes for one adjustment.' };
        }
        return { ok: true, minutes: minutes };
    }

    function adjustButtonFrom(target) {
        let node = target;
        while (node) {
            const cls = String(node.className || '');
            if (cls.split(/\s+/).indexOf('adjust-tech-time-btn') !== -1) {
                return node;
            }
            node = node.parentElement || node.parent || null;
        }
        return null;
    }

    function personFromButton(button) {
        if (!button) return null;
        const id = button.getAttribute ? button.getAttribute('data-person-id') : button.dataset && button.dataset.personId;
        const name = button.getAttribute ? (button.getAttribute('data-person-name') || '') : '';
        if (!id) return null;
        return { id: String(id), name: name };
    }

    function notify(message, type) {
        if (typeof showToast === 'function') {
            showToast(message, type || 'info');
            return;
        }
        if (typeof alert === 'function') alert(message);
    }

    function applyBalance(doc, personId, personName, display) {
        const id = String(personId);
        doc.querySelectorAll('[data-tech-minutes-for="' + id + '"]').forEach(function (el) {
            el.textContent = display;
        });
        doc.querySelectorAll('[data-tech-balance-for="' + id + '"]').forEach(function (el) {
            el.textContent = personName + ': ' + display;
        });
    }

    function ensureModal(doc) {
        if (doc.getElementById('tech-time-adjust-modal')) return;
        const wrap = doc.createElement('div');
        wrap.id = 'tech-time-adjust-modal';
        wrap.hidden = true;
        wrap.innerHTML =
            '<div class="tech-time-adjust-backdrop" data-adjust-cancel="1"></div>' +
            '<form class="tech-time-adjust-panel" id="tech-time-adjust-form">' +
            '<h3 id="tech-time-adjust-title">Adjust tech time</h3>' +
            '<p class="tech-time-adjust-help">Add minutes with a positive number. Subtract with a minus, for example -15.</p>' +
            '<label for="tech-time-adjust-minutes">Minutes</label>' +
            '<input id="tech-time-adjust-minutes" name="minutes" type="text" inputmode="text" autocomplete="off" enterkeyhint="next" placeholder="-15">' +
            '<label for="tech-time-adjust-note">Note (optional)</label>' +
            '<input id="tech-time-adjust-note" name="note" type="text" maxlength="200" autocomplete="off" enterkeyhint="done" placeholder="Watched a film">' +
            '<p id="tech-time-adjust-error" class="tech-time-adjust-error" role="alert"></p>' +
            '<div class="tech-time-adjust-actions">' +
            '<button type="submit" class="tech-time-adjust-save">Save</button>' +
            '<button type="button" class="tech-time-adjust-cancel" data-adjust-cancel="1">Cancel</button>' +
            '</div></form>';
        doc.body.appendChild(wrap);
        if (!doc.getElementById('tech-time-adjust-style')) {
            const style = doc.createElement('style');
            style.id = 'tech-time-adjust-style';
            style.textContent =
                '#tech-time-adjust-modal{position:fixed;inset:0;z-index:100000;display:flex;align-items:flex-end;justify-content:center;}' +
                '#tech-time-adjust-modal[hidden]{display:none;}' +
                '.tech-time-adjust-backdrop{position:absolute;inset:0;background:rgba(0,0,0,0.55);}' +
                '.tech-time-adjust-panel{position:relative;width:min(440px,100%);margin:0;padding:22px 18px 18px;border-radius:16px 16px 0 0;background:#1e293b;color:#f8fafc;box-shadow:0 -8px 40px rgba(0,0,0,0.45);}' +
                '.tech-time-adjust-panel h3{margin:0 0 8px;font-size:1.25rem;}' +
                '.tech-time-adjust-help{margin:0 0 14px;color:#cbd5e1;font-size:0.95rem;}' +
                '.tech-time-adjust-panel label{display:block;margin:10px 0 6px;font-weight:650;}' +
                '.tech-time-adjust-panel input{width:100%;box-sizing:border-box;font-size:1.15rem;padding:14px 12px;border-radius:10px;border:1px solid #475569;background:#0f172a;color:#f8fafc;}' +
                '.tech-time-adjust-error{min-height:1.2em;margin:10px 0 0;color:#fca5a5;font-weight:650;}' +
                '.tech-time-adjust-actions{display:flex;gap:10px;margin-top:14px;}' +
                '.tech-time-adjust-actions button{flex:1;min-height:48px;border:0;border-radius:12px;font-size:1.05rem;font-weight:750;cursor:pointer;}' +
                '.tech-time-adjust-save{background:#0284c7;color:#fff;}' +
                '.tech-time-adjust-cancel{background:#334155;color:#fff;}' +
                '@media (min-width:700px){#tech-time-adjust-modal{align-items:center;}.tech-time-adjust-panel{border-radius:16px;margin:16px;}}';
            doc.head.appendChild(style);
        }
    }

    function modalParts(doc) {
        return {
            root: doc.getElementById('tech-time-adjust-modal'),
            form: doc.getElementById('tech-time-adjust-form'),
            title: doc.getElementById('tech-time-adjust-title'),
            minutes: doc.getElementById('tech-time-adjust-minutes'),
            note: doc.getElementById('tech-time-adjust-note'),
            error: doc.getElementById('tech-time-adjust-error'),
        };
    }

    function setError(doc, message) {
        const error = doc.getElementById('tech-time-adjust-error');
        if (error) error.textContent = message || '';
    }

    function closeModal(doc) {
        const modal = doc.getElementById('tech-time-adjust-modal');
        if (!modal) return;
        modal.hidden = true;
        modal.dataset.personId = '';
        modal.dataset.personName = '';
        setError(doc, '');
    }

    function openModal(doc, person) {
        ensureModal(doc);
        const parts = modalParts(doc);
        parts.root.hidden = false;
        parts.root.dataset.personId = person.id;
        parts.root.dataset.personName = person.name;
        parts.title.textContent = 'Adjust tech time for ' + (person.name || 'this person');
        parts.minutes.value = '';
        parts.note.value = '';
        setError(doc, '');
        parts.minutes.focus();
    }

    function adultLocked() {
        return typeof isAdultMode === 'function' && !isAdultMode();
    }

    function onClick(event) {
        const doc = event.currentTarget && event.currentTarget.nodeType === 9
            ? event.currentTarget
            : document;
        const cancel = event.target && event.target.closest && event.target.closest('[data-adjust-cancel]');
        if (cancel && doc.getElementById('tech-time-adjust-modal')) {
            event.preventDefault();
            closeModal(doc);
            return;
        }
        const button = adjustButtonFrom(event.target);
        if (!button) return;
        event.preventDefault();
        if (adultLocked()) {
            notify('Ask an adult to unlock first.', 'warning');
            return;
        }
        const person = personFromButton(button);
        if (!person) {
            notify('Could not tell whose tech time to change.', 'error');
            return;
        }
        openModal(doc, person);
    }

    function save(doc) {
        const parts = modalParts(doc);
        if (!parts.root || parts.root.hidden) return;
        const parsed = parseMinuteDelta(parts.minutes.value);
        if (!parsed.ok) {
            setError(doc, parsed.error);
            parts.minutes.focus();
            return;
        }
        const personId = parts.root.dataset.personId;
        const personName = parts.root.dataset.personName || '';
        const note = parts.note.value.trim();
        setError(doc, '');
        fetch('/adjust_tech_time', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
            body: JSON.stringify({ person_id: personId, minutes: parsed.minutes, note: note }),
        })
        .then(function (response) {
            return response.json().catch(function () { return null; }).then(function (data) {
                return { response: response, data: data };
            });
        })
        .then(function (result) {
            if (result.response.status === 403 || (result.data && /adult/i.test(result.data.error || ''))) {
                setError(doc, 'Ask an adult to unlock first.');
                notify('Ask an adult to unlock first.', 'warning');
                return;
            }
            if (!result.response.ok || !result.data || !result.data.success) {
                const message = (result.data && (result.data.error || result.data.message)) || 'Could not save that change.';
                setError(doc, message);
                notify(message, 'error');
                return;
            }
            const display = result.data.tech_time_display;
            applyBalance(doc, personId, result.data.person_name || personName, display);
            closeModal(doc);
            notify((result.data.person_name || personName) + ' now has ' + display + '.', 'success');
        })
        .catch(function () {
            setError(doc, 'Could not save that change.');
            notify('Could not save that change.', 'error');
        });
    }

    function install(doc) {
        if (!doc || !doc.documentElement || doc.documentElement.dataset.techTimeAdjust === '1') return;
        doc.documentElement.dataset.techTimeAdjust = '1';
        ensureModal(doc);
        doc.addEventListener('click', onClick);
        const form = doc.getElementById('tech-time-adjust-form');
        if (form) {
            form.addEventListener('submit', function (event) {
                event.preventDefault();
                save(doc);
            });
        }
    }

    return {
        parseMinuteDelta: parseMinuteDelta,
        adjustButtonFrom: adjustButtonFrom,
        personFromButton: personFromButton,
        applyBalance: applyBalance,
        install: install,
        openModal: openModal,
        closeModal: closeModal,
    };
});
