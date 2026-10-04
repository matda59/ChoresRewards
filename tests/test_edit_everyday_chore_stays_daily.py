"""Editing an every-day chore must not turn it into a one-off.

The add form says to leave the day boxes unchecked for a chore that repeats
every day. Settings used to save that empty list as "not repeating", so
changing the title or the points stopped the morning reset from bringing it
back.
"""

import uuid

from app import app, db
from models import Chore, Person


def _edit(client, chore_id, assigned_to, **extra):
    payload = {
        'chore_id': chore_id,
        'title': extra.pop('title', 'Make the bed'),
        'assigned_to': assigned_to,
        'points': extra.pop('points', 2),
    }
    payload.update(extra)
    return client.post('/edit_chore', json=payload)


def test_editing_an_every_day_chore_keeps_it_repeating():
    app.config['TESTING'] = True
    client = app.test_client()
    suffix = uuid.uuid4().hex[:8]
    created = {'people': [], 'chores': []}

    with app.app_context():
        person = Person(name=f'Every Day {suffix}', points=0, bonus_points=0)
        db.session.add(person)
        db.session.commit()
        created['people'].append(person.id)
        chore = Chore(
            title='Make the bed',
            assigned_to=person.name,
            assigned_to_id=person.id,
            points=1,
            is_daily=True,
            days_of_week=None,
            completed=False,
            deleted=False,
        )
        db.session.add(chore)
        db.session.commit()
        created['chores'].append(chore.id)
        person_name = person.name
        chore_id = chore.id

    with client.session_transaction() as sess:
        sess['authenticated'] = True
        sess['adult_mode'] = True

    try:
        response = _edit(
            client,
            chore_id,
            person_name,
            title='Make the bed properly',
            points=3,
            days_of_week=[],
            is_daily=True,
        )
        body = response.get_json()
        assert response.status_code == 200
        assert body['success'] is True
        assert body['is_daily'] is True
        assert body['days_of_week'] == ''

        with app.app_context():
            chore = db.session.get(Chore, chore_id)
            assert chore.title == 'Make the bed properly'
            assert chore.points == 3
            assert chore.is_daily is True
            assert chore.days_of_week is None
    finally:
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


def test_turning_repeats_off_makes_the_chore_a_one_off():
    app.config['TESTING'] = True
    client = app.test_client()
    suffix = uuid.uuid4().hex[:8]
    created = {'people': [], 'chores': []}

    with app.app_context():
        person = Person(name=f'One Off {suffix}', points=0, bonus_points=0)
        db.session.add(person)
        db.session.commit()
        created['people'].append(person.id)
        chore = Chore(
            title='Wash the car',
            assigned_to=person.name,
            assigned_to_id=person.id,
            points=5,
            is_daily=True,
            days_of_week='saturday',
            completed=False,
            deleted=False,
        )
        db.session.add(chore)
        db.session.commit()
        created['chores'].append(chore.id)
        person_name = person.name
        chore_id = chore.id

    with client.session_transaction() as sess:
        sess['adult_mode'] = True

    try:
        response = _edit(
            client,
            chore_id,
            person_name,
            title='Wash the car',
            points=5,
            days_of_week=[],
            is_daily=False,
        )
        assert response.status_code == 200
        assert response.get_json()['is_daily'] is False
        with app.app_context():
            chore = db.session.get(Chore, chore_id)
            assert chore.is_daily is False
            assert chore.days_of_week is None
    finally:
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


def test_weekday_schedule_survives_an_edit():
    app.config['TESTING'] = True
    client = app.test_client()
    suffix = uuid.uuid4().hex[:8]
    created = {'people': [], 'chores': []}

    with app.app_context():
        person = Person(name=f'Weekday {suffix}', points=0, bonus_points=0)
        db.session.add(person)
        db.session.commit()
        created['people'].append(person.id)
        chore = Chore(
            title='Bins',
            assigned_to=person.name,
            assigned_to_id=person.id,
            points=1,
            is_daily=True,
            days_of_week='monday,thursday',
            completed=False,
            deleted=False,
        )
        db.session.add(chore)
        db.session.commit()
        created['chores'].append(chore.id)
        person_name = person.name
        chore_id = chore.id

    with client.session_transaction() as sess:
        sess['adult_mode'] = True

    try:
        response = _edit(
            client,
            chore_id,
            person_name,
            title='Take the bins out',
            points=2,
            days_of_week=['Monday', 'Thursday'],
            is_daily=True,
        )
        assert response.status_code == 200
        assert response.get_json()['days_of_week'] == 'monday,thursday'
        with app.app_context():
            chore = db.session.get(Chore, chore_id)
            assert chore.is_daily is True
            assert chore.days_of_week == 'monday,thursday'
            assert chore.title == 'Take the bins out'
    finally:
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
