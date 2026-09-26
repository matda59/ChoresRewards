/* Dashboard Play tile: maths practice and a colour game. */
(() => {
    const logic = window.PlayWidgetLogic;
    const overlay = document.getElementById('play-overlay');
    const mathsPanel = document.getElementById('play-maths');
    const coloursPanel = document.getElementById('play-colours');
    if (!logic || !overlay || !mathsPanel || !coloursPanel) return;

    const STORAGE_KEY = 'playWidgetV1';
    const openMathsBtn = document.getElementById('play-open-maths');
    const openColoursBtn = document.getElementById('play-open-colours');
    const closeBtn = document.getElementById('play-close');
    const backdrop = document.getElementById('play-backdrop');
    const titleText = document.getElementById('play-title-text');
    const scoreEl = document.getElementById('play-score');
    const eqPrompt = document.getElementById('play-eq-prompt');
    const eqAnswer = document.getElementById('play-eq-answer');
    const equation = document.getElementById('play-equation');
    const mathsFeedback = document.getElementById('play-maths-feedback');
    const keypad = document.getElementById('play-keypad');
    const findPanel = document.getElementById('play-find');
    const mixPanel = document.getElementById('play-mix');
    const findGrid = document.getElementById('play-find-grid');
    const findSwatch = document.getElementById('play-find-swatch');
    const findWord = document.getElementById('play-find-word');
    const findFeedback = document.getElementById('play-find-feedback');
    const potA = document.getElementById('play-pot-a');
    const potB = document.getElementById('play-pot-b');
    const potResult = document.getElementById('play-pot-result');
    const mixCaption = document.getElementById('play-mix-caption');
    const paintbox = document.getElementById('play-paintbox');
    const panel = overlay.querySelector('.play-overlay-panel');

    const state = {
        game: null,
        mathsMode: 'times',
        colourMode: 'find',
        streaks: { add: 0, times: 0, mix: 0, find: 0 },
        best: { add: 0, times: 0, mix: 0, find: 0 },
        question: null,
        typed: '',
        misses: 0,
        locked: false,
        findRound: null,
        findMissed: false,
        mix: { a: null, b: null, selected: 'a' },
        timer: 0
    };

    let audioCtx = null;
    const burst = document.createElement('div');
    burst.className = 'play-burst';
    burst.setAttribute('aria-hidden', 'true');
    if (panel) panel.appendChild(burst);

    function loadBest() {
        try {
            const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null');
            if (saved && saved.best) {
                ['add', 'times', 'mix', 'find'].forEach((key) => {
                    const n = Number(saved.best[key]);
                    if (Number.isFinite(n) && n > 0) state.best[key] = Math.floor(n);
                });
            }
            if (saved && (saved.mathsMode === 'add' || saved.mathsMode === 'times' || saved.mathsMode === 'mix')) {
                state.mathsMode = saved.mathsMode;
            }
            if (saved && (saved.colourMode === 'find' || saved.colourMode === 'mix')) {
                state.colourMode = saved.colourMode;
            }
        } catch (e) { /* keep defaults */ }
    }

    function saveBest() {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify({
                best: state.best,
                mathsMode: state.mathsMode,
                colourMode: state.colourMode
            }));
        } catch (e) { /* ignore */ }
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

    function playTone(freq, duration, delay, volume) {
        const ctx = ensureAudio();
        if (!ctx || isMuted()) return;
        const when = ctx.currentTime + (delay || 0);
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(freq, when);
        gain.gain.setValueAtTime(0.0001, when);
        gain.gain.exponentialRampToValueAtTime(volume || 0.12, when + 0.02);
        gain.gain.exponentialRampToValueAtTime(0.0001, when + duration);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(when);
        osc.stop(when + duration + 0.02);
    }

    function playRight() {
        playTone(523, 0.12, 0, 0.12);
        playTone(659, 0.12, 0.09, 0.12);
        playTone(784, 0.18, 0.18, 0.14);
        if (navigator.vibrate) navigator.vibrate(12);
    }

    function playWrong() {
        playTone(196, 0.16, 0, 0.08);
        if (navigator.vibrate) navigator.vibrate(30);
    }

    function say(text) {
        if (isMuted() || !text) return;
        const synth = window.speechSynthesis;
        if (!synth || typeof SpeechSynthesisUtterance !== 'function') return;
        try {
            const utter = new SpeechSynthesisUtterance(text);
            utter.rate = 0.95;
            utter.pitch = 1.08;
            synth.cancel();
            synth.speak(utter);
        } catch (e) { /* speech is optional */ }
    }

    function silence() {
        try {
            if (window.speechSynthesis) window.speechSynthesis.cancel();
        } catch (e) { /* ignore */ }
    }

    function inkFor(hex) {
        const n = parseInt(String(hex).slice(1), 16);
        if (!Number.isFinite(n)) return '#1e293b';
        const r = (n >> 16) & 255;
        const g = (n >> 8) & 255;
        const b = n & 255;
        const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
        return luminance > 0.64 ? '#1e293b' : '#ffffff';
    }

    function shapeMarkup(shape, hex) {
        const attrs = 'fill="' + hex + '" stroke="#64748b" stroke-width="3"';
        if (shape === 'circle') {
            return '<svg viewBox="0 0 100 100" aria-hidden="true"><circle cx="50" cy="50" r="40" ' + attrs + '/></svg>';
        }
        if (shape === 'square') {
            return '<svg viewBox="0 0 100 100" aria-hidden="true"><rect x="14" y="14" width="72" height="72" rx="12" ' + attrs + '/></svg>';
        }
        if (shape === 'diamond') {
            return '<svg viewBox="0 0 100 100" aria-hidden="true"><polygon points="50,8 92,50 50,92 8,50" ' + attrs + '/></svg>';
        }
        if (shape === 'triangle') {
            return '<svg viewBox="0 0 100 100" aria-hidden="true"><polygon points="50,10 92,88 8,88" ' + attrs + '/></svg>';
        }
        if (shape === 'star') {
            return '<svg viewBox="0 0 100 100" aria-hidden="true"><polygon points="50,5 61,35 95,35 68,57 79,91 50,70 21,91 32,57 5,35 39,35" ' + attrs + '/></svg>';
        }
        return '<svg viewBox="0 0 100 100" aria-hidden="true"><path d="M50 84 C20 62 8 44 8 30 C8 16 20 8 32 8 C40 8 46 12 50 20 C54 12 60 8 68 8 C80 8 92 16 92 30 C92 44 80 62 50 84Z" ' + attrs + '/></svg>';
    }

    function burstAt(hex) {
        if (!burst || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
        for (let i = 0; i < 14; i += 1) {
            const bit = document.createElement('span');
            bit.className = 'play-confetti';
            bit.style.background = i % 3 === 0 ? hex : ['#f97316', '#facc15', '#22c55e', '#3b82f6', '#a855f7', '#f472b6'][i % 6];
            bit.style.left = (30 + Math.random() * 40) + '%';
            bit.style.top = (28 + Math.random() * 30) + '%';
            bit.style.setProperty('--dx', (Math.random() * 180 - 90) + 'px');
            bit.style.setProperty('--dy', (Math.random() * -140 - 20) + 'px');
            burst.appendChild(bit);
            setTimeout(() => bit.remove(), 750);
        }
    }

    function clearTimer() {
        if (state.timer) {
            clearTimeout(state.timer);
            state.timer = 0;
        }
    }

    function scoreKey() {
        if (state.game === 'maths') return state.mathsMode;
        if (state.game === 'colours' && state.colourMode === 'find') return 'find';
        return null;
    }

    function renderScore() {
        const key = scoreKey();
        if (!scoreEl) return;
        if (!key) {
            scoreEl.hidden = true;
            return;
        }
        const streak = state.streaks[key] || 0;
        const best = state.best[key] || 0;
        const parts = [];
        if (streak) parts.push(streak + ' in a row');
        if (best) parts.push('best ' + best);
        if (!parts.length) {
            scoreEl.hidden = true;
            scoreEl.textContent = '';
            return;
        }
        scoreEl.hidden = false;
        scoreEl.textContent = parts.join(' · ');
    }

    function noteBest(key) {
        if ((state.streaks[key] || 0) > (state.best[key] || 0)) {
            state.best[key] = state.streaks[key];
            saveBest();
            return true;
        }
        return false;
    }

    function setModes(selector, attr, current) {
        overlay.querySelectorAll(selector).forEach((btn) => {
            btn.classList.toggle('is-selected', btn.getAttribute(attr) === current);
        });
    }

    function showGame(game) {
        state.game = game;
        mathsPanel.hidden = game !== 'maths';
        coloursPanel.hidden = game !== 'colours';
        if (titleText) titleText.textContent = game === 'maths' ? 'Maths' : 'Colours';
        setModes('[data-maths-mode]', 'data-maths-mode', state.mathsMode);
        setModes('[data-colour-mode]', 'data-colour-mode', state.colourMode);
        renderScore();
    }

    function renderTyped() {
        if (!eqAnswer) return;
        if (!state.typed) {
            eqAnswer.textContent = '?';
            eqAnswer.classList.remove('is-filled');
            return;
        }
        eqAnswer.textContent = state.typed;
        eqAnswer.classList.add('is-filled');
    }

    function newMathsQuestion() {
        clearTimer();
        state.locked = false;
        state.misses = 0;
        state.typed = '';
        state.question = logic.nextMathQuestion(
            state.mathsMode,
            state.streaks[state.mathsMode] || 0,
            Math.random,
            state.question ? state.question.prompt : ''
        );
        if (eqPrompt) eqPrompt.textContent = state.question.prompt;
        if (equation) equation.classList.remove('is-right', 'is-wrong');
        if (mathsFeedback) mathsFeedback.textContent = '';
        renderTyped();
        renderScore();
        if (keypad) {
            keypad.querySelectorAll('button').forEach((btn) => { btn.disabled = false; });
        }
    }

    function lockKeypad(on) {
        state.locked = on;
        if (keypad) keypad.querySelectorAll('button').forEach((btn) => { btn.disabled = on; });
    }

    function finishMathsRound(message, delay) {
        if (mathsFeedback) mathsFeedback.textContent = message;
        lockKeypad(true);
        renderScore();
        clearTimer();
        state.timer = setTimeout(newMathsQuestion, delay);
    }

    function submitMaths() {
        if (state.locked || !state.question || state.typed === '') return;
        const value = Number(state.typed);
        const mode = state.mathsMode;
        if (value === state.question.answer) {
            state.streaks[mode] = (state.streaks[mode] || 0) + 1;
            const isBest = noteBest(mode);
            if (equation) {
                equation.classList.remove('is-wrong');
                equation.classList.add('is-right');
            }
            playRight();
            burstAt('#22c55e');
            let message = 'Yes!';
            if (isBest && state.streaks[mode] > 1) message = 'New best!';
            else if (state.streaks[mode] % 5 === 0) message = state.streaks[mode] + ' in a row!';
            finishMathsRound(message, 750);
            return;
        }
        state.streaks[mode] = 0;
        state.misses += 1;
        playWrong();
        if (equation) {
            equation.classList.remove('is-right');
            equation.classList.remove('is-wrong');
            void equation.offsetWidth;
            equation.classList.add('is-wrong');
        }
        renderScore();
        if (state.misses >= 2) {
            state.typed = String(state.question.answer);
            renderTyped();
            if (equation) {
                equation.classList.remove('is-wrong');
                equation.classList.add('is-right');
            }
            finishMathsRound('It\u2019s ' + state.question.answer, 1100);
            return;
        }
        if (mathsFeedback) mathsFeedback.textContent = 'Not quite';
    }

    function pushDigit(digit) {
        if (state.locked || state.game !== 'maths') return;
        if (state.typed.length >= 4) return;
        if (digit === '0' && state.typed === '0') return;
        state.typed = (state.typed === '0' ? '' : state.typed) + digit;
        if (equation) equation.classList.remove('is-wrong', 'is-right');
        renderTyped();
    }

    function backspace() {
        if (state.locked || state.game !== 'maths') return;
        state.typed = state.typed.slice(0, -1);
        if (equation) equation.classList.remove('is-wrong', 'is-right');
        renderTyped();
    }

    function buildKeypad() {
        if (!keypad || keypad.childElementCount) return;
        const keys = ['1', '2', '3', '4', '5', '6', '7', '8', '9', 'del', '0', 'ok'];
        keys.forEach((key) => {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'play-key';
            if (key === 'del') {
                btn.classList.add('play-key-del');
                btn.setAttribute('aria-label', 'Delete');
                btn.textContent = '\u232b';
                btn.addEventListener('click', backspace);
            } else if (key === 'ok') {
                btn.classList.add('play-key-ok');
                btn.setAttribute('aria-label', 'Check answer');
                btn.innerHTML = '<i class="fas fa-check" aria-hidden="true"></i>';
                btn.addEventListener('click', submitMaths);
            } else {
                btn.textContent = key;
                btn.setAttribute('aria-label', key);
                btn.addEventListener('click', () => pushDigit(key));
            }
            keypad.appendChild(btn);
        });
    }

    function newFindRound() {
        clearTimer();
        state.locked = false;
        state.findMissed = false;
        state.findRound = logic.pickFindRound(state.streaks.find || 0, Math.random);
        const target = state.findRound.target;
        if (findSwatch) findSwatch.style.background = target.hex;
        if (findWord) {
            findWord.textContent = target.name;
            findWord.style.background = target.hex;
            findWord.style.color = inkFor(target.hex);
        }
        if (findFeedback) findFeedback.textContent = '';
        if (findGrid) {
            findGrid.innerHTML = '';
            state.findRound.choices.forEach((choice) => {
                const btn = document.createElement('button');
                btn.type = 'button';
                btn.className = 'play-shape-btn';
                btn.setAttribute('aria-label', choice.color.name);
                btn.innerHTML = shapeMarkup(choice.shape, choice.color.hex);
                btn.addEventListener('click', () => onFindTap(choice.color, btn));
                findGrid.appendChild(btn);
            });
        }
        renderScore();
        say('Find ' + target.name);
    }

    function onFindTap(color, btn) {
        if (state.locked || !state.findRound) return;
        if (color.id === state.findRound.target.id) {
            if (!state.findMissed) {
                state.streaks.find = (state.streaks.find || 0) + 1;
                noteBest('find');
            }
            state.locked = true;
            btn.classList.add('is-right');
            if (findFeedback) {
                const label = color.name.charAt(0).toUpperCase() + color.name.slice(1);
                findFeedback.textContent = (state.streaks.find && state.streaks.find % 5 === 0 && !state.findMissed)
                    ? state.streaks.find + ' in a row!'
                    : 'Yes! ' + label + '!';
            }
            playRight();
            burstAt(color.hex);
            say(color.name);
            renderScore();
            clearTimer();
            state.timer = setTimeout(newFindRound, 1400);
            return;
        }
        state.findMissed = true;
        state.streaks.find = 0;
        renderScore();
        playWrong();
        btn.classList.remove('is-wrong');
        void btn.offsetWidth;
        btn.classList.add('is-wrong');
        if (findFeedback) findFeedback.textContent = 'Not that one';
    }

    function paintById(id) {
        return logic.PAINTS.find((paint) => paint.id === id) || null;
    }

    function paintPot(el, paint, label) {
        if (!el) return;
        if (!paint) {
            el.classList.add('is-empty');
            el.style.background = '';
            el.setAttribute('aria-label', label);
            return;
        }
        el.classList.remove('is-empty');
        el.style.background = paint.hex;
        el.setAttribute('aria-label', label + ': ' + paint.name);
    }

    function renderMix() {
        const a = paintById(state.mix.a);
        const b = paintById(state.mix.b);
        paintPot(potA, a, 'First colour');
        paintPot(potB, b, 'Second colour');
        if (potA) potA.classList.toggle('is-selected', state.mix.selected === 'a');
        if (potB) potB.classList.toggle('is-selected', state.mix.selected === 'b');
        if (!a || !b) {
            if (potResult) {
                potResult.classList.add('is-empty');
                potResult.style.background = '';
            }
            if (mixCaption) {
                mixCaption.textContent = !a && !b ? 'Tap a colour' : 'Now the other pot';
            }
            return;
        }
        const mixed = logic.mixPaints(a.id, b.id);
        if (potResult && mixed) {
            potResult.classList.remove('is-empty');
            potResult.style.background = mixed.hex;
        }
        if (mixCaption && mixed) mixCaption.textContent = mixed.caption;
    }

    function choosePaint(id) {
        const slot = state.mix.selected === 'b' ? 'b' : 'a';
        const changed = state.mix[slot] !== id;
        state.mix[slot] = id;
        if (slot === 'a' && !state.mix.b) state.mix.selected = 'b';
        else if (slot === 'b' && !state.mix.a) state.mix.selected = 'a';
        renderMix();
        const a = paintById(state.mix.a);
        const b = paintById(state.mix.b);
        if (changed && a && b) {
            const mixed = logic.mixPaints(a.id, b.id);
            if (mixed) {
                playRight();
                burstAt(mixed.hex);
                say(mixed.caption);
            }
        }
    }

    function buildPaintbox() {
        if (!paintbox || paintbox.childElementCount) return;
        logic.PAINTS.forEach((paint) => {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'play-paint';
            btn.style.background = paint.hex;
            btn.setAttribute('aria-label', paint.name);
            if (paint.id === 'white') btn.classList.add('is-white');
            btn.addEventListener('click', () => choosePaint(paint.id));
            paintbox.appendChild(btn);
        });
    }

    function showColourMode(mode) {
        state.colourMode = mode;
        saveBest();
        setModes('[data-colour-mode]', 'data-colour-mode', mode);
        if (findPanel) findPanel.hidden = mode !== 'find';
        if (mixPanel) mixPanel.hidden = mode !== 'mix';
        renderScore();
        if (mode === 'find') newFindRound();
        else {
            clearTimer();
            silence();
            renderMix();
        }
    }

    function notifyScreensaver() {
        if (window.ChoresScreensaver && typeof window.ChoresScreensaver.syncIdle === 'function') {
            window.ChoresScreensaver.syncIdle();
        }
    }

    function openPlay(game) {
        if (window.DashboardLayout && window.DashboardLayout.isArranging()) return;
        ensureAudio();
        showGame(game);
        overlay.hidden = false;
        document.body.classList.add('play-widget-open');
        if (game === 'maths') newMathsQuestion();
        else showColourMode(state.colourMode);
        if (closeBtn) closeBtn.focus();
        notifyScreensaver();
    }

    function closePlay() {
        clearTimer();
        silence();
        overlay.hidden = true;
        document.body.classList.remove('play-widget-open');
        notifyScreensaver();
    }

    function onKeyDown(e) {
        if (overlay.hidden) return;
        if (e.key === 'Escape') {
            e.preventDefault();
            closePlay();
            return;
        }
        if (state.game !== 'maths') return;
        if (e.key >= '0' && e.key <= '9') {
            e.preventDefault();
            pushDigit(e.key);
        } else if (e.key === 'Backspace') {
            e.preventDefault();
            backspace();
        } else if (e.key === 'Enter') {
            e.preventDefault();
            submitMaths();
        }
    }

    loadBest();
    buildKeypad();
    buildPaintbox();
    setModes('[data-maths-mode]', 'data-maths-mode', state.mathsMode);
    setModes('[data-colour-mode]', 'data-colour-mode', state.colourMode);

    if (openMathsBtn) openMathsBtn.addEventListener('click', (e) => { e.stopPropagation(); openPlay('maths'); });
    if (openColoursBtn) openColoursBtn.addEventListener('click', (e) => { e.stopPropagation(); openPlay('colours'); });
    if (closeBtn) closeBtn.addEventListener('click', closePlay);
    if (backdrop) backdrop.addEventListener('click', closePlay);
    document.addEventListener('keydown', onKeyDown);

    overlay.querySelectorAll('[data-maths-mode]').forEach((btn) => {
        btn.addEventListener('click', () => {
            const mode = btn.getAttribute('data-maths-mode');
            if (!mode || mode === state.mathsMode) return;
            state.mathsMode = mode;
            saveBest();
            setModes('[data-maths-mode]', 'data-maths-mode', mode);
            state.question = null;
            newMathsQuestion();
        });
    });

    overlay.querySelectorAll('[data-colour-mode]').forEach((btn) => {
        btn.addEventListener('click', () => {
            const mode = btn.getAttribute('data-colour-mode');
            if (!mode || mode === state.colourMode) return;
            showColourMode(mode);
        });
    });

    if (potA) {
        potA.addEventListener('click', () => {
            state.mix.selected = 'a';
            renderMix();
        });
    }
    if (potB) {
        potB.addEventListener('click', () => {
            state.mix.selected = 'b';
            renderMix();
        });
    }

    window.ChoresPlayWidget = {
        isOpen: () => !overlay.hidden
    };
})();
