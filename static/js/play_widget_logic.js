/* Pure helpers for the dashboard Play widget (maths + colour mixing). */
(function (root, factory) {
    const api = factory();
    if (typeof module === 'object' && module.exports) {
        module.exports = api;
    }
    if (root) root.PlayWidgetLogic = api;
})(typeof window !== 'undefined' ? window : this, function () {
    const PAINTS = [
        { id: 'red', name: 'red', hex: '#ef4444' },
        { id: 'yellow', name: 'yellow', hex: '#facc15' },
        { id: 'blue', name: 'blue', hex: '#3b82f6' },
        { id: 'white', name: 'white', hex: '#f8fafc' },
        { id: 'black', name: 'black', hex: '#111827' }
    ];

    const MIX_RESULTS = {
        'black+white': { id: 'grey', name: 'grey', hex: '#9ca3af' },
        'blue+red': { id: 'purple', name: 'purple', hex: '#a855f7' },
        'blue+white': { id: 'light-blue', name: 'light blue', hex: '#7dd3fc' },
        'black+blue': { id: 'dark-blue', name: 'dark blue', hex: '#1e3a8a' },
        'blue+yellow': { id: 'green', name: 'green', hex: '#22c55e' },
        'black+red': { id: 'dark-red', name: 'dark red', hex: '#7f1d1d' },
        'red+white': { id: 'pink', name: 'pink', hex: '#f9a8d4' },
        'red+yellow': { id: 'orange', name: 'orange', hex: '#f97316' },
        'black+yellow': { id: 'olive', name: 'olive', hex: '#a16207' },
        'white+yellow': { id: 'light-yellow', name: 'light yellow', hex: '#fef08a' }
    };

    const FIND_COLORS = [
        { id: 'red', name: 'red', hex: '#ef4444' },
        { id: 'orange', name: 'orange', hex: '#f97316' },
        { id: 'yellow', name: 'yellow', hex: '#eab308' },
        { id: 'green', name: 'green', hex: '#22c55e' },
        { id: 'blue', name: 'blue', hex: '#3b82f6' },
        { id: 'purple', name: 'purple', hex: '#a855f7' },
        { id: 'pink', name: 'pink', hex: '#f472b6' },
        { id: 'brown', name: 'brown', hex: '#92400e' },
        { id: 'black', name: 'black', hex: '#111827' },
        { id: 'white', name: 'white', hex: '#f8fafc' }
    ];

    const NEAR = {
        red: ['orange', 'pink'],
        orange: ['red', 'yellow'],
        yellow: ['orange', 'green'],
        green: ['yellow', 'blue'],
        blue: ['purple', 'green'],
        purple: ['blue', 'pink'],
        pink: ['red', 'purple'],
        brown: ['orange', 'black'],
        black: ['brown', 'purple'],
        white: ['yellow', 'pink']
    };

    const SHAPES = ['circle', 'square', 'star', 'heart', 'triangle', 'diamond'];

    function randInt(rng, min, max) {
        return min + Math.floor(rng() * (max - min + 1));
    }

    function pick(rng, items) {
        return items[randInt(rng, 0, items.length - 1)];
    }

    function shuffle(items, rng) {
        const copy = items.slice();
        for (let i = copy.length - 1; i > 0; i -= 1) {
            const j = randInt(rng, 0, i);
            const tmp = copy[i];
            copy[i] = copy[j];
            copy[j] = tmp;
        }
        return copy;
    }

    function capitalise(text) {
        if (!text) return '';
        return text.charAt(0).toUpperCase() + text.slice(1);
    }

    function makeAddSub(streak, rng, forced) {
        const hard = streak >= 6;
        const op = forced || (rng() < 0.5 ? 'add' : 'sub');
        if (op === 'add') {
            const lo = hard ? 14 : 8;
            const hi = hard ? 99 : 48;
            const a = randInt(rng, lo, hi);
            const b = randInt(rng, lo, hi);
            return { prompt: a + ' + ' + b, answer: a + b };
        }
        const a = randInt(rng, hard ? 24 : 12, hard ? 120 : 60);
        const b = randInt(rng, hard ? 8 : 4, a - 1);
        return { prompt: a + ' − ' + b, answer: a - b };
    }

    function makeTimes(streak, rng) {
        const easy = [2, 3, 4, 5, 10];
        const hard = [6, 7, 8, 9, 11, 12];
        const hardChance = streak >= 4 ? 0.7 : 0.45;
        const a = pick(rng, rng() < hardChance ? hard : easy);
        const b = randInt(rng, 2, 12);
        const x = rng() < 0.5 ? a : b;
        const y = x === a ? b : a;
        return { prompt: x + ' × ' + y, answer: x * y };
    }

    function makeDivision(rng) {
        const divisor = randInt(rng, 2, 12);
        const quotient = randInt(rng, 2, 12);
        return { prompt: (divisor * quotient) + ' ÷ ' + divisor, answer: quotient };
    }

    function makeTwoStep(rng) {
        const a = randInt(rng, 2, 9);
        const b = randInt(rng, 2, 9);
        const prod = a * b;
        if (rng() < 0.5) {
            const c = randInt(rng, 2, 24);
            return { prompt: '(' + a + ' × ' + b + ') + ' + c, answer: prod + c };
        }
        const c = randInt(rng, 1, Math.max(1, prod - 1));
        return { prompt: '(' + a + ' × ' + b + ') − ' + c, answer: prod - c };
    }

    function makeQuestion(mode, streak, rng) {
        if (mode === 'times') return makeTimes(streak, rng);
        if (mode === 'mix') {
            const bag = ['add', 'add', 'sub', 'times', 'times', 'div'];
            if (streak >= 8) bag.push('two', 'two');
            const kind = pick(rng, bag);
            if (kind === 'two') return makeTwoStep(rng);
            if (kind === 'times') return makeTimes(streak, rng);
            if (kind === 'div') return makeDivision(rng);
            return makeAddSub(streak, rng, kind === 'sub' ? 'sub' : 'add');
        }
        return makeAddSub(streak, rng, null);
    }

    function nextMathQuestion(mode, streak, rng, previousPrompt) {
        const random = typeof rng === 'function' ? rng : Math.random;
        const safeMode = mode === 'times' || mode === 'mix' ? mode : 'add';
        const safeStreak = Math.max(0, Number(streak) || 0);
        let question = makeQuestion(safeMode, safeStreak, random);
        for (let i = 0; i < 12 && previousPrompt && question.prompt === previousPrompt; i += 1) {
            question = makeQuestion(safeMode, safeStreak, random);
        }
        return question;
    }

    function mixPaints(idA, idB) {
        const a = PAINTS.find((paint) => paint.id === idA);
        const b = PAINTS.find((paint) => paint.id === idB);
        if (!a || !b) return null;
        if (a.id === b.id) {
            return {
                id: a.id,
                name: a.name,
                hex: a.hex,
                same: true,
                caption: capitalise(a.name) + ' and ' + a.name + ' is still ' + a.name + '!'
            };
        }
        const key = [a.id, b.id].sort().join('+');
        const result = MIX_RESULTS[key];
        if (!result) return null;
        return {
            id: result.id,
            name: result.name,
            hex: result.hex,
            same: false,
            caption: capitalise(a.name) + ' and ' + b.name + ' make ' + result.name + '!'
        };
    }

    function pickFindRound(streak, rng) {
        const random = typeof rng === 'function' ? rng : Math.random;
        const target = pick(random, FIND_COLORS);
        const others = FIND_COLORS.filter((color) => color.id !== target.id);
        const chosen = [];
        if ((Number(streak) || 0) >= 3) {
            const nearIds = NEAR[target.id] || [];
            const near = others.filter((color) => nearIds.indexOf(color.id) !== -1);
            if (near.length) chosen.push(pick(random, near));
        }
        const pool = shuffle(others.filter((color) => !chosen.some((item) => item.id === color.id)), random);
        while (chosen.length < 5 && pool.length) chosen.push(pool.pop());
        const colors = shuffle([target].concat(chosen), random);
        const shapes = shuffle(SHAPES, random);
        return {
            target: target,
            choices: colors.map((color, index) => ({ color: color, shape: shapes[index] }))
        };
    }

    function fillChoices(answer, preferred, rng) {
        const choices = [answer];
        preferred.forEach((n) => {
            if (choices.length >= 4) return;
            if (!Number.isInteger(n) || n < 0 || n > 999 || choices.indexOf(n) !== -1) return;
            choices.push(n);
        });
        let extra = 1;
        while (choices.length < 4 && extra < 40) {
            const n = answer + extra;
            extra += 1;
            if (n <= 999 && choices.indexOf(n) === -1) choices.push(n);
        }
        return shuffle(choices, rng);
    }

    function makeStepPattern(streak, rng, sign) {
        const steps = streak >= 6 ? [2, 3, 4, 5, 6, 8, 10] : [2, 3, 5, 10];
        const step = pick(rng, steps);
        const start = sign > 0
            ? randInt(rng, 1, streak >= 6 ? 24 : 12)
            : randInt(rng, step * 4 + 2, step * 4 + 24);
        const sequence = [0, 1, 2, 3].map((i) => start + sign * i * step);
        const answer = start + sign * 4 * step;
        return {
            sequence: sequence,
            answer: answer,
            choices: fillChoices(answer, [
                answer + step,
                answer - step,
                answer + sign * step * 2,
                sequence[3],
                answer + 1,
                answer - 1
            ], rng),
            kind: sign > 0 ? 'add' : 'sub',
            step: step,
            key: sequence.join(',')
        };
    }

    function makeMulPattern(streak, rng) {
        const factor = streak >= 6 && rng() < 0.35 ? 3 : 2;
        const start = randInt(rng, 1, factor === 2 ? 5 : 3);
        const sequence = [start];
        while (sequence.length < 4) sequence.push(sequence[sequence.length - 1] * factor);
        const answer = sequence[3] * factor;
        return {
            sequence: sequence,
            answer: answer,
            choices: fillChoices(answer, [
                answer + factor,
                answer - factor,
                sequence[3] + sequence[3],
                answer + start,
                sequence[3]
            ], rng),
            kind: 'mul',
            step: factor,
            key: sequence.join(',')
        };
    }

    function makeSquares(rng) {
        const start = randInt(rng, 1, 5);
        const sequence = [0, 1, 2, 3].map((i) => (start + i) * (start + i));
        const answer = (start + 4) * (start + 4);
        return {
            sequence: sequence,
            answer: answer,
            choices: fillChoices(answer, [
                answer + 1,
                answer - 1,
                (start + 5) * (start + 5),
                sequence[3] + (start + 3)
            ], rng),
            kind: 'square',
            step: start,
            key: sequence.join(',')
        };
    }

    function makePattern(streak, rng) {
        const bag = ['add', 'add', 'sub', 'mul'];
        if (streak >= 4) bag.push('square');
        if (streak >= 8) bag.push('mul', 'square');
        const kind = pick(rng, bag);
        if (kind === 'square') return makeSquares(rng);
        if (kind === 'mul') return makeMulPattern(streak, rng);
        if (kind === 'sub') return makeStepPattern(streak, rng, -1);
        return makeStepPattern(streak, rng, 1);
    }

    function nextPattern(streak, rng, previousKey) {
        const random = typeof rng === 'function' ? rng : Math.random;
        const safeStreak = Math.max(0, Number(streak) || 0);
        let round = makePattern(safeStreak, random);
        for (let i = 0; i < 12 && previousKey && round.key === previousKey; i += 1) {
            round = makePattern(safeStreak, random);
        }
        return round;
    }

    function pickShapeRound(rng) {
        const random = typeof rng === 'function' ? rng : Math.random;
        const shapes = shuffle(SHAPES, random);
        const colors = shuffle(FIND_COLORS, random).slice(0, shapes.length);
        const target = pick(random, shapes);
        return {
            target: target,
            choices: shapes.map((shape, index) => ({ shape: shape, color: colors[index] }))
        };
    }

    const MEMORY_PAIRS = [
        { id: 'red', name: 'red', hex: '#ef4444', shape: 'circle' },
        { id: 'yellow', name: 'yellow', hex: '#facc15', shape: 'star' },
        { id: 'blue', name: 'blue', hex: '#3b82f6', shape: 'heart' },
        { id: 'green', name: 'green', hex: '#22c55e', shape: 'square' }
    ];

    function memoryDeck(mode, rng) {
        const random = typeof rng === 'function' ? rng : Math.random;
        const cards = [];
        if (mode === 'bonds') {
            [[1, 9], [2, 8], [3, 7], [4, 6]].forEach((pair, index) => {
                pair.forEach((value, side) => {
                    cards.push({
                        uid: 'b' + index + '-' + side,
                        pair: String(index),
                        kind: 'bonds',
                        label: String(value),
                        value: value
                    });
                });
            });
        } else {
            MEMORY_PAIRS.forEach((paint) => {
                [0, 1].forEach((side) => {
                    cards.push({
                        uid: paint.id + '-' + side,
                        pair: paint.id,
                        kind: 'colours',
                        label: paint.name,
                        hex: paint.hex,
                        shape: paint.shape
                    });
                });
            });
        }
        return shuffle(cards, random);
    }

    return {
        PAINTS: PAINTS,
        FIND_COLORS: FIND_COLORS,
        NEAR: NEAR,
        SHAPES: SHAPES,
        nextMathQuestion: nextMathQuestion,
        mixPaints: mixPaints,
        pickFindRound: pickFindRound,
        nextPattern: nextPattern,
        pickShapeRound: pickShapeRound,
        memoryDeck: memoryDeck
    };
});
