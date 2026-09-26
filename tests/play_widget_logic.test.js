const assert = require('assert');
const logic = require('../static/js/play_widget_logic.js');

function mulberry32(seed) {
    let value = seed >>> 0;
    return function rng() {
        value = (value + 0x6D2B79F5) >>> 0;
        let t = Math.imul(value ^ (value >>> 15), 1 | value);
        t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
}

function answerOf(prompt) {
    let match = prompt.match(/^\((\d+) × (\d+)\) \+ (\d+)$/);
    if (match) return Number(match[1]) * Number(match[2]) + Number(match[3]);
    match = prompt.match(/^\((\d+) × (\d+)\) − (\d+)$/);
    if (match) return Number(match[1]) * Number(match[2]) - Number(match[3]);
    match = prompt.match(/^(\d+) \+ (\d+)$/);
    if (match) return Number(match[1]) + Number(match[2]);
    match = prompt.match(/^(\d+) − (\d+)$/);
    if (match) return Number(match[1]) - Number(match[2]);
    match = prompt.match(/^(\d+) × (\d+)$/);
    if (match) return Number(match[1]) * Number(match[2]);
    match = prompt.match(/^(\d+) ÷ (\d+)$/);
    if (match) return Number(match[1]) / Number(match[2]);
    throw new Error('Unparsed prompt: ' + prompt);
}

function kindOf(prompt) {
    if (prompt.indexOf('(') === 0) return 'two';
    if (prompt.indexOf('÷') !== -1) return 'div';
    if (prompt.indexOf('×') !== -1) return 'times';
    if (prompt.indexOf('−') !== -1) return 'sub';
    if (prompt.indexOf('+') !== -1) return 'add';
    throw new Error('Unknown kind: ' + prompt);
}

['add', 'times', 'mix'].forEach((mode, index) => {
    const rng = mulberry32(1000 + index);
    let prev = '';
    const seen = {};
    for (let streak = 0; streak < 16; streak += 1) {
        for (let n = 0; n < 40; n += 1) {
            const question = logic.nextMathQuestion(mode, streak, rng, prev);
            const solved = answerOf(question.prompt);
            assert.strictEqual(question.answer, solved, question.prompt);
            assert.ok(Number.isInteger(question.answer), question.prompt);
            assert.ok(question.answer >= 0 && question.answer < 1000, question.prompt);
            assert.notStrictEqual(question.prompt, prev);
            const kind = kindOf(question.prompt);
            seen[kind] = true;
            if (mode === 'add') assert.ok(kind === 'add' || kind === 'sub', question.prompt);
            if (mode === 'times') assert.strictEqual(kind, 'times', question.prompt);
            if (mode === 'mix' && streak < 8) assert.notStrictEqual(kind, 'two', question.prompt);
            prev = question.prompt;
        }
    }
    if (mode === 'mix') {
        assert.ok(seen.add && seen.sub && seen.times && seen.div && seen.two);
    }
});

const paintIds = logic.PAINTS.map((paint) => paint.id);
paintIds.forEach((a) => {
    paintIds.forEach((b) => {
        const mixed = logic.mixPaints(a, b);
        const flipped = logic.mixPaints(b, a);
        assert.ok(mixed && mixed.name && mixed.hex && mixed.caption);
        assert.strictEqual(flipped.name, mixed.name);
        assert.strictEqual(flipped.hex, mixed.hex);
        if (a === b) assert.strictEqual(mixed.same, true);
    });
});
assert.strictEqual(logic.mixPaints('red', 'yellow').name, 'orange');
assert.strictEqual(logic.mixPaints('yellow', 'blue').name, 'green');
assert.strictEqual(logic.mixPaints('blue', 'red').name, 'purple');
assert.strictEqual(logic.mixPaints('red', 'white').name, 'pink');
assert.strictEqual(logic.mixPaints('black', 'white').name, 'grey');

for (let streak = 0; streak < 8; streak += 1) {
    const rng = mulberry32(50 + streak);
    for (let n = 0; n < 25; n += 1) {
        const round = logic.pickFindRound(streak, rng);
        assert.strictEqual(round.choices.length, 6);
        const colors = round.choices.map((choice) => choice.color.id);
        const shapes = round.choices.map((choice) => choice.shape);
        assert.strictEqual(new Set(colors).size, 6);
        assert.strictEqual(new Set(shapes).size, 6);
        assert.strictEqual(colors.filter((id) => id === round.target.id).length, 1);
        if (streak >= 3) {
            const near = logic.NEAR[round.target.id];
            assert.ok(colors.some((id) => near.indexOf(id) !== -1));
        }
    }
}

function followsPattern(round) {
    const sequence = round.sequence;
    if (round.kind === 'add' || round.kind === 'sub') {
        const step = sequence[1] - sequence[0];
        return sequence[2] - sequence[1] === step
            && sequence[3] - sequence[2] === step
            && round.answer - sequence[3] === step
            && round.answer >= 0;
    }
    if (round.kind === 'mul') {
        return sequence[1] / sequence[0] === round.step
            && sequence[2] / sequence[1] === round.step
            && sequence[3] / sequence[2] === round.step
            && round.answer / sequence[3] === round.step;
    }
    if (round.kind === 'square') {
        const roots = sequence.map((n) => Math.round(Math.sqrt(n)));
        return roots.every((root, index) => root * root === sequence[index])
            && roots[1] === roots[0] + 1
            && round.answer === (roots[3] + 1) * (roots[3] + 1);
    }
    return false;
}

for (let streak = 0; streak < 12; streak += 1) {
    const rng = mulberry32(400 + streak);
    let prev = '';
    const seen = {};
    for (let n = 0; n < 30; n += 1) {
        const round = logic.nextPattern(streak, rng, prev);
        assert.ok(followsPattern(round), JSON.stringify(round));
        assert.strictEqual(round.choices.length, 4);
        assert.strictEqual(new Set(round.choices).size, 4);
        assert.ok(round.choices.indexOf(round.answer) !== -1);
        assert.notStrictEqual(round.key, prev);
        seen[round.kind] = true;
        if (streak < 4) assert.notStrictEqual(round.kind, 'square');
        prev = round.key;
    }
    if (streak >= 8) assert.ok(seen.add && seen.mul);
}

for (let n = 0; n < 20; n += 1) {
    const round = logic.pickShapeRound(mulberry32(20 + n));
    const shapes = round.choices.map((choice) => choice.shape);
    assert.strictEqual(shapes.length, 6);
    assert.strictEqual(new Set(shapes).size, 6);
    assert.ok(shapes.indexOf(round.target) !== -1);
}

const memoryCards = { small: 8, medium: 12, high: 16 };
['colours', 'bonds'].forEach((mode) => {
    Object.keys(memoryCards).forEach((size) => {
        const deck = logic.memoryDeck(mode, size, mulberry32(7 + memoryCards[size]));
        assert.strictEqual(deck.length, memoryCards[size], mode + ' ' + size);
        const pairs = {};
        deck.forEach((card) => {
            pairs[card.pair] = pairs[card.pair] || [];
            pairs[card.pair].push(card);
            assert.ok(card.uid && card.label);
        });
        assert.strictEqual(Object.keys(pairs).length, memoryCards[size] / 2);
        Object.keys(pairs).forEach((pair) => {
            assert.strictEqual(pairs[pair].length, 2);
            if (mode === 'bonds') {
                assert.strictEqual(pairs[pair][0].value + pairs[pair][1].value, pairs[pair][0].sum);
            }
        });
        if (mode === 'colours') {
            const pictures = deck.map((card) => card.pair);
            assert.strictEqual(new Set(pictures).size, memoryCards[size] / 2);
        }
    });
});
const smallBonds = logic.memoryDeck('bonds', 'small', mulberry32(3));
assert.strictEqual(smallBonds[0].sum, 10);
assert.strictEqual(logic.memoryDeck('bonds', 'high', mulberry32(4))[0].sum, 20);
assert.strictEqual(logic.memoryDeck('colours', mulberry32(9)).length, 8);

console.log('play widget logic ok');
