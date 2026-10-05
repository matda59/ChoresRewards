"""Chores reset at midnight in the timezone chosen in Settings.

Due times are wall-clock times in that zone. The reset used to follow the
container date instead. On a UTC container with Australia selected, the new
day did not open until mid-morning, which is after an 8am deadline, so the
chore reappeared already overdue and paid nothing.
"""

import uuid
from datetime import date, datetime, timezone

from app import app, db
from models import AppSetting, Chore, Person
import routes as routes_mod
from routes import _family_today


# 6pm UTC is 3:30am the next day in Adelaide (ACST, UTC+9:30).
FROZEN_UTC = datetime(2026, 10, 1, 18, 0, tzinfo=timezone.utc)
CONTAINER_TODAY = date(2026, 10, 1)
FAMILY_TODAY = date(2026, 10, 2)


class _FrozenClock(datetime):
    @classmethod
    def now(cls, tz=None):
        if tz is None:
            return FROZEN_UTC.replace(tzinfo=None)
        return FROZEN_UTC.astimezone(tz)


class _ContainerDate(date):
    @classmethod
    def today(cls):
        return CONTAINER_TODAY


def _snapshot_daily(own_ids):
    rows = []
    for chore in Chore.query.filter_by(is_daily=True, deleted=False).all():
        if chore.id in own_ids:
            continue
        rows.append((
            chore.id,
            chore.completed,
            chore.due_date,
            chore.due_datetime,
            chore.date_completed,
        ))
    return rows


def _restore_daily(rows):
    for chore_id, completed, due_date, due_datetime, date_completed in rows:
        chore = db.session.get(Chore, chore_id)
        if chore is None:
            continue
        chore.completed = completed
        chore.due_date = due_date
        chore.due_datetime = due_datetime
        chore.date_completed = date_completed
    db.session.commit()


def test_morning_deadline_pays_when_the_family_day_is_ahead_of_the_container(monkeypatch):
    monkeypatch.setattr(routes_mod, 'datetime', _FrozenClock)
    monkeypatch.setattr(routes_mod, 'date', _ContainerDate)

    app.config['TESTING'] = True
    client = app.test_client()
    created = {'people': [], 'chores': []}
    snapshot = []
    title = f'Make the bed {uuid.uuid4().hex[:8]}'

    with app.app_context():
        saved_timezone = AppSetting.get('timezone')
        saved_reset = AppSetting.get('last_daily_reset')
        saved_gotify = AppSetting.get('gotify_notify_due_chores_expired')
        AppSetting.set('timezone', 'Australia/Adelaide')
        AppSetting.set('last_daily_reset', '1999-01-01')
        AppSetting.set('gotify_notify_due_chores_expired', 'false')
        assert routes_mod.date.today() == CONTAINER_TODAY
        assert _family_today() == FAMILY_TODAY

        person = Person(name=f'Tz Kid {uuid.uuid4().hex[:6]}', points=0, bonus_points=0)
        db.session.add(person)
        db.session.flush()
        chore = Chore(
            title=title,
            assigned_to=person.name,
            assigned_to_id=person.id,
            points=5,
            is_daily=True,
            completed=True,
            deleted=False,
            due_date=CONTAINER_TODAY,
            due_datetime=datetime(2026, 10, 1, 8, 0),
            date_completed=datetime(2026, 10, 1, 7, 30),
        )
        db.session.add(chore)
        db.session.commit()
        created['people'].append(person.id)
        created['chores'].append(chore.id)
        snapshot = _snapshot_daily(set(created['chores']))

    with client.session_transaction() as sess:
        sess['authenticated'] = True

    try:
        html = client.get('/').get_data(as_text=True)
        assert title in html

        with app.app_context():
            reopened = db.session.get(Chore, created['chores'][0])
            assert reopened.completed is False
            assert reopened.due_date == FAMILY_TODAY
            assert reopened.due_datetime == datetime(2026, 10, 2, 8, 0)

        resp = client.post('/complete_chore', json={'chore_id': created['chores'][0]})
        body = resp.get_json()
        assert resp.status_code == 200
        assert body['success'] is True
        assert body['overdue'] is False
        assert body['points_awarded'] == 5
        with app.app_context():
            assert db.session.get(Person, created['people'][0]).points == 5
    finally:
        with app.app_context():
            _restore_daily(snapshot)
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
            if saved_reset is None:
                row = AppSetting.query.filter_by(key='last_daily_reset').first()
                if row:
                    db.session.delete(row)
            else:
                AppSetting.set('last_daily_reset', saved_reset)
            if saved_gotify is None:
                row = AppSetting.query.filter_by(key='gotify_notify_due_chores_expired').first()
                if row:
                    db.session.delete(row)
            else:
                AppSetting.set('gotify_notify_due_chores_expired', saved_gotify)
            db.session.commit()
