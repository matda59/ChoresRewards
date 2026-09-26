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

console.log('play widget logic ok');
