"""General Settings must say whether a save worked.

The page already builds a success or error message for the App PIN, ages,
timezone, and bonus settings. Quiz and extra-chore settings print theirs.
General Settings did not, so a wrong current PIN reloaded the same form
and looked the same as a PIN that had changed.
"""

import uuid

import bcrypt

from app import app, db
from models import ActivityLog, AppSetting, Person


def _adult_client():
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['adult_mode'] = True
    return client


def _pin_is(raw_pin):
    stored = AppSetting.get('master_pin')
    if not stored or not raw_pin:
        return False
    try:
        return bcrypt.checkpw(raw_pin.encode('utf-8'), stored.encode('utf-8'))
    except ValueError:
        return False


def test_a_failed_pin_change_says_why_and_leaves_the_pin():
    app.config['TESTING'] = True
    client = _adult_client()
    with app.app_context():
        original = AppSetting.get('master_pin')
        AppSetting.set(
            'master_pin',
            bcrypt.hashpw(b'1234', bcrypt.gensalt()).decode('utf-8'),
        )
    try:
        page = client.get('/settings')
        assert page.status_code == 200
        html = page.get_data(as_text=True)
        assert 'class="success-message"' not in html
        assert 'class="error-message"' not in html

        wrong = client.post('/settings', data={
            'change_pin': '1',
            'current_pin': '0000',
            'new_pin': '9999',
            'confirm_pin': '9999',
        })
        assert wrong.status_code == 200
        assert 'Current PIN is incorrect.' in wrong.get_data(as_text=True)
        assert 'Master PIN changed successfully.' not in wrong.get_data(as_text=True)
        with app.app_context():
            assert _pin_is('1234')

        mismatch = client.post('/settings', data={
            'change_pin': '1',
            'current_pin': '1234',
            'new_pin': '9999',
            'confirm_pin': '8888',
        })
        assert 'New PIN and confirmation do not match.' in mismatch.get_data(as_text=True)
        with app.app_context():
            assert _pin_is('1234')

        changed = client.post('/settings', data={
            'change_pin': '1',
            'current_pin': '1234',
            'new_pin': '5678',
            'confirm_pin': '5678',
        })
        assert 'Master PIN changed successfully.' in changed.get_data(as_text=True)
        with app.app_context():
            assert _pin_is('5678')
    finally:
        with app.app_context():
            if original:
                AppSetting.set('master_pin', original)
            else:
                row = AppSetting.query.filter_by(key='master_pin').first()
                if row:
                    db.session.delete(row)
                    db.session.commit()


def test_save_ages_and_bonus_settings_say_they_saved():
    app.config['TESTING'] = True
    client = _adult_client()
    suffix = uuid.uuid4().hex[:8]
    keys = (
        'bonus_mode',
        'bonus_static',
        'bonus_min',
        'bonus_max',
        'bonus_once_per_day',
        'quiz_questions_enabled',
    )
    with app.app_context():
        person = Person(name='Banner {}'.format(suffix))
        db.session.add(person)
        db.session.commit()
        person_id = person.id
        saved_settings = {key: AppSetting.get(key) for key in keys}
    try:
        ages = client.post('/settings', data={
            'save_ages': '1',
            'person_age_{}'.format(person_id): '9',
        })
        assert ages.status_code == 200
        assert 'Ages saved successfully!' in ages.get_data(as_text=True)
        with app.app_context():
            assert db.session.get(Person, person_id).age == 9

        bonus = client.post('/settings', data={
            'bonus_mode': 'static',
            'bonus_static': saved_settings.get('bonus_static') or '10',
            'bonus_min': saved_settings.get('bonus_min') or '',
            'bonus_max': saved_settings.get('bonus_max') or '',
            'bonus_once_per_day': 'on' if saved_settings.get('bonus_once_per_day') == 'true' else '',
            'quiz_questions_enabled': 'on' if saved_settings.get('quiz_questions_enabled') == 'true' else '',
        })
        assert 'Bonus points settings saved.' in bonus.get_data(as_text=True)
        with app.app_context():
            assert AppSetting.get('bonus_mode') == 'static'
            assert AppSetting.get('bonus_once_per_day') == (
                'true' if saved_settings.get('bonus_once_per_day') == 'true' else 'false'
            )
    finally:
        with app.app_context():
            person = db.session.get(Person, person_id)
            if person:
                db.session.delete(person)
            ActivityLog.query.filter(ActivityLog.description.contains(suffix)).delete(synchronize_session=False)
            for key, value in saved_settings.items():
                if value is None:
                    row = AppSetting.query.filter_by(key=key).first()
                    if row:
                        db.session.delete(row)
                else:
                    AppSetting.set(key, value)
            db.session.commit()


def test_child_session_cannot_open_settings_or_change_the_pin():
    app.config['TESTING'] = True
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['authenticated'] = True
        sess['adult_mode'] = False
    with app.app_context():
        original = AppSetting.get('master_pin')
    try:
        page = client.get('/settings', follow_redirects=False)
        assert page.status_code in (302, 303)
        denied = client.post('/settings', data={
            'change_pin': '1',
            'current_pin': '0000',
            'new_pin': '9999',
            'confirm_pin': '9999',
        }, follow_redirects=False)
        assert denied.status_code in (302, 303)
        with app.app_context():
            assert AppSetting.get('master_pin') == original
    finally:
        with app.app_context():
            if AppSetting.get('master_pin') != original:
                if original:
                    AppSetting.set('master_pin', original)
                else:
                    row = AppSetting.query.filter_by(key='master_pin').first()
                    if row:
                        db.session.delete(row)
                        db.session.commit()
