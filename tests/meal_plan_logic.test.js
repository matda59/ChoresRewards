const assert = require('assert');
const logic = require('../static/js/meal_plan_logic.js');

function porridgeRule() {
    return {
        monday: {
            breakfast: { enabled: true, value: 'Porridge' }
        }
    };
}

function monday(value, weeklyChecked, stopWeekly) {
    return {
        weekday: 'monday',
        meal: 'breakfast',
        value: value,
        weeklyChecked: !!weeklyChecked,
        stopWeekly: !!stopWeekly
    };
}

const kept = logic.collectRecurringFromSlots(porridgeRule(), [monday('Toast', false)]);
assert.strictEqual(kept.monday.breakfast.enabled, true);
assert.strictEqual(kept.monday.breakfast.value, 'Porridge');

const renamed = logic.collectRecurringFromSlots(porridgeRule(), [monday('Oats', true)]);
assert.strictEqual(renamed.monday.breakfast.enabled, true);
assert.strictEqual(renamed.monday.breakfast.value, 'Oats');

const stopped = logic.collectRecurringFromSlots(porridgeRule(), [monday('Porridge', false)]);
assert.strictEqual(stopped.monday.breakfast.enabled, false);
assert.strictEqual(stopped.monday.breakfast.value, '');

const clearedOneOff = logic.collectRecurringFromSlots(porridgeRule(), [monday('', false)]);
assert.strictEqual(clearedOneOff.monday.breakfast.enabled, true);
assert.strictEqual(clearedOneOff.monday.breakfast.value, 'Porridge');

const clearedStaple = logic.collectRecurringFromSlots(porridgeRule(), [monday('', false, true)]);
assert.strictEqual(clearedStaple.monday.breakfast.enabled, false);

const swapped = logic.collectRecurringFromSlots(porridgeRule(), [
    monday('Toast', false),
    { weekday: 'tuesday', meal: 'dinner', value: 'Porridge', weeklyChecked: false }
]);
assert.strictEqual(swapped.monday.breakfast.value, 'Porridge');
assert.strictEqual(swapped.monday.breakfast.enabled, true);
assert.strictEqual(swapped.tuesday.dinner.enabled, false);

assert.strictEqual(logic.slotIsWeeklyMeal('Toast', porridgeRule().monday.breakfast), false);
assert.strictEqual(logic.slotIsWeeklyMeal('porridge', porridgeRule().monday.breakfast), true);
assert.strictEqual(logic.slotIsWeeklyMeal('', porridgeRule().monday.breakfast), false);
assert.strictEqual(logic.slotIsWeeklyMeal('Porridge', { enabled: false, value: 'Porridge' }), false);

console.log('meal_plan_logic.test.js ok');
