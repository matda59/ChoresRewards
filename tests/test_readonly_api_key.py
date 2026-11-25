"""A read-only API key can read the allowlist and cannot do anything else.

The key is for a trusted automation. It is not a browser session: it must not
set a cookie, run the daily chore reset, or share the PIN lockout.
"""

import json
import os
import time
import uuid
from datetime import date, timedelta

import bcrypt
import pytest

import auth_guard
from app import app, db
from models import AppSetting, Chore, OrganiseItem, Person, VehicleService


_EXPECTED_EXACT = frozenset({
    '/api/screensaver/chore_summary',
    '/api/meal_planner',
    '/api/shopping_list',
    '/api/shopping_stores',
    '/api/meal_ingredients',
    '/api/notifications',
    '/api/notes',
    '/api/dashboard_notes',
    '/api/organise',
})


def _anon():
    client = app.test_client()
    with client.session_transaction() as sess:
        sess.clear()
    return client


def _session(adult):
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['authenticated'] = True
        sess['adult_mode'] = adult
    return client


def _bearer(key):
    return {'Authorization': f'Bearer {key}'}


def _pin_path():
    return os.path.join(app.instance_path, 'pin_attempts.json')


def _attempt_path():
    return os.path.join(app.instance_path, 'readonly_api_key_attempts.json')


def _read(path):
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as handle:
        return handle.read()


def _write(path, text):
    if text is None:
        if os.path.exists(path):
            os.remove(path)
        return
    with open(path, 'w', encoding='utf-8') as handle:
        handle.write(text)


@pytest.fixture
def readonly_key(monkeypatch):
    key = 'readonly-test-' + ('k' * 32)
    monkeypatch.setenv('CR_READONLY_API_KEY', key)
    auth_guard._API_KEY_MEMORY.clear()
    _write(_attempt_path(), None)
    yield key
    auth_guard._API_KEY_MEMORY.clear()
    _write(_attempt_path(), None)


@pytest.fixture(autouse=True)
def _no_calendar_network(monkeypatch):
    monkeypatch.setattr(
        'routes.fetch_google_calendar_events',
        lambda *_args, **_kwargs: ([], None),
    )


def test_allowlist_is_the_explicit_read_set():
    assert auth_guard._READONLY_API_EXACT == _EXPECTED_EXACT
    assert auth_guard.readonly_api_allows('GET', '/api/organise/12/services')
    assert auth_guard.readonly_api_allows('HEAD', '/api/notes/')
    assert not auth_guard.readonly_api_allows('POST', '/api/notes')
    assert not auth_guard.readonly_api_allows('PUT', '/api/organise/12/services')
    assert not auth_guard.readonly_api_allows('GET', '/api/organise/12')
    assert not auth_guard.readonly_api_allows('GET', '/api/organise/12/services/4')
    assert not auth_guard.readonly_api_allows('GET', '/api/organise/12/photo')
    assert not auth_guard.readonly_api_allows('GET', '/')
    assert not auth_guard.readonly_api_allows('GET', '/get_chores')
    assert not auth_guard.readonly_api_allows('GET', '/settings')
    assert not auth_guard.readonly_api_allows('GET', '/api/notes/../organise')


def test_no_key_is_rejected_and_a_valid_key_reads_the_allowlist(readonly_key):
    app.config['TESTING'] = True
    name = f'Key Reader {uuid.uuid4().hex[:8]}'
    title = f'Pack lunch {uuid.uuid4().hex[:8]}'
    rego = f'K{uuid.uuid4().hex[:5].upper()}'
    with app.app_context():
        from routes import _family_today
        person = Person(name=name, points=1, bonus_points=0)
        db.session.add(person)
        db.session.flush()
        chore = Chore(
            title=title,
            assigned_to=name,
            assigned_to_id=person.id,
            points=1,
            completed=False,
            is_daily=False,
            deleted=False,
            due_date=_family_today(),
        )
        car = OrganiseItem(
            category='Car',
            title=f'Family car {rego}',
            due_date=_family_today() + timedelta(days=2),
            reminder_days=30,
            paid=False,
            vehicle_rego=rego,
            next_service_date=_family_today() + timedelta(days=3),
            next_service_explicit=True,
        )
        db.session.add(chore)
        db.session.add(car)
        db.session.flush()
        service = VehicleService(
            organise_item_id=car.id,
            service_type='Oil',
            service_date=_family_today() - timedelta(days=30),
        )
        db.session.add(service)
        db.session.commit()
        person_id = person.id
        chore_id = chore.id
        car_id = car.id
        service_id = service.id
    try:
        stranger = _anon()
        missing = stranger.get('/api/notes')
        assert missing.status_code == 401
        assert missing.get_json()['error'] == 'Login required'
        assert 'Set-Cookie' not in missing.headers

        wrong = stranger.get('/api/notes', headers={'X-API-Key': 'wrong-' + ('x' * 32)})
        assert wrong.status_code == 401
        assert wrong.get_json()['error'] == 'Invalid API key'
        assert readonly_key not in wrong.get_data(as_text=True)
        assert 'Set-Cookie' not in wrong.headers

        headers = _bearer(readonly_key)
        for path in sorted(_EXPECTED_EXACT):
            response = stranger.get(path, headers=headers)
            assert response.status_code == 200, path
            assert response.get_json()['success'] is True, path
            assert 'Set-Cookie' not in response.headers

        header_key = stranger.get('/api/shopping_stores', headers={'X-API-Key': readonly_key})
        assert header_key.status_code == 200
        lowered = stranger.get('/api/dashboard_notes', headers={'Authorization': f'bearer {readonly_key}'})
        assert lowered.status_code == 200
        with app.app_context():
            ingredients_before = AppSetting.get('meal_ingredients_json')
        head = stranger.head('/api/meal_ingredients', headers=headers)
        assert head.status_code == 200
        assert 'Set-Cookie' not in head.headers
        with app.app_context():
            assert AppSetting.get('meal_ingredients_json') == ingredients_before

        summary = stranger.get('/api/screensaver/chore_summary', headers=headers)
        assert name in summary.get_data(as_text=True)
        assert title in summary.get_data(as_text=True)

        alerts = stranger.get('/api/notifications', headers=headers)
        blob = alerts.get_data(as_text=True)
        assert rego in blob
        assert 'Service' in blob

        listed = stranger.get('/api/organise', headers=headers)
        assert rego in listed.get_data(as_text=True)
        history = stranger.get(f'/api/organise/{car_id}/services', headers=headers)
        assert history.status_code == 200
        assert history.get_json()['services'][0]['service_type'] == 'Oil'

        # The key did not log the client in.
        assert stranger.get('/api/notes').status_code == 401
    finally:
        with app.app_context():
            for model, row_id in (
                (VehicleService, service_id),
                (OrganiseItem, car_id),
                (Chore, chore_id),
                (Person, person_id),
            ):
                row = db.session.get(model, row_id)
                if row:
                    db.session.delete(row)
            db.session.commit()


def test_valid_key_cannot_write_or_read_outside_the_allowlist(readonly_key):
    app.config['TESTING'] = True
    headers = _bearer(readonly_key)
    client = _anon()
    with app.app_context():
        original_list = AppSetting.get('shopping_list_json')
        original_reset = AppSetting.get('last_daily_reset')
        AppSetting.set(
            'shopping_list_json',
            json.dumps({'general': [{'name': 'Milk', 'store': 'aldi'}]}),
        )
        AppSetting.set('last_daily_reset', '1999-01-01')
    try:
        denied_gets = (
            '/',
            '/settings',
            '/usage',
            '/get_chores',
            '/chore_history',
            '/activity_log',
            '/completed_chores_fragment',
            '/api/auth_status',
            '/api/sounds',
            '/api/images',
            '/api/extra_chores',
            '/api/text_pads',
            '/api/person_points',
            '/api/bonus_settings',
            '/api/check_auth',
            '/static/uploads/not-a-real-photo.png',
            '/profile/1',
        )
        for path in denied_gets:
            response = client.get(path, headers=headers)
            assert response.status_code == 403, path
            assert response.get_json()['error'] == 'API key is read-only'
            assert 'Set-Cookie' not in response.headers
            assert 'data-login-shell' not in response.get_data(as_text=True)

        for method, path, payload in (
            ('post', '/api/shopping_list', {'general': [{'name': 'Bread', 'store': 'aldi'}]}),
            ('post', '/api/notes', {'notes': [], 'columns': []}),
            ('post', '/api/meal_planner', {'plan': {}}),
            ('post', '/api/organise', {'title': 'Sneaky bill'}),
            ('post', '/delete_person', {'person_id': 1}),
            ('post', '/api/login', {'pin': '1234'}),
            ('put', '/api/organise/1', {'title': 'Renamed'}),
            ('patch', '/api/notes', {'notes': []}),
            ('delete', '/api/organise/1', None),
        ):
            kwargs = {'headers': headers}
            if payload is not None:
                kwargs['json'] = payload
            response = getattr(client, method)(path, **kwargs)
            assert response.status_code == 403, (method, path)
            assert 'Set-Cookie' not in response.headers

        query = client.get(f'/api/notes?api_key={readonly_key}')
        assert query.status_code == 401
        assert query.get_json()['error'] == 'Login required'
        both = client.get(
            f'/api/shopping_list?access_token={readonly_key}',
            headers={'X-API-Key': 'nope-' + ('n' * 32)},
        )
        assert both.status_code == 401
        assert both.get_json()['error'] == 'Invalid API key'
        conflict = client.get(
            '/api/notes',
            headers={'Authorization': f'Bearer {readonly_key}', 'X-API-Key': 'other-' + ('o' * 32)},
        )
        assert conflict.status_code == 401

        with app.app_context():
            saved = AppSetting.get('shopping_list_json')
            assert 'Milk' in saved
            assert 'Bread' not in saved
            assert AppSetting.get('last_daily_reset') == '1999-01-01'
    finally:
        with app.app_context():
            if original_list is None:
                row = AppSetting.query.filter_by(key='shopping_list_json').first()
                if row:
                    db.session.delete(row)
                    db.session.commit()
            else:
                AppSetting.set('shopping_list_json', original_list)
            if original_reset is None:
                row = AppSetting.query.filter_by(key='last_daily_reset').first()
                if row:
                    db.session.delete(row)
                    db.session.commit()
            else:
                AppSetting.set('last_daily_reset', original_reset)


def test_key_does_not_create_a_session_or_touch_the_pin_lockout(readonly_key):
    app.config['TESTING'] = True
    pin_before = _read(_pin_path())
    client = _anon()
    try:
        for _ in range(3):
            response = client.get('/api/meal_planner', headers={'X-API-Key': 'guess-' + ('g' * 32)})
            assert response.status_code == 401
        assert _read(_pin_path()) == pin_before

        locked_until = time.time() + 600
        payload = {}
        if pin_before:
            try:
                loaded = json.loads(pin_before)
                if isinstance(loaded, dict):
                    payload = loaded
            except Exception:
                payload = {}
        for ip in ('127.0.0.1', '::1'):
            payload[f'pin:{ip}'] = {'count': 0, 'locked_until': locked_until}
        _write(_pin_path(), json.dumps(payload))

        locked = client.post('/api/login', json={'pin': '1234'})
        assert locked.status_code == 429
        opened = client.get('/api/notifications', headers=_bearer(readonly_key))
        assert opened.status_code == 200
        assert 'Set-Cookie' not in opened.headers
        assert client.get('/api/notifications').status_code == 401
    finally:
        _write(_pin_path(), pin_before)


def test_valid_key_cannot_log_in_with_the_pin(readonly_key):
    app.config['TESTING'] = True
    pin_before = _read(_pin_path())
    with app.app_context():
        original = AppSetting.get('master_pin')
        AppSetting.set('master_pin', bcrypt.hashpw(b'1234', bcrypt.gensalt()).decode('utf-8'))
    try:
        client = _anon()
        response = client.post('/api/login', json={'pin': '1234'}, headers=_bearer(readonly_key))
        assert response.status_code == 403
        assert 'Set-Cookie' not in response.headers
        assert client.get('/api/notes').status_code == 401
        assert _read(_pin_path()) == pin_before
    finally:
        _write(_pin_path(), pin_before)
        with app.app_context():
            if original:
                AppSetting.set('master_pin', original)
            else:
                row = AppSetting.query.filter_by(key='master_pin').first()
                if row:
                    db.session.delete(row)
                    db.session.commit()


def test_wrong_keys_are_rate_limited_and_a_good_key_still_works(readonly_key, monkeypatch):
    app.config['TESTING'] = True
    monkeypatch.setattr(auth_guard, '_API_KEY_MAX_FAILURES', 3)
    client = _anon()
    statuses = [
        client.get('/api/notes', headers={'X-API-Key': f'nope-{index}-' + ('z' * 32)}).status_code
        for index in range(4)
    ]
    assert statuses == [401, 401, 429, 429]
    limited = client.get('/api/notes', headers={'X-API-Key': 'still-wrong-' + ('q' * 32)})
    assert limited.status_code == 429
    assert limited.get_json()['retry_after']
    assert limited.headers['Retry-After']
    assert 'Set-Cookie' not in limited.headers
    assert client.get('/api/notes', headers=_bearer(readonly_key)).status_code == 200


def test_feature_is_disabled_when_the_env_is_missing_or_short(monkeypatch):
    app.config['TESTING'] = True
    long_key = 'b' * 40
    client = _anon()

    monkeypatch.delenv('CR_READONLY_API_KEY', raising=False)
    disabled = client.get('/api/notes', headers=_bearer(long_key))
    assert disabled.status_code == 401
    assert disabled.get_json()['error'] == 'Login required'

    monkeypatch.setenv('CR_READONLY_API_KEY', '   ')
    blank = client.get('/api/shopping_list', headers={'X-API-Key': long_key})
    assert blank.status_code == 401
    assert blank.get_json()['error'] == 'Login required'

    monkeypatch.setenv('CR_READONLY_API_KEY', 'c' * 31)
    short = client.get('/api/meal_planner', headers=_bearer('c' * 31))
    assert short.status_code == 401
    assert short.get_json()['error'] == 'Login required'

    monkeypatch.setenv('CR_READONLY_API_KEY', '  ' + ('d' * 32) + '  ')
    boundary = client.get('/api/dashboard_notes', headers={'X-API-Key': 'd' * 32})
    assert boundary.status_code == 200
    assert boundary.get_json()['success'] is True


def test_sessions_still_work_while_the_key_feature_is_on(readonly_key):
    app.config['TESTING'] = True
    child = _session(adult=False)
    with child.session_transaction() as sess:
        before = dict(sess)

    read = child.get('/api/notes')
    assert read.status_code == 200
    denied = child.post('/delete_person', json={'person_id': 1})
    assert denied.status_code == 403
    empty = child.post('/api/meal_comment', json={})
    assert empty.status_code == 400

    # A key on the request is the credential, even if a session cookie is attached.
    keyed = child.post('/api/notes', json={'notes': [], 'columns': []}, headers=_bearer(readonly_key))
    assert keyed.status_code == 403
    with child.session_transaction() as sess:
        assert sess.get('authenticated') is True
        assert sess.get('adult_mode') is False
        assert dict(sess) == before

    board_name = f'Board {uuid.uuid4().hex[:8]}'
    with app.app_context():
        person = Person(name=board_name, points=0, bonus_points=0)
        db.session.add(person)
        db.session.commit()
        person_id = person.id
    try:
        adult = _session(adult=True)
        home = adult.get('/')
        assert home.status_code == 200
        html = home.get_data(as_text=True)
        assert 'data-login-shell' not in html
        assert board_name in html
    finally:
        with app.app_context():
            person = db.session.get(Person, person_id)
            if person:
                db.session.delete(person)
            db.session.commit()


def test_child_session_still_hides_service_alerts_when_the_key_is_enabled(readonly_key):
    app.config['TESTING'] = True
    title = f'Service leak {uuid.uuid4().hex[:8]}'
    rego = f'S{uuid.uuid4().hex[:5].upper()}'
    with app.app_context():
        item = OrganiseItem(
            category='Car',
            title=title,
            due_date=date.today() + timedelta(days=2),
            reminder_days=30,
            paid=False,
            vehicle_rego=rego,
            next_service_date=date.today() + timedelta(days=2),
            next_service_explicit=True,
        )
        db.session.add(item)
        db.session.commit()
        item_id = item.id
    try:
        child = _session(adult=False).get('/api/notifications')
        assert child.status_code == 200
        hidden = child.get_data(as_text=True)
        assert title not in hidden
        assert rego not in hidden

        shown = _anon().get('/api/notifications', headers=_bearer(readonly_key))
        assert shown.status_code == 200
        visible = shown.get_data(as_text=True)
        assert title in visible
        assert rego in visible
    finally:
        with app.app_context():
            item = db.session.get(OrganiseItem, item_id)
            if item:
                db.session.delete(item)
            db.session.commit()
