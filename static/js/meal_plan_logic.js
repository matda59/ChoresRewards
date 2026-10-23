/* Weekly meals stay on their weekday. A different meal on one date is a one-off. */
(function (root, factory) {
    const api = factory();
    if (typeof module === 'object' && module.exports) {
        module.exports = api;
    }
    if (root) root.MealPlanLogic = api;
})(typeof window !== 'undefined' ? window : this, function () {
    const DAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'];
    const MEALS = ['breakfast', 'lunch', 'dinner'];

    function normalizeMealText(value) {
        return String(value || '').trim();
    }

    function mealTextsMatch(a, b) {
        return normalizeMealText(a).toLowerCase() === normalizeMealText(b).toLowerCase();
    }

    function emptyRecurring() {
        const out = {};
        DAYS.forEach(function (day) {
            out[day] = {};
            MEALS.forEach(function (meal) {
                out[day][meal] = { enabled: false, value: '' };
            });
        });
        return out;
    }

    function cloneRecurring(rules) {
        const out = emptyRecurring();
        DAYS.forEach(function (day) {
            const source = rules && rules[day];
            if (!source || typeof source !== 'object') return;
            MEALS.forEach(function (meal) {
                const prev = source[meal];
                if (!prev || typeof prev !== 'object') return;
                const value = normalizeMealText(prev.value);
                out[day][meal] = { enabled: !!(prev.enabled && value), value: value };
            });
        });
        return out;
    }

    function slotIsWeeklyMeal(value, rule) {
        const text = normalizeMealText(value);
        if (!rule || !rule.enabled || !text) return false;
        return mealTextsMatch(text, rule.value);
    }

    // slots: { weekday, meal, value, weeklyChecked, stopWeekly }
    // weeklyChecked is the Weekly box for this date.
    // stopWeekly is set only when that date's meal is the repeating one and it is cleared.
    function collectRecurringFromSlots(existingRules, slots) {
        const out = cloneRecurring(existingRules);
        (slots || []).forEach(function (slot) {
            if (!slot) return;
            const day = slot.weekday;
            const meal = slot.meal;
            if (!out[day] || !out[day][meal]) return;
            const value = normalizeMealText(slot.value);
            const prev = out[day][meal];
            if (slot.stopWeekly) {
                out[day][meal] = { enabled: false, value: '' };
                return;
            }
            if (slot.weeklyChecked && value) {
                out[day][meal] = { enabled: true, value: value };
                return;
            }
            const same = !!(prev.enabled && prev.value && mealTextsMatch(value, prev.value));
            if (!slot.weeklyChecked && prev.enabled && prev.value && !same) {
                out[day][meal] = { enabled: true, value: prev.value };
                return;
            }
            if (!slot.weeklyChecked && same) {
                out[day][meal] = { enabled: false, value: '' };
                return;
            }
            out[day][meal] = { enabled: false, value: value };
        });
        return out;
    }

    return {
        normalizeMealText: normalizeMealText,
        mealTextsMatch: mealTextsMatch,
        slotIsWeeklyMeal: slotIsWeeklyMeal,
        collectRecurringFromSlots: collectRecurringFromSlots
    };
});
