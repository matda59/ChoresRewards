"""Completing a chore with a due time must succeed and must not corrupt points."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app import app, db
from models import Chore, Person, AppSetting


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.app_context():
        AppSetting.set('timezone', 'UTC')
    test_client = app.test_client()
    created = {'people': [], 'chores': []}

    def add_person(points=0):
        with app.app_context():
            person = Person(
                name=f'Test Kid {uuid.uuid4().hex[:8]}',
                points=points,
                bonus_points=0,
            )
            db.session.add(person)
            db.session.commit()
            created['people'].append(person.id)
            return person.id, person.name

    def add_chore(person_id, person_name, points=5, due_datetime=None, due_date=None):
        with app.app_context():
            chore = Chore(
                title='Homework',
                assigned_to=person_name,
                assigned_to_id=person_id,
                points=points,
                is_daily=False,
                completed=False,
                due_date=due_date,
                due_datetime=due_datetime,
            )
            db.session.add(chore)
            db.session.commit()
            created['chores'].append(chore.id)
            return chore.id

    test_client.add_person = add_person
    test_client.add_chore = add_chore

    with test_client.session_transaction() as sess:
        sess['authenticated'] = True

    yield test_client

    with app.app_context():
        for chore_id in created['chores']:
            chore = db.session.get(Chore, chore_id)
            if chore:
                db.session.delete(chore)
        for person_id in created['people']:
            person = db.session.get(Person, person_id)
            if person:
                db.session.delete(person)
        db.session.commit()


def _points(person_id):
    with app.app_context():
        person = db.session.get(Person, person_id)
        return person.points


def _completed(chore_id):
    with app.app_context():
        chore = db.session.get(Chore, chore_id)
        return chore.completed


def test_future_due_datetime_completes_and_awards_points(client):
    person_id, name = client.add_person()
    due = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=2)
    chore_id = client.add_chore(person_id, name, due_datetime=due, due_date=due.date())

    resp = client.post('/complete_chore', json={'chore_id': chore_id})
    body = resp.get_json()

    assert resp.status_code == 200
    assert body['success'] is True
    assert body['overdue'] is False
    assert body['points_awarded'] == 5
    assert _completed(chore_id) is True
    assert _points(person_id) == 5


def test_past_due_datetime_completes_without_points(client):
    person_id, name = client.add_person(points=10)
    due = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=2)
    chore_id = client.add_chore(person_id, name, due_datetime=due, due_date=due.date())

    resp = client.post('/complete_chore', json={'chore_id': chore_id})
    body = resp.get_json()

    assert resp.status_code == 200
    assert body['success'] is True
    assert body['overdue'] is True
    assert body['points_awarded'] == 0
    assert _completed(chore_id) is True
    assert _points(person_id) == 10


def test_undo_overdue_completion_does_not_deduct_points(client):
    person_id, name = client.add_person(points=10)
    due = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=2)
    chore_id = client.add_chore(person_id, name, due_datetime=due, due_date=due.date())

    complete = client.post('/complete_chore', json={'chore_id': chore_id})
    assert complete.status_code == 200
    assert complete.get_json()['overdue'] is True

    undo = client.post('/undo_complete_chore', json={'chore_id': chore_id})
    body = undo.get_json()

    assert undo.status_code == 200
    assert body['success'] is True
    assert _completed(chore_id) is False
    assert _points(person_id) == 10


def test_undo_on_time_completion_deducts_awarded_points(client):
    person_id, name = client.add_person()
    due = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=2)
    chore_id = client.add_chore(person_id, name, due_datetime=due, due_date=due.date())

    complete = client.post('/complete_chore', json={'chore_id': chore_id})
    assert complete.status_code == 200
    assert _points(person_id) == 5

    undo = client.post('/undo_complete_chore', json={'chore_id': chore_id})

    assert undo.status_code == 200
    assert undo.get_json()['success'] is True
    assert _completed(chore_id) is False
    assert _points(person_id) == 0


def test_chore_without_deadline_still_awards_points(client):
    person_id, name = client.add_person()
    chore_id = client.add_chore(person_id, name)

    resp = client.post('/complete_chore', json={'chore_id': chore_id})

    assert resp.status_code == 200
    assert resp.get_json()['success'] is True
    assert resp.get_json()['overdue'] is False
    assert _points(person_id) == 5
