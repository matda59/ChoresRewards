// Shared side-nav collapse/expand behaviour for every page that includes
// templates/fragments/side_nav.html. (index.html additionally wires up
// scroll-spy + click-to-scroll in its own inline script.)
(function () {
    'use strict';
    const nav = document.getElementById('side-nav');
    const toggleBtn = document.getElementById('side-nav-toggle');
    if (!nav || !toggleBtn) return;
    const COLLAPSED_KEY = 'sideNavCollapsed';

    function setCollapsed(collapsed) {
        nav.classList.toggle('side-nav-collapsed', collapsed);
        document.body.classList.toggle('side-nav-body-collapsed', collapsed);
        toggleBtn.title = collapsed ? 'Open sidebar' : 'Close sidebar';
        const icon = toggleBtn.querySelector('i');
        if (icon) icon.className = collapsed ? 'fas fa-chevron-right' : 'fas fa-chevron-left';
        localStorage.setItem(COLLAPSED_KEY, collapsed ? '1' : '0');
    }

    setCollapsed(localStorage.getItem(COLLAPSED_KEY) === '1');
    toggleBtn.addEventListener('click', function () {
        setCollapsed(!nav.classList.contains('side-nav-collapsed'));
    });
})();
