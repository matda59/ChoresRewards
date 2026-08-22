/**
 * Screensaver / Photo Slideshow — idle detection + fullscreen overlay slideshow.
 * Self-contained: injects its own stylesheet + DOM, reads config from the
 * backend, and can be dropped into any page via a single <script> tag.
 *
 * Gestures while showing:
 *   swipe left  → next photo
 *   swipe right → previous photo
 *   tap, vertical swipe, pinch, mouse move, wheel, other keys → exit
 */
(function () {
    'use strict';

    if (window.ChoresScreensaver) return; // already initialised on this page

    const CONFIG_URL = '/api/screensaver/config';
    const CHORE_SUMMARY_URL = '/api/screensaver/chore_summary';
    const CONFIG_REFRESH_MS = 5 * 60 * 1000; // pick up settings/photo changes without a page reload
    const MOUSE_MOVE_THRESHOLD = 8; // px — ignore tiny jitter so it doesn't re-trigger instantly
    const SWIPE_MIN_PX = 50;
    const TAP_MAX_PX = 14;
    const ACTIVITY_EVENTS = ['mousedown', 'touchstart', 'wheel', 'scroll'];

    let config = null;
    let overlayEl = null;
    let layerEls = [];
    let activeLayerIdx = 0;
    let order = [];
    let currentOrderIdx = -1;
    let slideTimer = null;
    let clockTimer = null;
    let idleTimer = null;
    let showing = false;
    let lastMouseX = null;
    let lastMouseY = null;
    let forcedPreview = false;
    let choreSummaryTimer = null;
    let slideGen = 0;
    let gesture = null;
    let ignoreInputUntil = 0;
    const CHORE_SUMMARY_REFRESH_MS = 2 * 60 * 1000; // keep per-person/calendar overlay reasonably fresh
    const SHOW_INPUT_GRACE_MS = 450; // ignore the click/tap that launched the overlay

    function injectStylesheet() {
        if (document.getElementById('cr-screensaver-css')) return;
        const link = document.createElement('link');
        link.id = 'cr-screensaver-css';
        link.rel = 'stylesheet';
        link.href = '/static/css/screensaver.css';
        document.head.appendChild(link);
    }

    function buildOverlay() {
        if (overlayEl) return overlayEl;
        overlayEl = document.createElement('div');
        overlayEl.id = 'cr-screensaver-overlay';
        overlayEl.innerHTML = `
            <div class="cr-ss-fallback" id="cr-ss-fallback"></div>
            <div class="cr-ss-layer" id="cr-ss-layer-0"></div>
            <div class="cr-ss-layer" id="cr-ss-layer-1"></div>
            <div class="cr-ss-vignette"></div>
            <div class="cr-ss-overlay-info">
                <div class="cr-ss-clock" id="cr-ss-clock"></div>
                <div class="cr-ss-date" id="cr-ss-date"></div>
                <div class="cr-ss-info-panel" id="cr-ss-info-panel" style="display:none;">
                    <div class="cr-ss-people" id="cr-ss-people"></div>
                    <div class="cr-ss-events" id="cr-ss-events"></div>
                </div>
            </div>
            <div class="cr-ss-hint">Swipe for next photo · Tap to exit</div>
        `;
        document.body.appendChild(overlayEl);
        layerEls = [document.getElementById('cr-ss-layer-0'), document.getElementById('cr-ss-layer-1')];
        bindOverlayGestures(overlayEl);
        return overlayEl;
    }

    function bindOverlayGestures(el) {
        el.addEventListener('pointerdown', onOverlayPointerDown, { passive: false });
        el.addEventListener('pointermove', onOverlayPointerMove);
        el.addEventListener('pointerup', onOverlayPointerUp);
        el.addEventListener('pointercancel', clearGesture);
    }

    function clearGesture() {
        gesture = null;
    }

    function onOverlayPointerDown(e) {
        if (!showing) return;
        if (Date.now() < ignoreInputUntil) return;
        // Pinch / second finger: any extra pointer dismisses
        if (gesture && e.pointerId !== gesture.id) {
            hideScreensaver();
            resetIdleTimer();
            return;
        }
        gesture = { x: e.clientX, y: e.clientY, id: e.pointerId, type: null };
        try { overlayEl.setPointerCapture(e.pointerId); } catch (_) { /* ignore */ }
        e.preventDefault();
    }

    function onOverlayPointerMove(e) {
        if (!showing || !gesture || e.pointerId !== gesture.id) return;
        if (gesture.type) return;
        const dx = e.clientX - gesture.x;
        const dy = e.clientY - gesture.y;
        const absX = Math.abs(dx);
        const absY = Math.abs(dy);
        if (absX > SWIPE_MIN_PX && absX > absY * 1.15) {
            gesture.type = 'swipe';
            showSlide(dx < 0 ? 1 : -1);
            restartSlideTimer();
        } else if (absY > SWIPE_MIN_PX && absY > absX * 1.15) {
            gesture.type = 'exit';
            hideScreensaver();
            resetIdleTimer();
        }
    }

    function onOverlayPointerUp(e) {
        if (!gesture || e.pointerId !== gesture.id) return;
        const dx = e.clientX - gesture.x;
        const dy = e.clientY - gesture.y;
        const wasTap = !gesture.type && Math.hypot(dx, dy) <= TAP_MAX_PX;
        const unfinished = !gesture.type;
        gesture = null;
        if (wasTap || unfinished) {
            hideScreensaver();
            resetIdleTimer();
        }
    }

    function fetchConfig() {
        return fetch(CONFIG_URL, { credentials: 'same-origin' })
            .then(res => res.ok ? res.json() : null)
            .then(data => (data && data.success) ? data : null)
            .catch(() => null);
    }

    function shuffle(arr) {
        const a = arr.slice();
        for (let i = a.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [a[i], a[j]] = [a[j], a[i]];
        }
        return a;
    }

    function buildOrder() {
        const n = (config && config.photos) ? config.photos.length : 0;
        const indices = Array.from({ length: n }, (_, i) => i);
        order = (config && config.order === 'shuffle') ? shuffle(indices) : indices;
        currentOrderIdx = -1;
    }

    function resetIdleTimer() {
        clearTimeout(idleTimer);
        if (!config || !config.enabled) return;
        idleTimer = setTimeout(showScreensaver, config.idle_timeout * 1000);
    }

    function onActivity(e) {
        if (showing && Date.now() < ignoreInputUntil) return;
        if (showing) {
            // Overlay pointer handlers own tap / swipe; don't dismiss on the press itself
            if (gesture) return;
            if (overlayEl && overlayEl.contains(e.target) &&
                (e.type === 'mousedown' || e.type === 'touchstart')) {
                return;
            }
            if (e.type === 'mousemove') {
                if (lastMouseX === null) {
                    lastMouseX = e.clientX;
                    lastMouseY = e.clientY;
                    return;
                }
                const dx = Math.abs(e.clientX - lastMouseX);
                const dy = Math.abs(e.clientY - lastMouseY);
                lastMouseX = e.clientX;
                lastMouseY = e.clientY;
                if (dx < MOUSE_MOVE_THRESHOLD && dy < MOUSE_MOVE_THRESHOLD) return;
            }
            hideScreensaver();
        }
        resetIdleTimer();
    }

    function onKeyDown(e) {
        if (showing && Date.now() < ignoreInputUntil) return;
        if (!showing) {
            resetIdleTimer();
            return;
        }
        if (e.key === 'ArrowRight') {
            showSlide(1);
            restartSlideTimer();
            e.preventDefault();
            return;
        }
        if (e.key === 'ArrowLeft') {
            showSlide(-1);
            restartSlideTimer();
            e.preventDefault();
            return;
        }
        hideScreensaver();
        resetIdleTimer();
    }

    function updateClock() {
        const clockEl = document.getElementById('cr-ss-clock');
        const dateEl = document.getElementById('cr-ss-date');
        if (!clockEl || !dateEl) return;
        const now = new Date();
        clockEl.textContent = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        dateEl.textContent = now.toLocaleDateString([], { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
    }

    function escapeHtml(str) {
        return String(str).replace(/[&<>"']/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));
    }

    function renderPeople(people) {
        const el = document.getElementById('cr-ss-people');
        if (!el) return;
        if (!people || !people.length) { el.innerHTML = ''; return; }
        el.innerHTML = people.map(p => {
            const chores = (p.chores || []).map(c => `<li>${escapeHtml(c)}</li>`).join('');
            const status = p.remaining > 0
                ? `<ul class="cr-ss-person-chores">${chores}</ul>`
                : `<div class="cr-ss-person-done"><i class="fas fa-circle-check"></i> All done</div>`;
            return `
                <div class="cr-ss-person-card">
                    <img class="cr-ss-person-avatar" src="${p.avatar}" alt="" style="border-color:${p.color || '#fff'};">
                    <div class="cr-ss-person-info">
                        <div class="cr-ss-person-name">${escapeHtml(p.name)}</div>
                        ${status}
                    </div>
                </div>`;
        }).join('');
    }

    function renderEvents(events) {
        const el = document.getElementById('cr-ss-events');
        if (!el) return;
        if (!events || !events.length) { el.innerHTML = ''; return; }
        const items = events.map(ev => `
            <li>
                <span class="cr-ss-event-when">${escapeHtml(ev.all_day ? ev.weekday_short : `${ev.weekday_short} ${ev.start_time_display}`)}</span>
                <span class="cr-ss-event-title">${escapeHtml(ev.title)}</span>
            </li>`).join('');
        el.innerHTML = `<div class="cr-ss-events-title"><i class="fas fa-calendar-days"></i> Upcoming</div><ul>${items}</ul>`;
    }

    function updateChoreSummary() {
        const panel = document.getElementById('cr-ss-info-panel');
        if (!panel) return;
        if (!config || !config.overlay_chores) {
            panel.style.display = 'none';
            return;
        }
        fetch(CHORE_SUMMARY_URL, { credentials: 'same-origin' })
            .then(res => res.ok ? res.json() : null)
            .then(data => {
                if (!data || !data.success || !showing) return;
                panel.style.display = '';
                renderPeople(data.people);
                renderEvents(data.events);
            })
            .catch(() => {});
    }

    function showSlide(step) {
        const photos = (config && config.photos) || [];
        const fallback = document.getElementById('cr-ss-fallback');
        if (!photos.length) {
            if (fallback) fallback.style.display = '';
            layerEls.forEach(l => l.classList.remove('cr-ss-active'));
            return;
        }
        if (fallback) fallback.style.display = 'none';
        if (!order.length) buildOrder();
        const n = order.length;
        if (!n) return;

        if (currentOrderIdx < 0) {
            currentOrderIdx = step < 0 ? n - 1 : 0;
        } else {
            let next = currentOrderIdx + step;
            if (next >= n) {
                if (config && config.order === 'shuffle') buildOrder();
                next = 0;
            } else if (next < 0) {
                next = n - 1;
            }
            currentOrderIdx = next;
        }

        const photoIdx = order[currentOrderIdx];
        const url = photos[photoIdx];
        if (!url) return;

        const nextLayerIdx = 1 - activeLayerIdx;
        const incoming = layerEls[nextLayerIdx];
        const outgoing = layerEls[activeLayerIdx];
        const transition = (config && config.transition) || 'kenburns';
        const gen = ++slideGen;

        const img = new Image();
        img.onload = () => {
            if (gen !== slideGen) return;
            incoming.style.backgroundImage = `url("${url}")`;
            incoming.className = 'cr-ss-layer';
            if (transition === 'kenburns') {
                incoming.classList.add('cr-ss-kenburns');
                incoming.style.animationDuration = `${Math.max(config.slide_duration + 1, 4)}s`;
            } else if (transition === 'slide') {
                incoming.classList.add(step < 0 ? 'cr-ss-slide-prev' : 'cr-ss-slide');
            } else if (transition === 'none') {
                incoming.style.transition = 'none';
            }
            void incoming.offsetWidth;
            incoming.classList.add('cr-ss-active');
            if (outgoing) outgoing.classList.remove('cr-ss-active', 'cr-ss-kenburns', 'cr-ss-slide', 'cr-ss-slide-prev');
            activeLayerIdx = nextLayerIdx;
        };
        img.src = url;
    }

    function restartSlideTimer() {
        clearInterval(slideTimer);
        const duration = Math.max((config && config.slide_duration) || 8, 3) * 1000;
        slideTimer = setInterval(() => {
            if (document.hidden) return;
            showSlide(1);
        }, duration);
    }

    function startSlideshow() {
        buildOrder();
        showSlide(1);
        restartSlideTimer();
    }

    function stopSlideshow() {
        clearInterval(slideTimer);
        slideTimer = null;
    }

    function showScreensaver() {
        if (showing) return;
        if (!forcedPreview && (!config || !config.enabled)) return;
        buildOverlay();
        showing = true;
        gesture = null;
        ignoreInputUntil = Date.now() + SHOW_INPUT_GRACE_MS;
        lastMouseX = null;
        lastMouseY = null;
        overlayEl.classList.add('cr-ss-visible');
        document.getElementById('cr-ss-info-panel').style.display = 'none';
        updateClock();
        updateChoreSummary();
        clearInterval(clockTimer);
        clockTimer = setInterval(updateClock, 1000);
        clearInterval(choreSummaryTimer);
        choreSummaryTimer = setInterval(updateChoreSummary, CHORE_SUMMARY_REFRESH_MS);
        startSlideshow();
    }

    function hideScreensaver() {
        if (!showing) return;
        showing = false;
        forcedPreview = false;
        gesture = null;
        if (overlayEl) overlayEl.classList.remove('cr-ss-visible');
        stopSlideshow();
        clearInterval(clockTimer);
        clockTimer = null;
        clearInterval(choreSummaryTimer);
        choreSummaryTimer = null;
    }

    function init() {
        injectStylesheet();
        fetchConfig().then(cfg => {
            config = cfg || { enabled: false, photos: [] };
            resetIdleTimer();
        });
        setInterval(() => {
            fetchConfig().then(cfg => {
                if (cfg) {
                    config = cfg;
                    if (!showing) resetIdleTimer();
                }
            });
        }, CONFIG_REFRESH_MS);

        ACTIVITY_EVENTS.forEach(evt => document.addEventListener(evt, onActivity, { passive: true }));
        document.addEventListener('mousemove', onActivity, { passive: true });
        document.addEventListener('keydown', onKeyDown);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    window.ChoresScreensaver = {
        show: showScreensaver,
        hide: hideScreensaver,
        next: function () { if (showing) { showSlide(1); restartSlideTimer(); } },
        prev: function () { if (showing) { showSlide(-1); restartSlideTimer(); } },
        preview: function () {
            forcedPreview = true;
            if (!config) {
                fetchConfig().then(cfg => {
                    config = cfg || { enabled: false, photos: [], idle_timeout: 180, slide_duration: 8, transition: 'kenburns', order: 'shuffle', overlay_clock: true, overlay_chores: false };
                    showScreensaver();
                });
            } else {
                showScreensaver();
            }
        }
    };
})();
