(() => {
    const grid = document.getElementById('dashboard-grid');
    const section = document.getElementById('dashboard-section');
    const arrangeBtn = document.getElementById('dash-arrange-btn');
    const resetBtn = document.getElementById('dash-layout-reset-btn');
    if (!grid || !section) return;

    const STORAGE_KEY = 'dashboardLayoutV1';
    const GRID_COLS = 12;
    const ROW_UNIT = 18;
    const MINIMISED_ROWS = 3;
    const DEFAULT_ORDER = ['tasks', 'meals', 'events', 'rewards', 'photos', 'timer', 'play', 'notes'];
    const DEFAULTS = {
        tasks: { cols: 4, rows: 12 },
        meals: { cols: 4, rows: 8 },
        events: { cols: 4, rows: 8 },
        rewards: { cols: 4, rows: 9 },
        photos: { cols: 4, rows: 12 },
        timer: { cols: 2, rows: 8 },
        play: { cols: 4, rows: 11 },
        notes: { cols: 12, rows: 16 }
    };
    const MIN_SIZE = {
        tasks: { cols: 2, rows: 8 },
        meals: { cols: 2, rows: 6 },
        events: { cols: 2, rows: 6 },
        rewards: { cols: 2, rows: 7 },
        photos: { cols: 2, rows: 8 },
        timer: { cols: 2, rows: 6 },
        play: { cols: 2, rows: 8 },
        notes: { cols: 3, rows: 10 }
    };

    let arranging = false;
    let drag = null;
    let resize = null;

    function tiles() {
        return Array.from(grid.querySelectorAll('.dash-tile[data-dash-id]'));
    }

    function tileById(id) {
        return grid.querySelector('.dash-tile[data-dash-id="' + id + '"]');
    }

    function clamp(n, lo, hi) {
        return Math.min(hi, Math.max(lo, n));
    }

    function minFor(id) {
        return MIN_SIZE[id] || { cols: 2, rows: 6 };
    }

    function loadLayout() {
        try {
            const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null');
            if (saved && typeof saved === 'object') return saved;
        } catch (e) { /* keep defaults */ }
        return { order: DEFAULT_ORDER.slice(), tiles: {} };
    }

    function saveLayout(layout) {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(layout));
        } catch (e) { /* ignore */ }
    }

    function currentLayout() {
        const layout = { order: [], tiles: {} };
        tiles().forEach((el) => {
            const id = el.dataset.dashId;
            layout.order.push(id);
            const expanded = expandedSize(el);
            layout.tiles[id] = {
                cols: expanded.cols,
                rows: expanded.rows,
                minimised: el.classList.contains('is-minimised')
            };
        });
        return layout;
    }

    function applySize(el, size, opts) {
        const id = el.dataset.dashId;
        const mins = minFor(id);
        const minimised = !!(opts && opts.minimised);
        const cols = clamp(Math.round(size.cols), mins.cols, GRID_COLS);
        const rows = clamp(Math.round(size.rows), minimised ? MINIMISED_ROWS : mins.rows, 50);
        el.style.setProperty('--dash-cols', String(cols));
        el.style.setProperty('--dash-rows', String(rows));
    }

    function expandedSize(el) {
        const id = el.dataset.dashId;
        const fallback = DEFAULTS[id] || { cols: 4, rows: 8 };
        const cols = Number(el.dataset.expandedCols);
        const rows = Number(el.dataset.expandedRows);
        return {
            cols: cols || fallback.cols,
            rows: rows || fallback.rows
        };
    }

    function updateMinButton(el) {
        const btn = el.querySelector('.dash-tile-min');
        if (!btn) return;
        const minimised = el.classList.contains('is-minimised');
        const label = minimised ? 'Expand' : 'Minimise';
        btn.title = label;
        btn.setAttribute('aria-label', label);
        btn.innerHTML = minimised
            ? '<i class="fas fa-chevron-down"></i>'
            : '<i class="fas fa-minus"></i>';
    }

    function setMinimised(el, on) {
        const expanded = expandedSize(el);
        el.dataset.expandedCols = String(expanded.cols);
        el.dataset.expandedRows = String(expanded.rows);
        el.classList.toggle('is-minimised', !!on);
        applySize(el, on ? { cols: expanded.cols, rows: MINIMISED_ROWS } : expanded, { minimised: !!on });
        updateMinButton(el);
    }

    function toggleMinimised(el) {
        if (!el) return;
        setMinimised(el, !el.classList.contains('is-minimised'));
        saveLayout(currentLayout());
    }

    function applyLayout(layout) {
        const present = new Set(tiles().map((el) => el.dataset.dashId));
        const order = (layout.order || DEFAULT_ORDER).filter((id) => present.has(id));
        DEFAULT_ORDER.forEach((id) => {
            if (!present.has(id) || order.indexOf(id) !== -1) return;
            const notesAt = order.indexOf('notes');
            if (notesAt !== -1) order.splice(notesAt, 0, id);
            else order.push(id);
        });
        tiles().forEach((el) => {
            if (order.indexOf(el.dataset.dashId) === -1) order.push(el.dataset.dashId);
        });
        order.forEach((id) => {
            const el = tileById(id);
            if (el) grid.appendChild(el);
        });
        tiles().forEach((el) => {
            const id = el.dataset.dashId;
            const saved = (layout.tiles && layout.tiles[id]) || {};
            const fallback = DEFAULTS[id] || { cols: 4, rows: 8 };
            const size = {
                cols: saved.cols || fallback.cols,
                rows: saved.rows || fallback.rows
            };
            el.dataset.expandedCols = String(size.cols);
            el.dataset.expandedRows = String(size.rows);
            const minimised = !!saved.minimised;
            el.classList.toggle('is-minimised', minimised);
            applySize(el, minimised ? { cols: size.cols, rows: MINIMISED_ROWS } : size, { minimised: minimised });
            updateMinButton(el);
        });
    }

    function ensureMinButtons() {
        tiles().forEach((el) => {
            const title = el.querySelector('.dashboard-card-title');
            if (!title || title.querySelector('.dash-tile-min')) return;
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'dash-tile-min';
            btn.innerHTML = '<i class="fas fa-minus"></i>';
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                toggleMinimised(el);
            });
            title.appendChild(btn);
        });
    }

    function setArranging(on) {
        arranging = !!on;
        section.classList.toggle('is-arranging', arranging);
        if (arrangeBtn) {
            arrangeBtn.classList.toggle('is-active', arranging);
            arrangeBtn.innerHTML = arranging
                ? '<i class="fas fa-check"></i> Done'
                : '<i class="fas fa-up-down-left-right"></i> Arrange';
        }
        if (resetBtn) resetBtn.hidden = !arranging;
    }

    window.DashboardLayout = {
        isArranging: () => arranging
    };

    ensureMinButtons();
    applyLayout(loadLayout());

    if (arrangeBtn) {
        arrangeBtn.addEventListener('click', () => setArranging(!arranging));
    }
    if (resetBtn) {
        resetBtn.addEventListener('click', () => {
            localStorage.removeItem(STORAGE_KEY);
            applyLayout({ order: DEFAULT_ORDER.slice(), tiles: {} });
        });
    }

    grid.addEventListener('click', (e) => {
        if (e.target.closest('.dash-tile-min')) return;
        const anyTile = e.target.closest('.dash-tile');
        if (anyTile && grid.contains(anyTile) && anyTile.classList.contains('is-minimised')) {
            if (arranging || drag || resize) return;
            if (e.target.closest('.dash-tile-handle, .dash-tile-resize')) return;
            e.preventDefault();
            toggleMinimised(anyTile);
            return;
        }
        if (arranging || drag || resize) return;
        if (e.target.closest('.dash-tile-handle, .dash-tile-resize, .dash-note-add-btn, .visual-timer-launcher, .play-launch')) return;
        const tile = e.target.closest('.dash-tile[data-dash-nav]');
        if (!tile || !grid.contains(tile)) return;
        if (typeof goToSection === 'function') goToSection(tile.dataset.dashNav);
    });

    function colWidth() {
        const styles = window.getComputedStyle(grid);
        const gap = parseFloat(styles.columnGap) || 16;
        return (grid.clientWidth - gap * (GRID_COLS - 1)) / GRID_COLS;
    }

    function startResize(e, tile) {
        if (!arranging || tile.classList.contains('is-minimised')) return;
        e.preventDefault();
        e.stopPropagation();
        const id = tile.dataset.dashId;
        resize = {
            tile,
            startX: e.clientX,
            startY: e.clientY,
            cols: Number(tile.style.getPropertyValue('--dash-cols')) || (DEFAULTS[id] || {}).cols || 4,
            rows: Number(tile.style.getPropertyValue('--dash-rows')) || (DEFAULTS[id] || {}).rows || 8,
            pointerId: e.pointerId
        };
        tile.classList.add('is-resizing');
        e.currentTarget.setPointerCapture(e.pointerId);
    }

    function moveResize(e) {
        if (!resize) return;
        const dx = e.clientX - resize.startX;
        const dy = e.clientY - resize.startY;
        const nextCols = window.innerWidth < 700 ? resize.cols : resize.cols + dx / colWidth();
        const nextRows = resize.rows + dy / ROW_UNIT;
        applySize(resize.tile, { cols: nextCols, rows: nextRows });
    }

    function endResize() {
        if (!resize) return;
        const tile = resize.tile;
        tile.classList.remove('is-resizing');
        if (!tile.classList.contains('is-minimised')) {
            const cols = Number(tile.style.getPropertyValue('--dash-cols'));
            const rows = Number(tile.style.getPropertyValue('--dash-rows'));
            if (cols) tile.dataset.expandedCols = String(cols);
            if (rows) tile.dataset.expandedRows = String(rows);
        }
        resize = null;
        saveLayout(currentLayout());
    }

    function placeholderFor(tile) {
        const ph = document.createElement('div');
        ph.className = 'dash-tile-placeholder';
        ph.style.setProperty('--dash-cols', tile.style.getPropertyValue('--dash-cols') || '4');
        ph.style.setProperty('--dash-rows', tile.style.getPropertyValue('--dash-rows') || '8');
        return ph;
    }

    function startDrag(e, tile) {
        if (!arranging) return;
        if (e.button != null && e.button !== 0) return;
        e.preventDefault();
        e.stopPropagation();
        const rect = tile.getBoundingClientRect();
        drag = {
            tile,
            offsetX: e.clientX - rect.left,
            offsetY: e.clientY - rect.top,
            width: rect.width,
            height: rect.height,
            startX: e.clientX,
            startY: e.clientY,
            moved: false,
            placeholder: null,
            pointerId: e.pointerId
        };
        e.currentTarget.setPointerCapture(e.pointerId);
    }

    function liftTile(e) {
        if (!drag || drag.moved) return;
        drag.moved = true;
        const tile = drag.tile;
        drag.placeholder = placeholderFor(tile);
        tile.after(drag.placeholder);
        tile.classList.add('is-dragging');
        tile.style.width = drag.width + 'px';
        tile.style.height = drag.height + 'px';
        tile.style.left = (e.clientX - drag.offsetX) + 'px';
        tile.style.top = (e.clientY - drag.offsetY) + 'px';
        document.body.classList.add('dash-layout-dragging');
    }

    function movePlaceholder(x, y) {
        const under = document.elementFromPoint(x, y);
        if (!under) return;
        const target = under.closest('.dash-tile, .dash-tile-placeholder');
        if (!target || target === drag.tile || target === drag.placeholder) return;
        if (!grid.contains(target)) return;
        const rect = target.getBoundingClientRect();
        const before = y < rect.top + rect.height / 2;
        if (before) grid.insertBefore(drag.placeholder, target);
        else target.after(drag.placeholder);
    }

    function moveDrag(e) {
        if (!drag) return;
        const dist = Math.abs(e.clientX - drag.startX) + Math.abs(e.clientY - drag.startY);
        if (!drag.moved && dist > 8) liftTile(e);
        if (!drag.moved) return;
        drag.tile.style.left = (e.clientX - drag.offsetX) + 'px';
        drag.tile.style.top = (e.clientY - drag.offsetY) + 'px';
        movePlaceholder(e.clientX, e.clientY);
    }

    function endDrag() {
        if (!drag) return;
        const tile = drag.tile;
        if (drag.moved && drag.placeholder) {
            drag.placeholder.replaceWith(tile);
        }
        tile.classList.remove('is-dragging');
        tile.style.width = '';
        tile.style.height = '';
        tile.style.left = '';
        tile.style.top = '';
        document.body.classList.remove('dash-layout-dragging');
        drag = null;
        saveLayout(currentLayout());
    }

    grid.addEventListener('pointerdown', (e) => {
        const handle = e.target.closest('.dash-tile-handle');
        const resizeHandle = e.target.closest('.dash-tile-resize');
        const tile = e.target.closest('.dash-tile');
        if (!tile || !grid.contains(tile)) return;
        if (handle) startDrag(e, tile);
        else if (resizeHandle) startResize(e, tile);
    });

    grid.addEventListener('pointermove', (e) => {
        if (resize) moveResize(e);
        else if (drag) moveDrag(e);
    });

    function endPointer() {
        if (resize) endResize();
        if (drag) endDrag();
    }

    grid.addEventListener('pointerup', endPointer);
    grid.addEventListener('pointercancel', endPointer);
})();
