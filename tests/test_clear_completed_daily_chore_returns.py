"""Clearing today's completed list must not erase a repeating chore.

Clear All used to send a permanent delete for every card. A daily chore
marked deleted never comes back. Skipping today should hide it until
tomorrow, and leave the points from today's completion alone.
"""

import uuid
from datetime import date, datetime, timedelta

from app import app, db
from models import Chore, Person


def _person(name):
    person = Person(name=name, points=4, bonus_points=0, is_admin=True)
    db.session.add(person)
    db.session.commit()
    return person


def _chore(person, title, is_daily, completed=True):
    today = date.today()
    chore = Chore(
        title=title,
        assigned_to=person.name,
        assigned_to_id=person.id,
        points=2,
        is_daily=is_daily,
        completed=completed,
        deleted=False,
        due_date=today,
        date_completed=datetime.combine(today, datetime.min.time().replace(hour=9)) if completed else None,
    )
    db.session.add(chore)
    db.session.commit()
    return chore


def _cleanup(person_id, chore_ids):
    with app.app_context():
        for chore_id in chore_ids:
            chore = db.session.get(Chore, chore_id)
            if chore:
                db.session.delete(chore)
        person = db.session.get(Person, person_id)
        if person:
            db.session.delete(person)
        db.session.commit()


def test_skipping_a_finished_daily_chore_brings_it_back_tomorrow():
    app.config['TESTING'] = True
    client = app.test_client()
    suffix = uuid.uuid4().hex[:8]
    with app.app_context():
        person = _person(f'Clear Daily {suffix}')
        chore = _chore(person, f'Make the bed {suffix}', is_daily=True)
        person_id, chore_id = person.id, chore.id
        points_before = person.points
    try:
        with client.session_transaction() as sess:
            sess['authenticated'] = True
            sess['adult_mode'] = True
        response = client.post('/delete_chore', json={'chore_id': chore_id, 'permanent': False})
        assert response.status_code == 200
        assert response.get_json()['success'] is True
        with app.app_context():
            saved = db.session.get(Chore, chore_id)
            person = db.session.get(Person, person_id)
            assert saved.deleted is False
            assert saved.completed is False
            assert saved.due_date == date.today() + timedelta(days=1)
            assert person.points == points_before
    finally:
        _cleanup(person_id, [chore_id])


def test_permanent_delete_still_removes_a_daily_chore():
    app.config['TESTING'] = True
    client = app.test_client()
    suffix = uuid.uuid4().hex[:8]
    with app.app_context():
        person = _person(f'Clear Permanent {suffix}')
        chore = _chore(person, f'Walk the dog {suffix}', is_daily=True)
        person_id, chore_id = person.id, chore.id
    try:
        with client.session_transaction() as sess:
            sess['authenticated'] = True
            sess['adult_mode'] = True
        response = client.post('/delete_chore', json={'chore_id': chore_id, 'permanent': True})
        assert response.status_code == 200
        with app.app_context():
            assert db.session.get(Chore, chore_id).deleted is True
    finally:
        _cleanup(person_id, [chore_id])


def test_skipping_an_open_daily_chore_does_not_mark_it_done():
    app.config['TESTING'] = True
    client = app.test_client()
    suffix = uuid.uuid4().hex[:8]
    with app.app_context():
        person = _person(f'Clear Open {suffix}')
        chore = _chore(person, f'Feed the cat {suffix}', is_daily=True, completed=False)
        person_id, chore_id = person.id, chore.id
    try:
        with client.session_transaction() as sess:
            sess['authenticated'] = True
            sess['adult_mode'] = True
        response = client.post('/delete_chore', json={'chore_id': chore_id, 'permanent': False})
        assert response.status_code == 200
        with app.app_context():
            saved = db.session.get(Chore, chore_id)
            assert saved.deleted is False
            assert saved.completed is False
            assert saved.due_date == date.today() + timedelta(days=1)
    finally:
        _cleanup(person_id, [chore_id])


def test_child_cannot_clear_a_finished_daily_chore():
    app.config['TESTING'] = True
    client = app.test_client()
    suffix = uuid.uuid4().hex[:8]
    with app.app_context():
        person = _person(f'Clear Kid {suffix}')
        chore = _chore(person, f'Set the table {suffix}', is_daily=True)
        person_id, chore_id = person.id, chore.id
    try:
        with client.session_transaction() as sess:
            sess['authenticated'] = True
            sess['adult_mode'] = False
        response = client.post('/delete_chore', json={'chore_id': chore_id, 'permanent': False})
        assert response.status_code == 403
        with app.app_context():
            saved = db.session.get(Chore, chore_id)
            assert saved.deleted is False
            assert saved.completed is True
            assert saved.due_date == date.today()
    finally:
        _cleanup(person_id, [chore_id])


def test_clearing_a_one_off_chore_removes_it():
    app.config['TESTING'] = True
    client = app.test_client()
    suffix = uuid.uuid4().hex[:8]
    with app.app_context():
        person = _person(f'Clear Once {suffix}')
        chore = _chore(person, f'Wash the car {suffix}', is_daily=False)
        person_id, chore_id = person.id, chore.id
    try:
        with client.session_transaction() as sess:
            sess['authenticated'] = True
            sess['adult_mode'] = True
        response = client.post('/delete_chore', json={'chore_id': chore_id, 'permanent': True})
        assert response.status_code == 200
        with app.app_context():
            assert db.session.get(Chore, chore_id) is None
    finally:
        _cleanup(person_id, [chore_id])


def test_clear_all_keeps_repeating_chores_and_is_hidden_from_kids():
    app.config['TESTING'] = True
    client = app.test_client()
    suffix = uuid.uuid4().hex[:8]
    title = f'Pack lunch {suffix}'
    with app.app_context():
        person = _person(f'Clear Page {suffix}')
        chore = _chore(person, title, is_daily=True)
        person_id, chore_id = person.id, chore.id
    try:
        html = client.get('/').get_data(as_text=True)
        marker = f'data-chore-id="{chore_id}"'
        assert marker in html
        card_at = html.find(marker)
        card = html[card_at:card_at + 220]
        assert 'data-is-daily="true"' in card
        assert 'class="chore completed"' in html[card_at - 80:card_at + 40]
        start = html.find('function clearAllCompletedChores')
        assert start != -1
        body = html[start:html.find('\nfunction ', start + 10)]
        assert 'permanent: !chore.isDaily' in body
        assert 'permanent: true' not in body
        assert 'isAdultMode' in body
        assert 'clear-all-completed-btn admin-only' in html
        assert title in html
    finally:
        _cleanup(person_id, [chore_id])
