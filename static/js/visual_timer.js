(() => {
    const root = document.getElementById('visual-timer');
    if (!root) return;

    const STORAGE_KEY = 'visualTimerState';
    const COUNTDOWN_SECONDS = 10;
    const CX = 110;
    const CY = 110;
    const RADIUS = 100;

    const COLORS = [
        { id: 'red', label: 'Classic red', fill: '#ef4444', glow: 'rgba(239, 68, 68, 0.45)' },
        { id: 'orange', label: 'Sunshine', fill: '#f59e0b', glow: 'rgba(245, 158, 11, 0.45)' },
        { id: 'lime', label: 'Lime', fill: '#84cc16', glow: 'rgba(132, 204, 22, 0.45)' },
        { id: 'sky', label: 'Sky', fill: '#38bdf8', glow: 'rgba(56, 189, 248, 0.45)' },
        { id: 'grape', label: 'Grape', fill: '#a78bfa', glow: 'rgba(167, 139, 250, 0.45)' },
        { id: 'pink', label: 'Bubblegum', fill: '#f472b6', glow: 'rgba(244, 114, 182, 0.45)' }
    ];

    const pie = document.getElementById('visual-timer-pie');
    const hand = document.getElementById('visual-timer-hand');
    const ticks = document.getElementById('visual-timer-ticks');
    const digits = document.getElementById('visual-timer-digits');
    const statusEl = document.getElementById('visual-timer-status');
    const face = document.getElementById('visual-timer-face');
    const colorWrap = document.getElementById('visual-timer-colors');
    const startBtn = document.getElementById('visual-timer-start');
    const pauseBtn = document.getElementById('visual-timer-pause');
    const resetBtn = document.getElementById('visual-timer-reset');
    const customForm = document.getElementById('visual-timer-custom-form');
    const customInput = document.getElementById('visual-timer-custom-min');
    const presetBtns = Array.from(document.querySelectorAll('.visual-timer-preset'));

    const state = {
        durationMs: 5 * 60 * 1000,
        remainingMs: 5 * 60 * 1000,
        endsAt: 0,
        running: false,
        finished: false,
        colorId: 'red',
        alertPlayed: false
    };

    let rafId = 0;
    let lastBeepSec = -1;
    let audioCtx = null;

    function currentColor() {
        return COLORS.find((c) => c.id === state.colorId) || COLORS[0];
    }

    function isMuted() {
        return typeof globalMute !== 'undefined' && globalMute;
    }

    function ensureAudio() {
        const AC = window.AudioContext || window.webkitAudioContext;
        if (!AC) return null;
        if (!audioCtx) audioCtx = new AC();
        if (audioCtx.state === 'suspended') audioCtx.resume();
        return audioCtx;
    }

    function playTone(freq, duration, delay, volume, type) {
        const ctx = ensureAudio();
        if (!ctx || isMuted()) return;
        const when = ctx.currentTime + (delay || 0);
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = type || 'sine';
        osc.frequency.setValueAtTime(freq, when);
        gain.gain.setValueAtTime(0.0001, when);
        gain.gain.exponentialRampToValueAtTime(volume || 0.18, when + 0.02);
        gain.gain.exponentialRampToValueAtTime(0.0001, when + duration);
        osc.connect(gain).connect(ctx.destination);
        osc.start(when);
        osc.stop(when + duration + 0.05);
    }

    function playTick(secondsLeft) {
        const pitch = 740 + (COUNTDOWN_SECONDS - secondsLeft) * 55;
        playTone(pitch, 0.12, 0, 0.16, 'triangle');
    }

    function playFinishedChime() {
        playTone(523.25, 0.22, 0, 0.2, 'sine');
        playTone(659.25, 0.22, 0.16, 0.2, 'sine');
        playTone(783.99, 0.28, 0.32, 0.22, 'sine');
        playTone(1046.5, 0.45, 0.5, 0.24, 'sine');
    }

    function persist() {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify({
                durationMs: state.durationMs,
                remainingMs: state.remainingMs,
                endsAt: state.endsAt,
                running: state.running,
                finished: state.finished,
                colorId: state.colorId,
                alertPlayed: state.alertPlayed
            }));
        } catch (e) { /* ignore quota / private mode */ }
    }

    function restore() {
        try {
            const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null');
            if (!saved || typeof saved !== 'object') return;
            if (COLORS.some((c) => c.id === saved.colorId)) state.colorId = saved.colorId;
            if (Number.isFinite(saved.durationMs) && saved.durationMs > 0) {
                state.durationMs = saved.durationMs;
            }
            if (saved.running && Number.isFinite(saved.endsAt)) {
                const remaining = Math.max(0, saved.endsAt - Date.now());
                state.endsAt = saved.endsAt;
                state.remainingMs = remaining;
                state.running = remaining > 0;
                state.finished = remaining <= 0;
                state.alertPlayed = remaining <= 0;
            } else {
                if (Number.isFinite(saved.remainingMs)) {
                    state.remainingMs = Math.max(0, Math.min(saved.remainingMs, state.durationMs));
                } else {
                    state.remainingMs = state.durationMs;
                }
                state.running = false;
                state.finished = !!saved.finished && state.remainingMs <= 0;
                state.alertPlayed = !!saved.alertPlayed;
            }
        } catch (e) { /* keep defaults */ }
    }

    function formatTime(ms) {
        const total = Math.max(0, Math.ceil(ms / 1000));
        const hours = Math.floor(total / 3600);
        const minutes = Math.floor((total % 3600) / 60);
        const seconds = total % 60;
        if (hours > 0) {
            return hours + ':' + String(minutes).padStart(2, '0') + ':' + String(seconds).padStart(2, '0');
        }
        return String(minutes).padStart(2, '0') + ':' + String(seconds).padStart(2, '0');
    }

    function piePath(fraction) {
        if (fraction <= 0.0005) return '';
        if (fraction >= 0.9995) {
            return 'M ' + CX + ' ' + (CY - RADIUS) +
                ' A ' + RADIUS + ' ' + RADIUS + ' 0 1 1 ' + CX + ' ' + (CY + RADIUS) +
                ' A ' + RADIUS + ' ' + RADIUS + ' 0 1 1 ' + CX + ' ' + (CY - RADIUS) + ' Z';
        }
        const sweep = fraction * 360;
        const rad = (sweep - 90) * Math.PI / 180;
        const x = CX + RADIUS * Math.cos(rad);
        const y = CY + RADIUS * Math.sin(rad);
        const large = sweep > 180 ? 1 : 0;
        return 'M ' + CX + ' ' + CY +
            ' L ' + CX + ' ' + (CY - RADIUS) +
            ' A ' + RADIUS + ' ' + RADIUS + ' 0 ' + large + ' 1 ' + x + ' ' + y + ' Z';
    }

    function handPoint(fraction) {
        const sweep = Math.max(0, Math.min(1, fraction)) * 360;
        const rad = (sweep - 90) * Math.PI / 180;
        return {
            x: CX + (RADIUS - 6) * Math.cos(rad),
            y: CY + (RADIUS - 6) * Math.sin(rad)
        };
    }

    function drawTicks() {
        if (!ticks || ticks.childElementCount) return;
        const ns = 'http://www.w3.org/2000/svg';
        for (let i = 0; i < 12; i++) {
            const angle = (i / 12) * Math.PI * 2 - Math.PI / 2;
            const inner = i % 3 === 0 ? 82 : 88;
            const line = document.createElementNS(ns, 'line');
            line.setAttribute('x1', String(CX + inner * Math.cos(angle)));
            line.setAttribute('y1', String(CY + inner * Math.sin(angle)));
            line.setAttribute('x2', String(CX + 97 * Math.cos(angle)));
            line.setAttribute('y2', String(CY + 97 * Math.sin(angle)));
            line.setAttribute('class', i % 3 === 0 ? 'visual-timer-tick visual-timer-tick-major' : 'visual-timer-tick');
            ticks.appendChild(line);
        }
    }

    function remainingNow() {
        if (state.running) return Math.max(0, state.endsAt - Date.now());
        return Math.max(0, state.remainingMs);
    }

    function syncPresetSelection() {
        presetBtns.forEach((btn) => {
            const ms = Number(btn.dataset.ms);
            btn.classList.toggle('is-selected', ms === state.durationMs && !state.finished);
        });
    }

    function render() {
        const remaining = remainingNow();
        const fraction = state.durationMs > 0 ? remaining / state.durationMs : 0;
        const color = currentColor();

        if (pie) {
            pie.setAttribute('d', piePath(fraction));
            pie.setAttribute('fill', color.fill);
        }
        if (hand) {
            const tip = handPoint(fraction);
            hand.setAttribute('x2', String(tip.x));
            hand.setAttribute('y2', String(tip.y));
            hand.setAttribute('stroke', color.fill);
            hand.style.opacity = remaining > 0 ? '1' : '0';
        }
        face.style.setProperty('--vt-fill', color.fill);
        face.style.setProperty('--vt-glow', color.glow);

        const ending = state.running && remaining > 0 && remaining <= COUNTDOWN_SECONDS * 1000;
        face.classList.toggle('is-running', state.running);
        face.classList.toggle('is-ending', ending);
        face.classList.toggle('is-finished', state.finished);

        digits.textContent = formatTime(remaining);
        if (state.finished) statusEl.textContent = "Time's up!";
        else if (state.running && ending) statusEl.textContent = 'Almost done…';
        else if (state.running) statusEl.textContent = 'Running';
        else if (remaining < state.durationMs && remaining > 0) statusEl.textContent = 'Paused';
        else statusEl.textContent = 'Pick a time';

        startBtn.disabled = state.running || state.durationMs <= 0;
        pauseBtn.disabled = !state.running;
        startBtn.innerHTML = remaining > 0 && remaining < state.durationMs && !state.running
            ? '<i class="fas fa-play"></i> Resume'
            : '<i class="fas fa-play"></i> Start';

        colorWrap.querySelectorAll('.visual-timer-color').forEach((btn) => {
            btn.classList.toggle('is-selected', btn.dataset.color === state.colorId);
        });
        syncPresetSelection();
    }

    function maybeCountdownBeep(remainingMs) {
        if (!state.running || state.finished) return;
        const sec = Math.ceil(remainingMs / 1000);
        if (sec < 1 || sec > COUNTDOWN_SECONDS) return;
        if (sec === lastBeepSec) return;
        lastBeepSec = sec;
        playTick(sec);
    }

    function finish() {
        state.running = false;
        state.finished = true;
        state.remainingMs = 0;
        state.endsAt = 0;
        if (rafId) {
            cancelAnimationFrame(rafId);
            rafId = 0;
        }
        if (!state.alertPlayed) {
            state.alertPlayed = true;
            playFinishedChime();
        }
        persist();
        render();
    }

    function tick() {
        if (!state.running) return;
        const remaining = remainingNow();
        state.remainingMs = remaining;
        if (remaining <= 0) {
            finish();
            return;
        }
        maybeCountdownBeep(remaining);
        render();
        rafId = requestAnimationFrame(tick);
    }

    function startLoop() {
        if (rafId) cancelAnimationFrame(rafId);
        rafId = requestAnimationFrame(tick);
    }

    function setDuration(ms, startAfter) {
        const next = Math.max(1000, Math.min(ms, 180 * 60 * 1000));
        state.durationMs = next;
        state.remainingMs = next;
        state.endsAt = 0;
        state.running = false;
        state.finished = false;
        state.alertPlayed = false;
        lastBeepSec = -1;
        if (rafId) {
            cancelAnimationFrame(rafId);
            rafId = 0;
        }
        persist();
        render();
        if (startAfter) startTimer();
    }

    function startTimer() {
        ensureAudio();
        if (state.running) return;
        if (state.finished || state.remainingMs <= 0) {
            state.remainingMs = state.durationMs;
            state.finished = false;
            state.alertPlayed = false;
        }
        state.running = true;
        state.finished = false;
        state.endsAt = Date.now() + state.remainingMs;
        lastBeepSec = -1;
        persist();
        render();
        startLoop();
    }

    function pauseTimer() {
        if (!state.running) return;
        state.remainingMs = remainingNow();
        state.running = false;
        state.endsAt = 0;
        if (rafId) {
            cancelAnimationFrame(rafId);
            rafId = 0;
        }
        persist();
        render();
    }

    function resetTimer() {
        state.remainingMs = state.durationMs;
        state.running = false;
        state.finished = false;
        state.alertPlayed = false;
        state.endsAt = 0;
        lastBeepSec = -1;
        if (rafId) {
            cancelAnimationFrame(rafId);
            rafId = 0;
        }
        persist();
        render();
    }

    function buildColors() {
        colorWrap.innerHTML = '';
        COLORS.forEach((color) => {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'visual-timer-color';
            btn.dataset.color = color.id;
            btn.title = color.label;
            btn.setAttribute('aria-label', color.label);
            btn.style.background = color.fill;
            btn.addEventListener('click', () => {
                state.colorId = color.id;
                persist();
                render();
            });
            colorWrap.appendChild(btn);
        });
    }

    presetBtns.forEach((btn) => {
        btn.addEventListener('click', () => {
            setDuration(Number(btn.dataset.ms));
        });
    });

    customForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const minutes = parseInt(customInput.value, 10);
        if (!Number.isFinite(minutes) || minutes < 1) {
            if (typeof showToast === 'function') showToast('Enter minutes from 1 to 180', 'warning');
            customInput.focus();
            return;
        }
        setDuration(Math.min(180, minutes) * 60 * 1000);
        customInput.value = '';
    });

    startBtn.addEventListener('click', startTimer);
    pauseBtn.addEventListener('click', pauseTimer);
    resetBtn.addEventListener('click', resetTimer);

    document.addEventListener('visibilitychange', () => {
        if (!document.hidden && state.running) render();
    });

    drawTicks();
    buildColors();
    restore();
    render();
    if (state.running) startLoop();
})();
