"""Family data stays behind the session, and the padlock is enforced on the server."""

import os
import uuid
from datetime import date, timedelta

import bcrypt

from app import app, db
from models import AppSetting, OrganiseItem, Person


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


def _clear_lockout():
    path = os.path.join(app.instance_path, 'pin_attempts.json')
    if os.path.exists(path):
        os.remove(path)


def test_stranger_cannot_read_family_apis_or_the_page():
    app.config['TESTING'] = True
    name = f'Holiday Secret {uuid.uuid4().hex[:8]}'
    with app.app_context():
        person = Person(name=name, points=3, bonus_points=0)
        db.session.add(person)
        db.session.commit()
        person_id = person.id
    try:
        stranger = _anon()
        for path in (
            '/api/shopping_list',
            '/api/meal_planner',
            '/api/notes',
            '/api/dashboard_notes',
            '/api/notifications',
            '/api/organise',
            '/api/auth_status',
            '/completed_chores_fragment',
        ):
            response = stranger.get(path)
            assert response.status_code == 401, path
            body = response.get_data(as_text=True)
            assert name not in body
            assert response.get_json()['error'] == 'Login required'

        page = stranger.get('/')
        assert page.status_code == 200
        html = page.get_data(as_text=True)
        assert 'data-login-shell="1"' in html
        assert name not in html
        assert 'master-pin-input' in html

        styles = stranger.get('/static/css/styles.css')
        assert styles.status_code == 200
        upload = stranger.get('/static/uploads/not-a-real-photo.png')
        assert upload.status_code == 401

        home = _session(adult=False).get('/')
        assert home.status_code == 200
        assert name in home.get_data(as_text=True)
        assert 'data-login-shell' not in home.get_data(as_text=True)

        listed = _session(adult=False).get('/api/shopping_list')
        assert listed.status_code == 200
        assert listed.get_json()['success'] is True
    finally:
        with app.app_context():
            person = db.session.get(Person, person_id)
            if person:
                db.session.delete(person)
            db.session.commit()


def test_stranger_gets_401_and_a_child_cannot_run_adult_actions():
    app.config['TESTING'] = True
    with app.app_context():
        person = Person(name=f'Keep {uuid.uuid4().hex[:8]}', points=4, bonus_points=0)
        db.session.add(person)
        db.session.commit()
        person_id = person.id
    try:
        stranger = _anon()
        for path, payload in (
            ('/delete_person', {'person_id': person_id}),
            ('/reset_points', {'person_id': person_id, 'new_points': 0}),
            ('/add_chore', {'title': 'Sneaky', 'assigned_to': 'Nobody', 'points': 1}),
            ('/delete_chore', {'chore_id': 1, 'permanent': True}),
            ('/award_bonus_points', {'person_id': person_id, 'bonus_points': 1}),
        ):
            response = stranger.post(path, json=payload)
            assert response.status_code == 401, path

        child = _session(adult=False)
        denied = child.post('/delete_person', json={'person_id': person_id})
        assert denied.status_code == 403
        points = child.post('/reset_points', json={'person_id': person_id, 'new_points': 0})
        assert points.status_code == 403
        with app.app_context():
            saved = db.session.get(Person, person_id)
            assert saved is not None
            assert saved.points == 4

        settings = child.get('/settings')
        assert settings.status_code == 302
    finally:
        with app.app_context():
            person = db.session.get(Person, person_id)
            if person:
                db.session.delete(person)
            db.session.commit()


def test_child_session_does_not_receive_admin_only_alerts():
    app.config['TESTING'] = True
    title = f'Rego leak {uuid.uuid4().hex[:8]}'
    with app.app_context():
        item = OrganiseItem(
            category='Car',
            title=title,
            due_date=date.today() + timedelta(days=2),
            reminder_days=30,
            paid=False,
            vehicle_rego='SECRET1',
        )
        db.session.add(item)
        db.session.commit()
        item_id = item.id
    try:
        child = _session(adult=False).get('/api/notifications')
        assert child.status_code == 200
        child_blob = child.get_data(as_text=True)
        assert title not in child_blob
        assert 'SECRET1' not in child_blob

        adult = _session(adult=True).get('/api/notifications')
        assert adult.status_code == 200
        assert title in adult.get_data(as_text=True)
    finally:
        with app.app_context():
            item = db.session.get(OrganiseItem, item_id)
            if item:
                db.session.delete(item)
            db.session.commit()


def test_login_accepts_the_existing_pin_and_a_longer_passphrase():
    app.config['TESTING'] = True
    _clear_lockout()
    with app.app_context():
        original = AppSetting.get('master_pin')
    try:
        with app.app_context():
            AppSetting.set('master_pin', bcrypt.hashpw(b'1234', bcrypt.gensalt()).decode('utf-8'))
        client = _anon()
        wrong = client.post('/api/login', json={'pin': '0000'})
        assert wrong.status_code == 401
        assert client.get('/api/shopping_list').status_code == 401

        right = client.post('/api/login', json={'pin': '1234'})
        assert right.status_code == 200
        assert right.get_json()['success'] is True
        assert client.get('/api/check_auth').get_json()['authenticated'] is True
        assert client.get('/api/notes').status_code == 200

        _clear_lockout()
        with app.app_context():
            AppSetting.set(
                'master_pin',
                bcrypt.hashpw('correct horse'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8'),
            )
        phrase_client = _anon()
        phrase = phrase_client.post('/api/login', json={'pin': 'correct horse'})
        assert phrase.status_code == 200
        assert phrase.get_json()['success'] is True
    finally:
        _clear_lockout()
        with app.app_context():
            if original:
                AppSetting.set('master_pin', original)
            else:
                row = AppSetting.query.filter_by(key='master_pin').first()
                if row:
                    db.session.delete(row)
                    db.session.commit()


def test_login_locks_out_after_repeated_failures():
    app.config['TESTING'] = True
    _clear_lockout()
    with app.app_context():
        original = AppSetting.get('master_pin')
        AppSetting.set('master_pin', bcrypt.hashpw(b'1234', bcrypt.gensalt()).decode('utf-8'))
    try:
        client = _anon()
        statuses = [
            client.post('/api/login', json={'pin': '9999'}).status_code
            for _ in range(3)
        ]
        assert statuses[:2] == [401, 401]
        assert statuses[2] == 429
        locked = client.post('/api/login', json={'pin': '1234'})
        assert locked.status_code == 429
        assert locked.get_json()['retry_after']
    finally:
        _clear_lockout()
        with app.app_context():
            if original:
                AppSetting.set('master_pin', original)
            else:
                row = AppSetting.query.filter_by(key='master_pin').first()
                if row:
                    db.session.delete(row)
                    db.session.commit()


def test_person_without_a_pin_cannot_open_a_session():
    app.config['TESTING'] = True
    _clear_lockout()
    with app.app_context():
        person = Person(name=f'No Pin {uuid.uuid4().hex[:8]}', points=0, bonus_points=0, is_admin=False)
        db.session.add(person)
        db.session.commit()
        person_id = person.id
    try:
        client = _anon()
        response = client.post('/api/person_login', json={'person_id': person_id, 'pin': ''})
        assert response.status_code == 401
        assert client.get('/api/check_auth').get_json()['authenticated'] is False
    finally:
        _clear_lockout()
        with app.app_context():
            person = db.session.get(Person, person_id)
            if person:
                db.session.delete(person)
            db.session.commit()


def test_cross_site_post_is_rejected_and_the_cookie_is_hardened():
    app.config['TESTING'] = True
    _clear_lockout()
    with app.app_context():
        original = AppSetting.get('master_pin')
        AppSetting.set('master_pin', bcrypt.hashpw(b'1234', bcrypt.gensalt()).decode('utf-8'))
        person = Person(name=f'Csrf {uuid.uuid4().hex[:8]}', points=1, bonus_points=0)
        db.session.add(person)
        db.session.commit()
        person_id = person.id
    try:
        client = _anon()
        logged_in = client.post(
            '/api/login',
            json={'pin': '1234'},
            headers={'X-Forwarded-Proto': 'https'},
        )
        assert logged_in.status_code == 200
        cookie = logged_in.headers.get('Set-Cookie', '')
        assert 'HttpOnly' in cookie
        assert 'SameSite=Lax' in cookie
        assert 'Secure' in cookie

        blocked = client.post(
            '/delete_person',
            json={'person_id': person_id},
            headers={'Origin': 'https://evil.example'},
        )
        assert blocked.status_code == 403
        with app.app_context():
            assert db.session.get(Person, person_id) is not None

        allowed = client.post(
            '/delete_person',
            json={'person_id': person_id},
            headers={'Origin': 'http://localhost'},
        )
        assert allowed.status_code == 200
    finally:
        _clear_lockout()
        with app.app_context():
            person = db.session.get(Person, person_id)
            if person:
                db.session.delete(person)
            if original:
                AppSetting.set('master_pin', original)
            else:
                row = AppSetting.query.filter_by(key='master_pin').first()
                if row:
                    db.session.delete(row)
            db.session.commit()
