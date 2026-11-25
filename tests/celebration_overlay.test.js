const assert = require('assert');
const Celebration = require('../static/js/celebration.js');

function memoryStorage() {
    const data = new Map();
    return {
        getItem(key) { return data.has(key) ? data.get(key) : null; },
        setItem(key, value) { data.set(key, String(value)); },
    };
}

function element(tag, parent) {
    return { tagName: tag, parentElement: parent || null, parent: parent || null };
}

const day = new Date(2026, 10, 25);

assert.strictEqual(Celebration.DISMISS_MS, 8000);
assert.strictEqual(Celebration.dayKey(day), '2026-11-25');
assert.strictEqual(Celebration.personKey(4, 'Dad'), 'id:4');
assert.strictEqual(Celebration.personKey('', 'Dad'), 'name:dad');

const store = memoryStorage();
const who = Celebration.personKey(4, 'Dad');
const today = Celebration.dayKey(day);
assert.strictEqual(Celebration.alreadyCelebrated(store, who, today), false);
Celebration.rememberCelebrated(store, who, today);
assert.strictEqual(Celebration.alreadyCelebrated(store, who, today), true);
assert.strictEqual(Celebration.alreadyCelebrated(store, who, '2026-11-26'), false);
assert.strictEqual(Celebration.alreadyCelebrated(store, Celebration.personKey(9, 'Mum'), today), false);

const button = element('BUTTON');
const label = element('SPAN', button);
const card = element('DIV');
const title = element('H1', card);
assert.strictEqual(Celebration.clickShouldDismiss(label), false);
assert.strictEqual(Celebration.clickShouldDismiss(button), false);
assert.strictEqual(Celebration.clickShouldDismiss(title), true);
assert.strictEqual(Celebration.clickShouldDismiss(card), true);

console.log('celebration overlay checks passed');
