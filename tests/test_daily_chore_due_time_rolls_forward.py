"""A repeating chore with a due time must pay points again the next day.

The morning reset brings the chore back, but it used to leave due_datetime on
the original day. Completing it the next morning was then after that deadline,
so the chore was saved as overdue and awarded nothing.
"""

import uuid
from datetime import datetime, time, timedelta, timezone

import pytest

from app import app, db
from models import AppSetting, Chore, Person
from routes import reset_daily_chores


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.app_context():
        saved_timezone = AppSetting.get('timezone')
        saved_gotify = AppSetting.get('gotify_notify_due_chores_expired')
        AppSetting.set('timezone', 'UTC')
        AppSetting.set('gotify_notify_due_chores_expired', 'false')
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

    def add_chore(person_id, person_name, **fields):
        with app.app_context():
            chore = Chore(
                title='Make bed',
                assigned_to=person_name,
                assigned_to_id=person_id,
                points=5,
                deleted=False,
                **fields,
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
        if saved_timezone is None:
            row = AppSetting.query.filter_by(key='timezone').first()
            if row:
                db.session.delete(row)
        else:
            AppSetting.set('timezone', saved_timezone)
        if saved_gotify is None:
            row = AppSetting.query.filter_by(key='gotify_notify_due_chores_expired').first()
            if row:
                db.session.delete(row)
        else:
            AppSetting.set('gotify_notify_due_chores_expired', saved_gotify)
        db.session.commit()


def _future_clock():
    """A clock time later today, so today's deadline has not passed yet."""
    now = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
    later = now + timedelta(hours=2)
    if later.date() != now.date():
        later = datetime.combine(now.date(), time(23, 59, 59))
    if later <= now:
        pytest.skip('too close to midnight to place a deadline later today')
    return later.time().replace(microsecond=0)


def _snapshot_other_daily(chore_ids):
    rows = []
    for chore in Chore.query.filter_by(is_daily=True, deleted=False).all():
        if chore.id in chore_ids:
            continue
        rows.append((
            chore.id,
            chore.completed,
            chore.due_date,
            chore.due_datetime,
            chore.date_completed,
        ))
    return rows


def _restore_other_daily(rows):
    for chore_id, completed, due_date, due_datetime, date_completed in rows:
        chore = db.session.get(Chore, chore_id)
        if chore is None:
            continue
        chore.completed = completed
        chore.due_date = due_date
        chore.due_datetime = due_datetime
        chore.date_completed = date_completed
    db.session.commit()


def _run_reset(own_ids):
    with app.app_context():
        snapshot = _snapshot_other_daily(set(own_ids))
        reset_daily_chores()
        _restore_other_daily(snapshot)


def test_next_day_completion_before_the_due_time_awards_points(client):
    person_id, name = client.add_person()
    clock = _future_clock()
    yesterday = datetime.now(timezone.utc).date() - timedelta(days=1)
    stale_due = datetime.combine(yesterday, clock)
    chore_id = client.add_chore(
        person_id,
        name,
        is_daily=True,
        completed=True,
        due_date=yesterday,
        due_datetime=stale_due,
    )

    _run_reset([chore_id])

    with app.app_context():
        chore = db.session.get(Chore, chore_id)
        assert chore.completed is False
        assert chore.due_date == datetime.now(timezone.utc).date()
        assert chore.due_datetime == datetime.combine(chore.due_date, clock)

    resp = client.post('/complete_chore', json={'chore_id': chore_id})
    body = resp.get_json()

    assert resp.status_code == 200
    assert body['success'] is True
    assert body['overdue'] is False
    assert body['points_awarded'] == 5
    with app.app_context():
        assert db.session.get(Person, person_id).points == 5


def test_due_time_rolls_forward_when_the_day_was_already_reset(client):
    """Opening the app today already moved due_date. The due time must follow."""
    person_id, name = client.add_person()
    clock = _future_clock()
    today = datetime.now(timezone.utc).date()
    yesterday = today - timedelta(days=1)
    chore_id = client.add_chore(
        person_id,
        name,
        is_daily=True,
        completed=False,
        due_date=today,
        due_datetime=datetime.combine(yesterday, clock),
    )

    _run_reset([chore_id])

    resp = client.post('/complete_chore', json={'chore_id': chore_id})
    body = resp.get_json()

    assert resp.status_code == 200
    assert body['overdue'] is False
    assert body['points_awarded'] == 5
    with app.app_context():
        chore = db.session.get(Chore, chore_id)
        assert chore.due_datetime == datetime.combine(today, clock)
        assert db.session.get(Person, person_id).points == 5


def test_undo_after_reset_does_not_take_points_from_an_unpaid_completion(client):
    """A finished chore must keep the deadline it was judged against.

    The morning reset used to move due_datetime onto today even when the chore
    was already completed. Undo decides whether to take points back by comparing
    the completion to that deadline, so an overdue completion that paid nothing
    looked on time and the balance dropped.
    """
    person_id, name = client.add_person(points=10)
    clock = _future_clock()
    today = datetime.now(timezone.utc).date()
    yesterday = today - timedelta(days=1)
    chore_id = client.add_chore(
        person_id,
        name,
        is_daily=True,
        completed=False,
        due_date=today,
        due_datetime=datetime.combine(yesterday, clock),
    )

    complete = client.post('/complete_chore', json={'chore_id': chore_id})
    assert complete.status_code == 200
    assert complete.get_json()['overdue'] is True
    assert complete.get_json()['points_awarded'] == 0

    _run_reset([chore_id])

    with app.app_context():
        chore = db.session.get(Chore, chore_id)
        assert chore.completed is True
        assert chore.due_datetime == datetime.combine(yesterday, clock)

    undo = client.post('/undo_complete_chore', json={'chore_id': chore_id})
    assert undo.status_code == 200
    assert undo.get_json()['success'] is True
    with app.app_context():
        assert db.session.get(Person, person_id).points == 10
        assert db.session.get(Chore, chore_id).completed is False

    _run_reset([chore_id])
    again = client.post('/complete_chore', json={'chore_id': chore_id})
    body = again.get_json()
    assert again.status_code == 200
    assert body['overdue'] is False
    assert body['points_awarded'] == 5
    with app.app_context():
        assert db.session.get(Person, person_id).points == 15


def test_one_off_chore_keeps_its_original_deadline(client):
    person_id, name = client.add_person()
    yesterday = datetime.now(timezone.utc).date() - timedelta(days=1)
    original = datetime.combine(yesterday, time(8, 0))
    chore_id = client.add_chore(
        person_id,
        name,
        is_daily=False,
        completed=False,
        due_date=yesterday,
        due_datetime=original,
    )

    _run_reset([chore_id])

    with app.app_context():
        chore = db.session.get(Chore, chore_id)
        assert chore.due_datetime == original
        assert chore.due_date == yesterday
        assert chore.completed is False
