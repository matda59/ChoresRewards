"""A blank saved slot must not hide a meal that repeats every week."""

import json
import uuid
from datetime import date, timedelta

from app import app, db
from models import AppSetting, Person
from routes import _merge_meal_plan_with_recurring


def _monday(day):
    return day - timedelta(days=day.weekday())


def _recurring_breakfast(weekday, meal):
    rules = {}
    rules[weekday] = {
        'breakfast': {'enabled': True, 'value': meal},
    }
    return rules


def test_blank_saved_slot_does_not_hide_the_weekly_meal():
    monday = date(2026, 9, 21)
    merged = _merge_meal_plan_with_recurring(
        {
            monday.isoformat(): {'breakfast': '', 'lunch': '', 'dinner': 'Tacos'},
        },
        _recurring_breakfast('monday', 'Porridge'),
        monday,
    )
    assert merged[monday.isoformat()]['breakfast'] == 'Porridge'
    assert merged[monday.isoformat()]['dinner'] == 'Tacos'
    assert merged[monday.isoformat()]['lunch'] == ''


def test_a_different_saved_meal_still_overrides_the_weekly_one():
    monday = date(2026, 9, 21)
    merged = _merge_meal_plan_with_recurring(
        {monday.isoformat(): {'breakfast': 'Toast'}},
        _recurring_breakfast('monday', 'Porridge'),
        monday,
    )
    assert merged[monday.isoformat()]['breakfast'] == 'Toast'


def test_save_keeps_the_weekly_meal_and_a_one_off():
    app.config['TESTING'] = True
    client = app.test_client()
    monday = date(2026, 9, 21)
    next_monday = monday + timedelta(days=7)
    with app.app_context():
        saved_plan = AppSetting.get('meal_planner_plan_json')
        saved_recurring = AppSetting.get('meal_planner_recurring_json')
        AppSetting.set('meal_planner_plan_json', json.dumps({
            next_monday.isoformat(): {'breakfast': '', 'lunch': '', 'dinner': ''},
        }))
        AppSetting.set('meal_planner_recurring_json', '{}')

    plan = {}
    for offset in range(7):
        day = (monday + timedelta(days=offset)).isoformat()
        plan[day] = {'breakfast': '', 'lunch': '', 'dinner': ''}
    plan[monday.isoformat()]['breakfast'] = 'Porridge'
    plan[monday.isoformat()]['dinner'] = 'Tacos'

    try:
        saved = client.post('/api/meal_planner', json={
            'week_start': monday.isoformat(),
            'plan': plan,
            'recurring': _recurring_breakfast('monday', 'Porridge'),
        })
        assert saved.status_code == 200
        body = saved.get_json()
        assert body['success'] is True
        assert body['plan'][monday.isoformat()]['breakfast'] == 'Porridge'
        assert body['plan'][monday.isoformat()]['dinner'] == 'Tacos'

        with app.app_context():
            stored = json.loads(AppSetting.get('meal_planner_plan_json'))
        assert 'breakfast' not in stored.get(monday.isoformat(), {})
        assert stored[monday.isoformat()]['dinner'] == 'Tacos'
        assert next_monday.isoformat() not in stored

        loaded = client.get('/api/meal_planner', query_string={'week_start': next_monday.isoformat()})
        assert loaded.status_code == 200
        next_plan = loaded.get_json()['plan']
        assert next_plan[next_monday.isoformat()]['breakfast'] == 'Porridge'
        assert next_plan[next_monday.isoformat()]['dinner'] == ''
    finally:
        with app.app_context():
            if saved_plan is None:
                row = AppSetting.query.filter_by(key='meal_planner_plan_json').first()
                if row:
                    db.session.delete(row)
            else:
                AppSetting.set('meal_planner_plan_json', saved_plan)
            if saved_recurring is None:
                row = AppSetting.query.filter_by(key='meal_planner_recurring_json').first()
                if row:
                    db.session.delete(row)
            else:
                AppSetting.set('meal_planner_recurring_json', saved_recurring)
            db.session.commit()


def _meals_card(html):
    marker = 'data-dash-id="meals"'
    marker_at = html.find(marker)
    assert marker_at != -1
    start = html.rfind('<div', 0, marker_at)
    next_tile = html.find('data-dash-id="', marker_at + len(marker))
    assert next_tile != -1
    end = html.rfind('<div', marker_at, next_tile)
    return html[start:end]


def test_glance_shows_weekly_breakfast_when_today_was_saved_blank():
    app.config['TESTING'] = True
    client = app.test_client()
    created_people = []
    today = date.today()
    weekday = ('monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday')[today.weekday()]
    with app.app_context():
        saved_plan = AppSetting.get('meal_planner_plan_json')
        saved_recurring = AppSetting.get('meal_planner_recurring_json')
        if Person.query.count() == 0:
            person = Person(name=f'Weekly Meal {uuid.uuid4().hex[:6]}', points=0, bonus_points=0)
            db.session.add(person)
            db.session.commit()
            created_people.append(person.id)
        AppSetting.set('meal_planner_plan_json', json.dumps({
            today.isoformat(): {'breakfast': '', 'lunch': '', 'dinner': ''},
        }))
        AppSetting.set('meal_planner_recurring_json', json.dumps(
            _recurring_breakfast(weekday, 'Porridge')
        ))

    try:
        html = client.get('/').get_data(as_text=True)
        card = _meals_card(html)
        assert 'Breakfast' in card
        assert 'Porridge' in card
        assert 'No meals planned for today yet.' not in card
    finally:
        with app.app_context():
            if saved_plan is None:
                row = AppSetting.query.filter_by(key='meal_planner_plan_json').first()
                if row:
                    db.session.delete(row)
            else:
                AppSetting.set('meal_planner_plan_json', saved_plan)
            if saved_recurring is None:
                row = AppSetting.query.filter_by(key='meal_planner_recurring_json').first()
                if row:
                    db.session.delete(row)
            else:
                AppSetting.set('meal_planner_recurring_json', saved_recurring)
            for person_id in created_people:
                person = db.session.get(Person, person_id)
                if person:
                    db.session.delete(person)
            db.session.commit()


def _slot_html(html, day_iso, meal):
    marker = f'data-day="{day_iso}" data-meal="{meal}"'
    at = html.find(marker)
    assert at != -1, marker
    start = html.rfind('<div', 0, at)
    nxt = html.find('class="meal-slot"', at + len(marker))
    end = nxt if nxt != -1 else at + 2500
    return html[start:end]


def test_one_off_breakfast_keeps_the_weekly_meal_on_later_weeks():
    app.config['TESTING'] = True
    client = app.test_client()
    monday = date(2026, 9, 21)
    next_monday = monday + timedelta(days=7)
    with app.app_context():
        saved_plan = AppSetting.get('meal_planner_plan_json')
        saved_recurring = AppSetting.get('meal_planner_recurring_json')
        AppSetting.set('meal_planner_plan_json', '{}')
        AppSetting.set('meal_planner_recurring_json', '{}')

    plan = {}
    for offset in range(7):
        day = (monday + timedelta(days=offset)).isoformat()
        plan[day] = {'breakfast': '', 'lunch': '', 'dinner': ''}
    plan[monday.isoformat()]['breakfast'] = 'Toast'

    try:
        saved = client.post('/api/meal_planner', json={
            'week_start': monday.isoformat(),
            'plan': plan,
            'recurring': _recurring_breakfast('monday', 'Porridge'),
        })
        assert saved.status_code == 200
        body = saved.get_json()
        assert body['plan'][monday.isoformat()]['breakfast'] == 'Toast'
        assert body['recurring']['monday']['breakfast']['value'] == 'Porridge'
        assert body['recurring']['monday']['breakfast']['enabled'] is True

        with app.app_context():
            stored = json.loads(AppSetting.get('meal_planner_plan_json'))
            stored_recurring = json.loads(AppSetting.get('meal_planner_recurring_json'))
        assert stored[monday.isoformat()]['breakfast'] == 'Toast'
        assert stored_recurring['monday']['breakfast']['value'] == 'Porridge'

        loaded = client.get('/api/meal_planner', query_string={'week_start': next_monday.isoformat()})
        assert loaded.get_json()['plan'][next_monday.isoformat()]['breakfast'] == 'Porridge'
    finally:
        with app.app_context():
            if saved_plan is None:
                row = AppSetting.query.filter_by(key='meal_planner_plan_json').first()
                if row:
                    db.session.delete(row)
            else:
                AppSetting.set('meal_planner_plan_json', saved_plan)
            if saved_recurring is None:
                row = AppSetting.query.filter_by(key='meal_planner_recurring_json').first()
                if row:
                    db.session.delete(row)
            else:
                AppSetting.set('meal_planner_recurring_json', saved_recurring)
            db.session.commit()


def test_one_off_slot_is_not_marked_as_the_weekly_meal():
    app.config['TESTING'] = True
    client = app.test_client()
    created_people = []
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    monday = week_start
    wednesday = week_start + timedelta(days=2)
    with app.app_context():
        saved_plan = AppSetting.get('meal_planner_plan_json')
        saved_recurring = AppSetting.get('meal_planner_recurring_json')
        if Person.query.count() == 0:
            person = Person(name=f'Weekly Meal {uuid.uuid4().hex[:6]}', points=0, bonus_points=0)
            db.session.add(person)
            db.session.commit()
            created_people.append(person.id)
        AppSetting.set('meal_planner_plan_json', json.dumps({
            monday.isoformat(): {'breakfast': 'Toast'},
        }))
        rules = _recurring_breakfast('monday', 'Porridge')
        rules['wednesday'] = {'breakfast': {'enabled': True, 'value': 'Porridge'}}
        AppSetting.set('meal_planner_recurring_json', json.dumps(rules))

    try:
        html = client.get('/').get_data(as_text=True)
        assert 'js/meal_plan_logic.js' in html
        monday_slot = _slot_html(html, monday.isoformat(), 'breakfast')
        assert 'value="Toast"' in monday_slot
        assert 'meal-recurring-badge hidden' in monday_slot
        assert 'meal-recurring-input" checked' not in monday_slot
        assert 'meal-picker-recurring" checked' not in monday_slot

        wednesday_slot = _slot_html(html, wednesday.isoformat(), 'breakfast')
        assert 'value="Porridge"' in wednesday_slot
        assert 'meal-recurring-badge hidden' not in wednesday_slot
        assert 'meal-recurring-input" checked' in wednesday_slot
        assert 'meal-picker-recurring" checked' in wednesday_slot
    finally:
        with app.app_context():
            if saved_plan is None:
                row = AppSetting.query.filter_by(key='meal_planner_plan_json').first()
                if row:
                    db.session.delete(row)
            else:
                AppSetting.set('meal_planner_plan_json', saved_plan)
            if saved_recurring is None:
                row = AppSetting.query.filter_by(key='meal_planner_recurring_json').first()
                if row:
                    db.session.delete(row)
            else:
                AppSetting.set('meal_planner_recurring_json', saved_recurring)
            for person_id in created_people:
                person = db.session.get(Person, person_id)
                if person:
                    db.session.delete(person)
            db.session.commit()
