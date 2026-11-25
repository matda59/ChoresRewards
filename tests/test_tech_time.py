"""Weekend tech time: minutes per chore, a Monday expiry, and points left alone.

The balance is the sum of this week's ledger rows. Monday does not delete
those rows, and the daily chore reset does not either.
"""

import uuid
from datetime import date, datetime, timedelta, timezone

from app import app, db
import auth_guard
from models import (
    ActivityLog,
    AppSetting,
    Chore,
    Person,
    TechTimeEntry,
    format_tech_minutes,
    minutes_from_points,
    tech_time_balance,
    week_start_for_instant,
)
import models as models_mod
import routes as routes_mod
from routes import reset_daily_chores


# 12:59 UTC Sunday is 23:59 Sunday in Melbourne (AEDT, UTC+11).
# 13:00 UTC is 00:00 Monday.
SUNDAY_UTC = datetime(2026, 11, 29, 12, 59, tzinfo=timezone.utc)
MONDAY_UTC = datetime(2026, 11, 29, 13, 0, tzinfo=timezone.utc)
WEEK_OF_SUNDAY = date(2026, 11, 23)
WEEK_OF_MONDAY = date(2026, 11, 30)


class _FrozenClock(datetime):
    when = SUNDAY_UTC

    @classmethod
    def now(cls, tz=None):
        if tz is None:
            return cls.when.replace(tzinfo=None)
        return cls.when.astimezone(tz)


def _adult():
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['authenticated'] = True
        sess['adult_mode'] = True
    return client


def _remember(*keys):
    return {key: AppSetting.get(key) for key in keys}


def _restore_settings(saved):
    for key, value in saved.items():
        row = AppSetting.query.filter_by(key=key).first()
        if value is None:
            if row:
                db.session.delete(row)
        else:
            if row:
                row.value = value
            else:
                db.session.add(AppSetting(key=key, value=value))
    db.session.commit()


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


def _person(name, points):
    person = Person(name=name, points=points, bonus_points=0)
    db.session.add(person)
    db.session.commit()
    return person


def _chore(person, title, points, is_daily=False, due_date=None):
    chore = Chore(
        title=title,
        assigned_to=person.name,
        assigned_to_id=person.id,
        points=points,
        completed=False,
        deleted=False,
        is_daily=is_daily,
        due_date=due_date,
    )
    db.session.add(chore)
    db.session.commit()
    return chore


def _cleanup(person_ids, chore_ids):
    TechTimeEntry.query.filter(TechTimeEntry.person_id.in_(person_ids or [0])).delete(synchronize_session=False)
    for chore_id in chore_ids:
        chore = db.session.get(Chore, chore_id)
        if chore:
            db.session.delete(chore)
    for person_id in person_ids:
        person = db.session.get(Person, person_id)
        if person:
            ActivityLog.query.filter_by(user_name=person.name).delete(synchronize_session=False)
            db.session.delete(person)
    db.session.commit()


def test_minutes_format_and_melbourne_week_boundary():
    app.config['TESTING'] = True
    with app.app_context():
        saved = _remember('timezone')
        AppSetting.set('timezone', 'Australia/Melbourne')
        try:
            assert format_tech_minutes(130) == '2h 10m'
            assert format_tech_minutes(60) == '1h'
            assert format_tech_minutes(0) == '0m'
            assert format_tech_minutes(15) == '15m'
            assert format_tech_minutes(-20) == '-20m'
            assert minutes_from_points(15) == 15
            assert minutes_from_points(0.5) == 1
            assert minutes_from_points(0) == 0
            assert week_start_for_instant(SUNDAY_UTC) == WEEK_OF_SUNDAY
            assert week_start_for_instant(MONDAY_UTC) == WEEK_OF_MONDAY
        finally:
            _restore_settings(saved)


def test_completing_and_uncompleting_moves_this_weeks_minutes():
    app.config['TESTING'] = True
    client = _adult()
    suffix = uuid.uuid4().hex[:8]
    name = 'Tech Earn {}'.format(suffix)
    with app.app_context():
        saved = _remember('reward_system', 'timezone', 'bonus_mode', 'bonus_static', 'bonus_once_per_day')
        AppSetting.set('timezone', 'Australia/Melbourne')
        AppSetting.set_reward_system('tech_time')
        AppSetting.set('bonus_mode', 'static')
        AppSetting.set('bonus_static', '10')
        AppSetting.set('bonus_once_per_day', 'false')
        person = _person(name, points=4)
        teeth = _chore(person, 'Brush teeth {}'.format(suffix), 5)
        room = _chore(person, 'Clean room {}'.format(suffix), 15)
        half = _chore(person, 'Half {}'.format(suffix), 0.5)
        person_id = person.id
        chore_ids = [teeth.id, room.id, half.id]
    try:
        first = client.post('/complete_chore', json={'chore_id': chore_ids[0]})
        assert first.status_code == 200
        assert first.get_json()['tech_minutes'] == 5
        assert first.get_json()['minutes_awarded'] == 5
        assert first.get_json()['points_awarded'] == 0
        second = client.post('/complete_chore', json={'chore_id': chore_ids[1]})
        assert second.get_json()['tech_minutes'] == 20
        assert second.get_json()['tech_time_display'] == '20m'
        with app.app_context():
            assert db.session.get(Person, person_id).points == 4
            assert tech_time_balance(person_id) == 20

        summary = client.get('/api/screensaver/chore_summary')
        body = summary.get_json()
        assert body['reward_mode'] == 'tech_time'
        row = next(person for person in body['people'] if person['name'] == name)
        assert row['tech_minutes'] == 20
        assert row['tech_time_display'] == '20m'

        undone = client.post('/undo_complete_chore', json={'chore_id': chore_ids[1]})
        assert undone.status_code == 200
        assert undone.get_json()['tech_minutes'] == 5
        again = client.post('/complete_chore', json={'chore_id': chore_ids[1]})
        assert again.get_json()['tech_minutes'] == 20
        client.post('/undo_complete_chore', json={'chore_id': chore_ids[1]})
        client.post('/undo_complete_chore', json={'chore_id': chore_ids[0]})
        with app.app_context():
            assert tech_time_balance(person_id) == 0
            assert db.session.get(Person, person_id).points == 4

        half_done = client.post('/complete_chore', json={'chore_id': chore_ids[2]})
        assert half_done.get_json()['minutes_awarded'] == 1
        bonus = client.post('/award_bonus_points', json={'person_id': person_id, 'bonus_points': 10})
        assert bonus.status_code == 200
        assert bonus.get_json()['tech_minutes'] == 11
        with app.app_context():
            assert db.session.get(Person, person_id).points == 4
            assert db.session.get(Person, person_id).bonus_points == 0
    finally:
        with app.app_context():
            _cleanup([person_id], chore_ids)
            _restore_settings(saved)


def test_minutes_expire_monday_melbourne_and_daily_reset_keeps_them():
    app.config['TESTING'] = True
    client = _adult()
    suffix = uuid.uuid4().hex[:8]
    with app.app_context():
        saved = _remember('reward_system', 'timezone', 'gotify_notify_due_chores_expired', 'last_daily_reset')
        AppSetting.set('timezone', 'Australia/Melbourne')
        AppSetting.set_reward_system('tech_time')
        AppSetting.set('gotify_notify_due_chores_expired', 'false')
        person = _person('Tech Week {}'.format(suffix), points=8)
        chore = _chore(
            person,
            'Sunday job {}'.format(suffix),
            15,
            is_daily=True,
            due_date=WEEK_OF_SUNDAY + timedelta(days=6),
        )
        person_id = person.id
        chore_id = chore.id
        snapshot = _snapshot_daily({chore_id})
    monkeypatch_routes = _FrozenClock
    _FrozenClock.when = SUNDAY_UTC
    original_routes = routes_mod.datetime
    original_models = models_mod.datetime
    routes_mod.datetime = monkeypatch_routes
    models_mod.datetime = monkeypatch_routes
    try:
        done = client.post('/complete_chore', json={'chore_id': chore_id})
        assert done.status_code == 200, done.get_json()
        assert done.get_json()['overdue'] is False
        assert done.get_json()['tech_minutes'] == 15
        assert done.get_json()['tech_time_display'] == '15m'
        with app.app_context():
            assert db.session.get(Person, person_id).points == 8
            entry = TechTimeEntry.query.filter_by(person_id=person_id, source='chore').one()
            assert entry.week_start == WEEK_OF_SUNDAY
            assert entry.minutes == 15
            assert tech_time_balance(person_id) == tech_time_balance(person_id) == 15

        _FrozenClock.when = MONDAY_UTC
        with app.app_context():
            assert tech_time_balance(person_id) == 0
            assert TechTimeEntry.query.filter_by(person_id=person_id).count() == 1
            assert db.session.get(Person, person_id).points == 8
        summary = client.get('/api/screensaver/chore_summary')
        row = next(person for person in summary.get_json()['people'] if person['name'].endswith(suffix))
        assert summary.get_json()['reward_mode'] == 'tech_time'
        assert row['tech_minutes'] == 0
        assert summary.get_json()['tech_week_start'] == WEEK_OF_MONDAY.isoformat()

        with app.app_context():
            before = TechTimeEntry.query.filter_by(person_id=person_id).count()
            reset_daily_chores()
            reopened = db.session.get(Chore, chore_id)
            assert reopened.completed is False
            assert TechTimeEntry.query.filter_by(person_id=person_id).count() == before
            assert TechTimeEntry.query.filter_by(person_id=person_id, source='undo').count() == 0
            assert tech_time_balance(person_id) == 0
            assert db.session.get(Person, person_id).points == 8
            kept = TechTimeEntry.query.filter_by(person_id=person_id, source='chore').one()
            assert kept.week_start == WEEK_OF_SUNDAY
            assert kept.minutes == 15
    finally:
        routes_mod.datetime = original_routes
        models_mod.datetime = original_models
        with app.app_context():
            _restore_daily(snapshot)
            _cleanup([person_id], [chore_id])
            _restore_settings(saved)


def test_manual_adjustment_adds_and_subtracts_for_adults_only():
    app.config['TESTING'] = True
    adult = _adult()
    child = app.test_client()
    with child.session_transaction() as sess:
        sess['authenticated'] = True
        sess['adult_mode'] = False
    suffix = uuid.uuid4().hex[:8]
    note = 'movie night {}'.format(suffix)
    with app.app_context():
        saved = _remember('reward_system', 'timezone')
        AppSetting.set('timezone', 'Australia/Melbourne')
        AppSetting.set_reward_system('tech_time')
        person = _person('Tech Adjust {}'.format(suffix), points=6)
        person_id = person.id
        db.session.add(TechTimeEntry(
            person_id=person_id,
            minutes=999,
            week_start=date(2020, 1, 6),
            source='adjustment',
            note='old week',
        ))
        db.session.commit()
    try:
        added = adult.post('/adjust_tech_time', json={
            'person_id': person_id,
            'minutes': 130,
            'note': note,
        })
        assert added.status_code == 200
        assert added.get_json()['tech_minutes'] == 130
        assert added.get_json()['tech_time_display'] == '2h 10m'
        removed = adult.post('/adjust_tech_time', json={'person_id': person_id, 'minutes': -20})
        assert removed.get_json()['tech_minutes'] == 110
        assert removed.get_json()['tech_time_display'] == '1h 50m'
        rejected = adult.post('/adjust_tech_time', json={'person_id': person_id, 'minutes': 0})
        assert rejected.status_code == 400
        fraction = adult.post('/adjust_tech_time', json={'person_id': person_id, 'minutes': 1.5})
        assert fraction.status_code == 400
        denied = child.post('/adjust_tech_time', json={'person_id': person_id, 'minutes': -50})
        assert denied.status_code == 403
        with app.app_context():
            assert tech_time_balance(person_id) == 110
            assert db.session.get(Person, person_id).points == 6
            logged = ActivityLog.query.filter_by(type='tech_time_adjusted', user_name='Tech Adjust {}'.format(suffix)).all()
            assert any(note in row.description and 'Added 130' in row.description for row in logged)
            assert any('Subtracted 20' in row.description for row in logged)
    finally:
        with app.app_context():
            _cleanup([person_id], [])
            _restore_settings(saved)


def test_write_key_can_adjust_tech_time(monkeypatch):
    app.config['TESTING'] = True
    monkeypatch.setenv('CR_WRITE_API_KEY', 'w' * 40)
    monkeypatch.delenv('CR_READONLY_API_KEY', raising=False)
    auth_guard._API_KEY_MEMORY.clear()
    client = app.test_client()
    suffix = uuid.uuid4().hex[:8]
    with app.app_context():
        saved = _remember('reward_system')
        AppSetting.set_reward_system('tech_time')
        person = _person('Tech Key {}'.format(suffix), points=2)
        person_id = person.id
    try:
        denied = client.post(
            '/adjust_tech_time',
            json={'person_id': person_id, 'minutes': 15},
            headers={'Authorization': 'Bearer ' + ('r' * 40)},
        )
        assert denied.status_code == 401
        adjusted = client.post(
            '/adjust_tech_time',
            json={'person_id': person_id, 'minutes': 15, 'note': 'assistant'},
            headers={'Authorization': 'Bearer ' + ('w' * 40)},
        )
        assert adjusted.status_code == 200, adjusted.get_json()
        assert adjusted.get_json()['tech_minutes'] == 15
        with app.app_context():
            assert db.session.get(Person, person_id).points == 2
    finally:
        with app.app_context():
            _cleanup([person_id], [])
            _restore_settings(saved)
        auth_guard._API_KEY_MEMORY.clear()


def test_settings_switch_and_points_and_cash_are_unchanged():
    app.config['TESTING'] = True
    client = _adult()
    suffix = uuid.uuid4().hex[:8]
    name = 'Tech Switch {}'.format(suffix)
    with app.app_context():
        saved = _remember('reward_system')
        AppSetting.set_reward_system('points')
        person = _person(name, points=3)
        chore = _chore(person, 'Points chore {}'.format(suffix), 4)
        cash_chore = _chore(person, 'Cash chore {}'.format(suffix), 1.5)
        person_id = person.id
        chore_id = chore.id
        cash_id = cash_chore.id
    try:
        switched = client.post('/settings', data={'reward_system': 'tech_time'})
        assert switched.status_code == 302
        settings = client.get('/settings')
        html = settings.get_data(as_text=True)
        assert 'value="tech_time" checked' in html
        assert 'Adjust Tech Time' in html
        nonsense = client.post('/settings', data={'reward_system': 'gold'})
        assert nonsense.status_code == 200
        assert 'Invalid reward system' in nonsense.get_data(as_text=True)
        with app.app_context():
            assert AppSetting.get_reward_system() == 'tech_time'

        home = client.get('/')
        page = home.get_data(as_text=True)
        assert 'Minutes' in page
        assert 'name="points"' in page
        assert 'step="1"' in page
        assert name + ': 0m' in page

        client.post('/settings', data={'reward_system': 'points'})
        with app.app_context():
            assert AppSetting.get_reward_system() == 'points'
            assert db.session.get(Person, person_id).points == 3
        points_page = client.get('/').get_data(as_text=True)
        assert 'balance-label">Tech Time' not in points_page
        assert 'balance-label">Points' in points_page

        earned = client.post('/complete_chore', json={'chore_id': chore_id})
        assert earned.status_code == 200
        assert earned.get_json()['points_awarded'] == 4
        assert earned.get_json()['reward_mode'] == 'points'
        undone = client.post('/undo_complete_chore', json={'chore_id': chore_id})
        assert undone.get_json()['new_points'] == 3
        with app.app_context():
            assert db.session.get(Person, person_id).points == 3
            assert TechTimeEntry.query.filter_by(person_id=person_id).count() == 0
            summary = None
        summary = client.get('/api/screensaver/chore_summary').get_json()
        assert summary['reward_mode'] == 'points'
        row = next(person for person in summary['people'] if person['name'] == name)
        assert row['tech_minutes'] == 0

        with app.app_context():
            AppSetting.set_reward_system('cash')
        cashed = client.post('/complete_chore', json={'chore_id': cash_id})
        assert cashed.get_json()['points_awarded'] == 1.5
        assert cashed.get_json()['new_points'] == 4.5
        with app.app_context():
            assert db.session.get(Person, person_id).points == 4.5
            assert TechTimeEntry.query.filter_by(person_id=person_id).count() == 0
        cash_page = client.get('/').get_data(as_text=True)
        assert '>$1.50<' in cash_page
        assert 'balance-label">Tech Time' not in cash_page
    finally:
        with app.app_context():
            _cleanup([person_id], [chore_id, cash_id])
            _restore_settings(saved)
