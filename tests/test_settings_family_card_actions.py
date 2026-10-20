"""Family-card actions on Settings must not submit Save Ages.

Set PIN, Change Points, and Delete Person live inside the ages form.
A button without type="button" submits that form, so the page reloads
and the PIN, balance, or person is left unchanged. Change Points also
has to keep cents, because cash mode uses them.
"""

import uuid

from app import app, db
from models import ActivityLog, Person


def _adult_client():
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['adult_mode'] = True
    return client


def _person(name, points=0, bonus=0, is_admin=False):
    person = Person(
        name=name,
        points=points,
        bonus_points=bonus,
        is_admin=is_admin,
    )
    db.session.add(person)
    db.session.commit()
    return person


def _cleanup(person_ids, suffix):
    with app.app_context():
        for person_id in person_ids:
            person = db.session.get(Person, person_id)
            if person:
                db.session.delete(person)
        ActivityLog.query.filter(ActivityLog.description.contains(suffix)).delete(synchronize_session=False)
        db.session.commit()


def test_family_card_actions_do_not_submit_the_ages_form():
    app.config['TESTING'] = True
    client = _adult_client()
    suffix = uuid.uuid4().hex[:8]
    with app.app_context():
        person = _person('Card {}'.format(suffix), is_admin=True)
        person_id = person.id
    try:
        page = client.get('/settings')
        assert page.status_code == 200
        html = page.get_data(as_text=True)
        assert 'type="button" class="reset-points-btn"' in html
        assert 'type="button" class="delete-person-btn"' in html
        assert 'type="button" onclick="setPersonPin({})"'.format(person_id) in html
        assert "event.preventDefault(); setPersonPin({})".format(person_id) in html
        assert '<button class="reset-points-btn"' not in html
        assert '<button class="delete-person-btn"' not in html
        assert '<button onclick="setPersonPin(' not in html
        assert '/static/js/toast.js' in html
    finally:
        _cleanup([person_id], suffix)


def test_change_points_keeps_cents_and_clears_bonus():
    app.config['TESTING'] = True
    client = _adult_client()
    suffix = uuid.uuid4().hex[:8]
    with app.app_context():
        person = _person('Cents {}'.format(suffix), points=10, bonus=1.25)
        person_id = person.id
    try:
        saved = client.post('/reset_points', json={'person_id': person_id, 'new_points': 2.5})
        assert saved.status_code == 200
        body = saved.get_json()
        assert body['success'] is True
        assert body['new_points'] == 2.5
        with app.app_context():
            person = db.session.get(Person, person_id)
            assert person.points == 2.5
            assert person.bonus_points == 0

        rejected = client.post('/reset_points', json={'person_id': person_id, 'new_points': -1})
        assert rejected.status_code == 400
        assert rejected.get_json()['error'] == 'Points cannot be negative'
        nonsense = client.post('/reset_points', json={'person_id': person_id, 'new_points': 'abc'})
        assert nonsense.status_code == 400
        with app.app_context():
            assert db.session.get(Person, person_id).points == 2.5
    finally:
        _cleanup([person_id], suffix)


def test_child_session_cannot_change_points():
    app.config['TESTING'] = True
    client = app.test_client()
    suffix = uuid.uuid4().hex[:8]
    with app.app_context():
        person = _person('Locked {}'.format(suffix), points=4)
        person_id = person.id
    try:
        with client.session_transaction() as sess:
            sess['authenticated'] = True
            sess['adult_mode'] = False
        denied = client.post('/reset_points', json={'person_id': person_id, 'new_points': 0})
        assert denied.status_code == 403
        with app.app_context():
            assert db.session.get(Person, person_id).points == 4
    finally:
        _cleanup([person_id], suffix)


def test_save_ages_still_saves_from_the_family_cards():
    app.config['TESTING'] = True
    client = _adult_client()
    suffix = uuid.uuid4().hex[:8]
    with app.app_context():
        person = _person('Age {}'.format(suffix))
        person_id = person.id
    try:
        saved = client.post('/settings', data={
            'save_ages': '1',
            'person_age_{}'.format(person_id): '9',
        })
        assert saved.status_code == 200
        assert 'name="person_age_{}"'.format(person_id) in saved.get_data(as_text=True)
        assert 'value="9"' in saved.get_data(as_text=True)
        with app.app_context():
            assert db.session.get(Person, person_id).age == 9
    finally:
        _cleanup([person_id], suffix)
