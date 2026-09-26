"""Today at a Glance should list breakfast with lunch and dinner."""

import json
import uuid
from datetime import date

from app import app, db
from models import AppSetting, Person


def _meals_card(html):
    marker = 'data-dash-id="meals"'
    marker_at = html.find(marker)
    assert marker_at != -1
    start = html.rfind('<div', 0, marker_at)
    next_tile = html.find('data-dash-id="', marker_at + len(marker))
    assert next_tile != -1
    end = html.rfind('<div', marker_at, next_tile)
    return html[start:end]


def test_glance_shows_breakfast_and_hides_the_empty_hint_when_only_breakfast_is_planned():
    app.config['TESTING'] = True
    client = app.test_client()
    created_people = []
    today = date.today().isoformat()
    with app.app_context():
        saved_plan = AppSetting.get('meal_planner_plan_json')
        saved_recurring = AppSetting.get('meal_planner_recurring_json')
        if Person.query.count() == 0:
            person = Person(name=f'Meal Glance {uuid.uuid4().hex[:6]}', points=0, bonus_points=0)
            db.session.add(person)
            db.session.commit()
            created_people.append(person.id)
        AppSetting.set('meal_planner_recurring_json', '{}')
        AppSetting.set('meal_planner_plan_json', json.dumps({
            today: {'breakfast': 'Porridge', 'lunch': '', 'dinner': ''},
        }))

    try:
        html = client.get('/').get_data(as_text=True)
        card = _meals_card(html)
        assert 'Breakfast' in card
        assert 'Porridge' in card
        assert 'No meals planned for today yet.' not in card
        assert '>Lunch</span>' not in card
        assert '>Dinner</span>' not in card
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


def test_glance_lists_breakfast_lunch_and_dinner():
    app.config['TESTING'] = True
    client = app.test_client()
    created_people = []
    today = date.today().isoformat()
    with app.app_context():
        saved_plan = AppSetting.get('meal_planner_plan_json')
        saved_recurring = AppSetting.get('meal_planner_recurring_json')
        if Person.query.count() == 0:
            person = Person(name=f'Meal Glance {uuid.uuid4().hex[:6]}', points=0, bonus_points=0)
            db.session.add(person)
            db.session.commit()
            created_people.append(person.id)
        AppSetting.set('meal_planner_recurring_json', '{}')
        AppSetting.set('meal_planner_plan_json', json.dumps({
            today: {'breakfast': 'Porridge', 'lunch': 'Sandwiches', 'dinner': 'Tacos'},
        }))

    try:
        html = client.get('/').get_data(as_text=True)
        card = _meals_card(html)
        assert 'Breakfast' in card and 'Porridge' in card
        assert 'Lunch' in card and 'Sandwiches' in card
        assert 'Dinner' in card and 'Tacos' in card
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


def test_glance_keeps_the_empty_hint_when_today_has_no_meals():
    app.config['TESTING'] = True
    client = app.test_client()
    created_people = []
    today = date.today().isoformat()
    with app.app_context():
        saved_plan = AppSetting.get('meal_planner_plan_json')
        saved_recurring = AppSetting.get('meal_planner_recurring_json')
        if Person.query.count() == 0:
            person = Person(name=f'Meal Glance {uuid.uuid4().hex[:6]}', points=0, bonus_points=0)
            db.session.add(person)
            db.session.commit()
            created_people.append(person.id)
        AppSetting.set('meal_planner_recurring_json', '{}')
        AppSetting.set('meal_planner_plan_json', json.dumps({
            today: {'breakfast': '', 'lunch': '', 'dinner': ''},
        }))

    try:
        html = client.get('/').get_data(as_text=True)
        card = _meals_card(html)
        assert 'No meals planned for today yet.' in card
        assert '>Breakfast</span>' not in card
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
