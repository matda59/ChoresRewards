// All-done celebration helpers. Kept out of the page so the dismiss rules
// can be tested without a browser.
(function (root, factory) {
    const api = factory();
    if (typeof module === 'object' && module.exports) {
        module.exports = api;
    }
    root.Celebration = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
    var DISMISS_MS = 8000;

    function dayKey(date) {
        var y = date.getFullYear();
        var m = String(date.getMonth() + 1).padStart(2, '0');
        var d = String(date.getDate()).padStart(2, '0');
        return y + '-' + m + '-' + d;
    }

    function personKey(personId, personName) {
        if (personId !== null && personId !== undefined && String(personId).trim() !== '') {
            return 'id:' + String(personId);
        }
        return 'name:' + String(personName || '').trim().toLowerCase();
    }

    function storageKey(who, day) {
        return 'cr-all-done:' + who + ':' + day;
    }

    function alreadyCelebrated(storage, who, day) {
        if (!storage || !who || !day) return false;
        try {
            return storage.getItem(storageKey(who, day)) === '1';
        } catch (err) {
            return false;
        }
    }

    function rememberCelebrated(storage, who, day) {
        if (!storage || !who || !day) return;
        try {
            storage.setItem(storageKey(who, day), '1');
        } catch (err) {
            /* private mode */
        }
    }

    function clickShouldDismiss(target) {
        var node = target;
        while (node) {
            var tag = String(node.tagName || '').toUpperCase();
            if (tag === 'BUTTON' || tag === 'A' || tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || tag === 'LABEL') {
                return false;
            }
            node = node.parentElement || node.parent || null;
        }
        return true;
    }

    return {
        DISMISS_MS: DISMISS_MS,
        dayKey: dayKey,
        personKey: personKey,
        storageKey: storageKey,
        alreadyCelebrated: alreadyCelebrated,
        rememberCelebrated: rememberCelebrated,
        clickShouldDismiss: clickShouldDismiss
    };
});
