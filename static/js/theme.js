// ── Light/Dark theme toggle ──────────────────────────────────────────────────
// Applies/persists `data-theme` on <html>. The actual attribute is also set as
// early as possible via an inline blocking script in each page's <head> to
// avoid a flash of the wrong theme before this file loads.
(function (global) {
    var STORAGE_KEY = 'cr-theme';

    function getTheme() {
        return document.documentElement.getAttribute('data-theme') === 'light' ? 'light' : 'dark';
    }

    function applyIcon(btn, theme) {
        var icon = btn.querySelector('i');
        if (!icon) return;
        icon.className = theme === 'light' ? 'fas fa-moon' : 'fas fa-sun';
    }

    function setTheme(theme, btn) {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem(STORAGE_KEY, theme);
        if (btn) applyIcon(btn, theme);
    }

    function initThemeToggle(buttonId) {
        var btn = document.getElementById(buttonId);
        if (!btn) return;
        applyIcon(btn, getTheme());
        btn.addEventListener('click', function () {
            setTheme(getTheme() === 'light' ? 'dark' : 'light', btn);
        });
    }

    global.initThemeToggle = initThemeToggle;
})(window);
