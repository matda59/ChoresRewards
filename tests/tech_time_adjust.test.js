const assert = require('assert');
const Adjust = require('../static/js/tech_time_adjust.js');

function node(className, parent, attrs) {
    return {
        className: className || '',
        parentElement: parent || null,
        parent: parent || null,
        getAttribute(name) { return attrs && Object.prototype.hasOwnProperty.call(attrs, name) ? attrs[name] : null; },
    };
}

assert.deepStrictEqual(Adjust.parseMinuteDelta('15'), { ok: true, minutes: 15 });
assert.deepStrictEqual(Adjust.parseMinuteDelta(' -20 '), { ok: true, minutes: -20 });
assert.strictEqual(Adjust.parseMinuteDelta('0').ok, false);
assert.strictEqual(Adjust.parseMinuteDelta('1.5').ok, false);
assert.strictEqual(Adjust.parseMinuteDelta('').ok, false);
assert.strictEqual(Adjust.parseMinuteDelta('15min').ok, false);
assert.strictEqual(Adjust.parseMinuteDelta('100001').ok, false);

const button = node('admin-only adjust-tech-time-btn', null, {
    'data-person-id': '4',
    'data-person-name': "O'Brien",
});
const icon = node('fas fa-tv', button);
assert.strictEqual(Adjust.adjustButtonFrom(icon), button);
assert.strictEqual(Adjust.adjustButtonFrom(node('column', null)), null);
assert.deepStrictEqual(Adjust.personFromButton(button), { id: '4', name: "O'Brien" });
assert.strictEqual(Adjust.personFromButton(node('adjust-tech-time-btn', null, {})), null);

const updates = [];
const doc = {
    querySelectorAll(selector) {
        const match = selector.match(/\[data-tech-(minutes|balance)-for="(\d+)"\]/);
        if (!match) return [];
        return [{
            kind: match[1],
            id: match[2],
            textContent: '',
            set textContent(value) { updates.push(this.kind + ':' + this.id + ':' + value); },
        }];
    },
};
Adjust.applyBalance(doc, 4, 'Charlie', '2h 25m');
assert.deepStrictEqual(updates.sort(), [
    'balance:4:Charlie: 2h 25m',
    'minutes:4:2h 25m',
]);

console.log('tech_time_adjust.test.js ok');
