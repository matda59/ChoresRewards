"""The write API key can change everyday family data and nothing else."""

import json
import os
import time
import uuid

import pytest

import auth_guard
from app import app, db
from models import AppSetting, Chore, Person, Reward


READ_KEY = 'r' * 40
WRITE_KEY = 'w' * 40

_KEPT_SETTINGS = (
    'shopping_list_json',
    'notes_kanban_json',
    'dashboard_notes_json',
    'meal_planner_plan_json',
    'meal_planner_recurring_json',
    'meal_planner_suggestions_json',
    'meal_ingredients_json',
    'last_daily_reset',
    'bonus_mode',
    'bonus_static',
    'bonus_once_per_day',
    'master_pin',
    'extra_chores_json',
)


def _anon():
    client = app.test_client()
    with client.session_transaction() as sess:
        sess.clear()
    return client


def _session(adult=True):
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


def _snapshot():
    with app.app_context():
        return {key: AppSetting.get(key) for key in _KEPT_SETTINGS}


def _restore(saved):
    with app.app_context():
        for key, value in saved.items():
            row = AppSetting.query.filter_by(key=key).first()
            if value is None:
                if row:
                    db.session.delete(row)
                    db.session.commit()
            else:
                AppSetting.set(key, value)


@pytest.fixture
def api_keys(monkeypatch):
    monkeypatch.setenv('CR_READONLY_API_KEY', READ_KEY)
    monkeypatch.setenv('CR_WRITE_API_KEY', WRITE_KEY)
    auth_guard._API_KEY_MEMORY.clear()
    auth_guard._write_key_equal_warned = False
    _write(_attempt_path(), None)
    saved = _snapshot()
    yield READ_KEY, WRITE_KEY
    _restore(saved)
    auth_guard._API_KEY_MEMORY.clear()
    auth_guard._write_key_equal_warned = False
    _write(_attempt_path(), None)


@pytest.fixture(autouse=True)
def _no_calendar_network(monkeypatch):
    monkeypatch.setattr(
        'routes.fetch_google_calendar_events',
        lambda *_args, **_kwargs: ([], None),
    )


def test_write_allowlist_matches_the_everyday_routes():
    expected = {
        ('POST', '/add_chore'),
        ('POST', '/edit_chore'),
        ('POST', '/add_daily_chore'),
        ('POST', '/edit_daily_chore'),
        ('POST', '/delete_chore'),
        ('POST', '/delete_daily_chore'),
        ('POST', '/complete_chore'),
        ('POST', '/undo_complete_chore'),
        ('POST', '/api/extra_chores/claim'),
        ('POST', '/add_reward'),
        ('POST', '/edit_reward'),
        ('POST', '/delete_reward'),
        ('POST', '/complete_reward'),
        ('POST', '/award_bonus_points'),
        ('POST', '/reset_points'),
        ('POST', '/adjust_tech_time'),
        ('POST', '/api/meal_planner/slot'),
        ('POST', '/api/meal_planner/recurring'),
        ('POST', '/api/meal_planner/suggestions/items'),
        ('POST', '/api/meal_planner/suggestions/remove'),
        ('POST', '/api/meal_ingredients/items'),
        ('POST', '/api/meal_ingredients/items/remove'),
        ('POST', '/api/shopping_list/items'),
        ('POST', '/api/shopping_list/items/check'),
        ('POST', '/api/shopping_list/items/remove'),
        ('POST', '/api/notes/cards'),
        ('POST', '/api/notes/cards/update'),
        ('POST', '/api/notes/cards/remove'),
        ('POST', '/api/dashboard_notes/notes'),
        ('POST', '/api/dashboard_notes/notes/update'),
        ('POST', '/api/dashboard_notes/notes/remove'),
    }
    assert auth_guard._WRITE_API_EXACT == frozenset(expected)
    assert not auth_guard.write_api_allows('GET', '/')
    assert not auth_guard.write_api_allows('POST', '/delete_person')
    assert not auth_guard.write_api_allows('POST', '/add_person')
    assert not auth_guard.write_api_allows('POST', '/api/login')
    assert not auth_guard.write_api_allows('POST', '/settings')
    assert not auth_guard.write_api_allows('POST', '/api/shopping_list')
    assert not auth_guard.write_api_allows('POST', '/api/notes')
    assert not auth_guard.write_api_allows('POST', '/upload_avatar/1')


def test_write_key_manages_chores_rewards_and_points(api_keys):
    app.config['TESTING'] = True
    _read_key, write_key = api_keys
    name = f'Writer {uuid.uuid4().hex[:8]}'
    other = f'Other {uuid.uuid4().hex[:8]}'
    headers = _bearer(write_key)
    client = _anon()
    with app.app_context():
        person = Person(name=name, points=10, bonus_points=0, age=8)
        second = Person(name=other, points=0, bonus_points=0)
        db.session.add(person)
        db.session.add(second)
        db.session.commit()
        person_id = person.id
        second_id = second.id
        extra_id = 'writekeyextra'
        AppSetting.set('extra_chores_json', json.dumps([{
            'id': extra_id,
            'title': 'Test extra',
            'points': 1,
            'min_age': 0,
            'icon': '',
            'enabled': True,
            'sort_order': 0,
        }]))
        AppSetting.set('bonus_mode', 'static')
        AppSetting.set('bonus_static', '2')
        AppSetting.set('bonus_once_per_day', 'false')
    chore_ids = []
    reward_id = None
    try:
        created = client.post('/add_chore', json={
            'title': 'Pack lunch',
            'assigned_to': name,
            'points': 1,
            'due_datetime': '2099-06-01T15:00:00',
        }, headers=headers)
        assert created.status_code == 200, created.get_data(as_text=True)
        assert created.get_json()['success'] is True
        assert 'Set-Cookie' not in created.headers
        chore_id = created.get_json()['chore_id']
        chore_ids.append(chore_id)

        edited = client.post('/edit_chore', json={
            'chore_id': chore_id,
            'title': 'Pack lunch box',
            'assigned_to': other,
            'points': 1,
            'days_of_week': [],
            'is_daily': False,
        }, headers=headers)
        assert edited.status_code == 200
        assert edited.get_json()['success'] is True

        done = client.post('/complete_chore', json={'chore_id': chore_id}, headers=headers)
        assert done.status_code == 200
        assert done.get_json()['success'] is True
        assert done.get_json()['points_awarded'] == 1
        undone = client.post('/undo_complete_chore', json={'chore_id': chore_id}, headers=headers)
        assert undone.status_code == 200
        assert undone.get_json()['success'] is True

        removed = client.post('/delete_chore', json={'chore_id': chore_id}, headers=headers)
        assert removed.status_code == 200
        assert removed.get_json()['success'] is True
        chore_ids.remove(chore_id)

        daily = client.post('/add_daily_chore', json={
            'title': 'Make bed',
            'assigned_to': name,
            'points': 1,
        }, headers=headers)
        assert daily.status_code == 200
        assert daily.get_json()['success'] is True
        daily_id = daily.get_json()['chore_id']
        chore_ids.append(daily_id)
        edited_daily = client.post('/edit_daily_chore', json={
            'chore_id': daily_id,
            'title': 'Make the bed',
            'assigned_to': name,
            'points': 2,
            'days_of_week': ['monday'],
        }, headers=headers)
        assert edited_daily.status_code == 200
        deleted_daily = client.post('/delete_daily_chore', json={'chore_id': daily_id}, headers=headers)
        assert deleted_daily.status_code == 200
        with app.app_context():
            saved_daily = db.session.get(Chore, daily_id)
            assert saved_daily.deleted is True

        claimed = client.post('/api/extra_chores/claim', json={
            'extra_id': extra_id,
            'person_id': person_id,
        }, headers=headers)
        assert claimed.status_code == 200, claimed.get_data(as_text=True)
        assert claimed.get_json()['success'] is True
        chore_ids.append(claimed.get_json()['chore_id'])

        reward = client.post('/add_reward', json={
            'title': 'Movie night',
            'points_required': 1,
            'assigned_to': name,
            'description': 'Friday',
        }, headers=headers)
        assert reward.status_code == 200
        assert reward.get_json()['success'] is True
        reward_id = reward.get_json()['reward_id']
        renamed = client.post('/edit_reward', json={
            'reward_id': reward_id,
            'title': 'Movie afternoon',
        }, headers=headers)
        assert renamed.status_code == 200
        redeemed = client.post('/complete_reward', json={'reward_id': reward_id}, headers=headers)
        assert redeemed.status_code == 200, redeemed.get_data(as_text=True)
        assert redeemed.get_json()['success'] is True

        reset = client.post('/reset_points', json={'person_id': person_id, 'new_points': 4}, headers=headers)
        assert reset.status_code == 200
        assert reset.get_json()['success'] is True
        bonus = client.post('/award_bonus_points', json={
            'person_id': person_id,
            'bonus_points': 2,
        }, headers=headers)
        assert bonus.status_code == 200, bonus.get_data(as_text=True)
        assert bonus.get_json()['success'] is True
        with app.app_context():
            saved = db.session.get(Person, person_id)
            assert saved.points == 6

        assert client.get('/api/notes').status_code == 401
        assert 'Set-Cookie' not in bonus.headers
    finally:
        with app.app_context():
            if reward_id:
                reward = db.session.get(Reward, reward_id)
                if reward:
                    db.session.delete(reward)
            for chore_id in chore_ids:
                chore = db.session.get(Chore, chore_id)
                if chore:
                    db.session.delete(chore)
            for row_id in (person_id, second_id):
                person = db.session.get(Person, row_id)
                if person:
                    db.session.delete(person)
            db.session.commit()


def test_granular_edits_do_not_wipe_the_rest_of_the_document(api_keys):
    app.config['TESTING'] = True
    _read_key, write_key = api_keys
    headers = _bearer(write_key)
    client = _anon()
    marker = f'Keep {uuid.uuid4().hex[:6]}'
    with app.app_context():
        AppSetting.set('shopping_list_json', json.dumps({
            'checked': {},
            'general': [{'name': marker, 'store': 'aldi'}],
            'hidden': {},
            'active': [],
            'meal_order': [],
            'archived': [],
        }))
        AppSetting.set('notes_kanban_json', json.dumps({
            'columns': [{'id': 'col-todo', 'title': 'To Do', 'color': '#fef08a'}],
            'notes': [{
                'id': 'card-existing',
                'column_id': 'col-todo',
                'text': marker,
                'checked': False,
                'order': 0,
                'deleted': False,
                'deleted_at': '',
            }],
        }))
        AppSetting.set('dashboard_notes_json', json.dumps([
            {'id': 'dash-existing', 'text': marker, 'color': '#fef08a', 'text_size': 'md'},
        ]))
        AppSetting.set('meal_planner_plan_json', json.dumps({
            '2099-01-05': {'dinner': marker},
            '2099-01-06': {'lunch': 'Keep lunch'},
        }))
        AppSetting.set('meal_ingredients_json', json.dumps({
            'pasta': [{'name': 'Existing', 'store': 'aldi', 'qty': '1'}],
        }))
        AppSetting.set('meal_planner_suggestions_json', json.dumps(['Existing soup']))
        AppSetting.set('last_daily_reset', '1999-01-01')
    try:
        blocked = client.post('/api/shopping_list', json={
            'general': [{'name': 'Bread', 'store': 'aldi'}],
        }, headers=headers)
        assert blocked.status_code == 403
        added = client.post('/api/shopping_list/items', json={'name': 'Eggs', 'store': 'aldi'}, headers=headers)
        assert added.status_code == 200
        assert added.get_json()['success'] is True
        checked = client.post('/api/shopping_list/items/check', json={
            'name': 'Eggs', 'store': 'aldi', 'checked': True,
        }, headers=headers)
        assert checked.status_code == 200
        assert checked.get_json()['checked'] is True
        listed = client.get('/api/shopping_list', headers=headers)
        blob = listed.get_data(as_text=True)
        assert marker in blob
        assert 'Eggs' in blob
        removed = client.post('/api/shopping_list/items/remove', json={
            'name': 'Eggs', 'store': 'aldi',
        }, headers=headers)
        assert removed.status_code == 200
        listed = client.get('/api/shopping_list', headers=headers)
        assert 'Eggs' not in listed.get_data(as_text=True)
        assert marker in listed.get_data(as_text=True)

        full_notes = client.post('/api/notes', json={'notes': [], 'columns': []}, headers=headers)
        assert full_notes.status_code == 403
        card = client.post('/api/notes/cards', json={'text': 'Book dentist', 'column_id': 'col-todo'}, headers=headers)
        assert card.status_code == 200
        card_id = card.get_json()['note']['id']
        ticked = client.post('/api/notes/cards/update', json={'id': card_id, 'checked': True}, headers=headers)
        assert ticked.status_code == 200
        assert ticked.get_json()['note']['checked'] is True
        cleared = client.post('/api/notes/cards/remove', json={'id': card_id}, headers=headers)
        assert cleared.status_code == 200
        notes = client.get('/api/notes', headers=headers).get_json()
        texts = [note.get('text') for note in notes['notes']]
        assert marker in texts

        full_dash = client.post('/api/dashboard_notes', json={'notes': []}, headers=headers)
        assert full_dash.status_code == 403
        posted = client.post('/api/dashboard_notes/notes', json={'text': 'Bins tonight'}, headers=headers)
        assert posted.status_code == 200
        dash_id = posted.get_json()['note']['id']
        updated = client.post('/api/dashboard_notes/notes/update', json={
            'id': dash_id, 'text': 'Bins tomorrow',
        }, headers=headers)
        assert updated.status_code == 200
        gone = client.post('/api/dashboard_notes/notes/remove', json={'id': dash_id}, headers=headers)
        assert gone.status_code == 200
        dash = client.get('/api/dashboard_notes', headers=headers).get_data(as_text=True)
        assert marker in dash
        assert 'Bins tomorrow' not in dash

        full_week = client.post('/api/meal_planner', json={'plan': {}, 'recurring': {}}, headers=headers)
        assert full_week.status_code == 403
        slot = client.post('/api/meal_planner/slot', json={
            'date': '2099-01-05', 'meal': 'dinner', 'value': 'Pasta',
        }, headers=headers)
        assert slot.status_code == 200
        plan = client.get('/api/meal_planner?week_start=2099-01-05', headers=headers).get_json()
        assert plan['plan']['2099-01-05']['dinner'] == 'Pasta'
        assert plan['plan']['2099-01-06']['lunch'] == 'Keep lunch'
        repeat = client.post('/api/meal_planner/recurring', json={
            'weekday': 'monday', 'meal': 'dinner', 'value': 'Soup', 'enabled': True,
        }, headers=headers)
        assert repeat.status_code == 200
        assert repeat.get_json()['enabled'] is True

        full_ings = client.post('/api/meal_ingredients', json={'ingredients': {}}, headers=headers)
        assert full_ings.status_code == 403
        ing = client.post('/api/meal_ingredients/items', json={
            'meal': 'pasta', 'name': 'Tomatoes', 'store': 'aldi', 'qty': '1 tin',
        }, headers=headers)
        assert ing.status_code == 200
        library = client.get('/api/meal_ingredients', headers=headers).get_json()['ingredients']
        names = [row['name'] for row in library['pasta']]
        assert names == ['Existing', 'Tomatoes']
        dropped = client.post('/api/meal_ingredients/items/remove', json={
            'meal': 'pasta', 'name': 'Tomatoes',
        }, headers=headers)
        assert dropped.status_code == 200

        suggested = client.post('/api/meal_planner/suggestions/items', json={'text': 'Tacos'}, headers=headers)
        assert suggested.status_code == 200
        assert 'Tacos' in suggested.get_json()['suggestions']
        assert 'Existing soup' in suggested.get_json()['suggestions']
        unsuggested = client.post('/api/meal_planner/suggestions/remove', json={'text': 'Tacos'}, headers=headers)
        assert unsuggested.status_code == 200

        home = client.get('/', headers=headers)
        assert home.status_code == 403
        with app.app_context():
            assert AppSetting.get('last_daily_reset') == '1999-01-01'
    finally:
        pass


def test_denied_routes_stay_denied(api_keys):
    app.config['TESTING'] = True
    _read_key, write_key = api_keys
    headers = _bearer(write_key)
    client = _anon()
    name = f'Stay {uuid.uuid4().hex[:8]}'
    with app.app_context():
        person = Person(name=name, points=3, bonus_points=0)
        db.session.add(person)
        db.session.commit()
        person_id = person.id
    try:
        denied = (
            ('get', '/', None),
            ('get', '/settings', None),
            ('post', '/settings', {}),
            ('post', '/add_person', {'name': 'Newcomer'}),
            ('post', '/delete_person', {'person_id': person_id}),
            ('post', '/update_name', {'person_id': person_id, 'name': 'Renamed'}),
            ('post', '/api/login', {'pin': '1234'}),
            ('post', '/api/adult_login', {'pin': '1234'}),
            ('post', '/api/adult_logout', {}),
            ('post', '/api/person_login', {'person_id': person_id, 'pin': '1234'}),
            ('post', '/upload_avatar/1', {}),
            ('post', '/api/sounds/upload', {}),
            ('post', '/api/screensaver/upload', {}),
            ('post', '/api/organise', {'title': 'Secret bill'}),
            ('post', '/save_column_color', {'person_id': person_id, 'color': '#fff'}),
            ('post', '/api/shopping_stores', {'stores': []}),
            ('get', '/api/shopping_list/items', None),
        )
        for method, path, payload in denied:
            kwargs = {'headers': headers}
            if payload is not None:
                kwargs['json'] = payload
            response = getattr(client, method)(path, **kwargs)
            assert response.status_code == 403, (method, path, response.status_code, response.get_data(as_text=True)[:180])
            assert 'Set-Cookie' not in response.headers
        query = client.post(f'/api/shopping_list/items?api_key={write_key}', json={'name': 'Nope', 'store': 'aldi'})
        assert query.status_code == 401
        with app.app_context():
            saved = db.session.get(Person, person_id)
            assert saved is not None
            assert saved.name == name
            assert saved.points == 3
    finally:
        with app.app_context():
            person = db.session.get(Person, person_id)
            if person:
                db.session.delete(person)
            db.session.commit()


def test_read_key_cannot_write_and_equal_keys_disable_the_write_key(api_keys, monkeypatch, capsys):
    app.config['TESTING'] = True
    read_key, write_key = api_keys
    client = _anon()
    name = f'Readonly {uuid.uuid4().hex[:8]}'
    with app.app_context():
        person = Person(name=name, points=1, bonus_points=0)
        db.session.add(person)
        db.session.commit()
        person_id = person.id
    try:
        denied = client.post('/add_chore', json={
            'title': 'Sneaky',
            'assigned_to': name,
            'points': 1,
        }, headers=_bearer(read_key))
        assert denied.status_code == 403
        assert denied.get_json()['error'] == 'API key is read-only'
        allowed = client.get('/api/shopping_list', headers=_bearer(read_key))
        assert allowed.status_code == 200
        with app.app_context():
            assert Chore.query.filter_by(title='Sneaky', assigned_to=name).first() is None
    finally:
        with app.app_context():
            person = db.session.get(Person, person_id)
            if person:
                db.session.delete(person)
            db.session.commit()

    same = 's' * 40
    monkeypatch.setenv('CR_READONLY_API_KEY', same)
    monkeypatch.setenv('CR_WRITE_API_KEY', same)
    auth_guard._write_key_equal_warned = False
    capsys.readouterr()
    same_client = _anon()
    reading = same_client.get('/api/notes', headers=_bearer(same))
    warning = capsys.readouterr().out
    assert reading.status_code == 200
    assert 'matches CR_READONLY_API_KEY' in warning
    assert same not in warning
    writing = same_client.post('/api/shopping_list/items', json={'name': 'Same key', 'store': 'aldi'}, headers=_bearer(same))
    assert writing.status_code == 403
    assert writing.get_json()['error'] == 'API key is read-only'
    assert write_key not in warning


def test_wrong_keys_are_rate_limited_and_ignore_the_pin_lockout(api_keys, monkeypatch):
    app.config['TESTING'] = True
    _read_key, write_key = api_keys
    monkeypatch.setattr(auth_guard, '_API_KEY_MAX_FAILURES', 3)
    pin_before = _read(_pin_path())
    client = _anon()
    try:
        statuses = [
            client.post(
                '/api/shopping_list/items',
                json={'name': 'Nope', 'store': 'aldi'},
                headers={'X-API-Key': f'nope-{index}-' + ('z' * 32)},
            ).status_code
            for index in range(4)
        ]
        assert statuses == [401, 401, 429, 429]
        assert _read(_pin_path()) == pin_before
        assert client.get('/api/notes', headers=_bearer(write_key)).status_code == 200

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
        assert client.post('/api/login', json={'pin': '1234'}).status_code == 429
        opened = client.post('/api/shopping_list/items', json={'name': 'During lock', 'store': 'aldi'}, headers=_bearer(write_key))
        assert opened.status_code == 200
        assert 'Set-Cookie' not in opened.headers
    finally:
        _write(_pin_path(), pin_before)


def test_write_key_bypasses_csrf_and_a_browser_session_does_not(api_keys):
    app.config['TESTING'] = True
    read_key, write_key = api_keys
    anon = _anon()
    blocked = _session().post(
        '/api/meal_comment',
        json={},
        headers={'Origin': 'https://evil.example'},
    )
    assert blocked.status_code == 403
    assert blocked.get_json()['error'] == 'Cross-site request blocked'

    still_open = _session().post('/api/meal_comment', json={})
    assert still_open.status_code == 400

    cross_read = anon.post(
        '/api/shopping_list/items',
        json={'name': 'From read key', 'store': 'aldi'},
        headers={**_bearer(read_key), 'Origin': 'https://evil.example'},
    )
    assert cross_read.status_code == 403
    cross_write = anon.post(
        '/api/shopping_list/items',
        json={'name': 'From write key', 'store': 'woolworths'},
        headers={**_bearer(write_key), 'Origin': 'https://evil.example'},
    )
    assert cross_write.status_code == 200
    assert cross_write.get_json()['item']['store'] == 'woolworths'
    session_add = _session().post('/api/shopping_list/items', json={'name': 'From the browser', 'store': 'aldi'})
    assert session_add.status_code == 200


def test_audit_line_records_the_write_without_the_key(api_keys, capsys):
    app.config['TESTING'] = True
    _read_key, write_key = api_keys
    capsys.readouterr()
    response = _anon().post(
        '/api/notes/cards',
        json={'text': f'Audit {uuid.uuid4().hex[:6]}'},
        headers=_bearer(write_key),
    )
    assert response.status_code == 200
    output = capsys.readouterr().out
    assert 'method=POST' in output
    assert 'path=/api/notes/cards' in output
    assert 'key_type=write' in output
    assert 'at=' in output
    assert 'status=200' in output
    assert write_key not in output


def test_missing_or_short_write_key_cannot_change_data(monkeypatch):
    app.config['TESTING'] = True
    monkeypatch.delenv('CR_WRITE_API_KEY', raising=False)
    monkeypatch.setenv('CR_READONLY_API_KEY', READ_KEY)
    client = _anon()
    missing = client.post('/api/notes/cards', json={'text': 'No write key'}, headers=_bearer('w' * 40))
    assert missing.status_code == 401
    assert missing.get_json()['error'] == 'Invalid API key'
    still_reads = client.get('/api/notes', headers=_bearer(READ_KEY))
    assert still_reads.status_code == 200

    monkeypatch.setenv('CR_WRITE_API_KEY', 'short-key')
    short = client.post('/api/notes/cards', json={'text': 'Short'}, headers=_bearer('short-key'))
    assert short.status_code == 401
    assert client.get('/api/dashboard_notes', headers=_bearer(READ_KEY)).status_code == 200
