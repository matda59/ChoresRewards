"""Locked and anonymous sessions must not destroy household data.

The sound delete route joined the caller-supplied name onto the sounds folder.
An absolute path made that join ignore the folder and delete the path itself.
Daily-chore maintenance and the settings forms also trusted a child session,
so a kid logged in without adult mode could erase a repeating chore or mark
themselves as an adult.
"""

import os
import tempfile
import uuid

from app import app, db
from models import Chore, Person


def _person(name_prefix):
    person = Person(
        name=f'{name_prefix} {uuid.uuid4().hex[:8]}',
        points=0,
        bonus_points=0,
        is_admin=False,
    )
    db.session.add(person)
    db.session.commit()
    return person


def _daily_chore(person):
    chore = Chore(
        title='Make bed',
        assigned_to=person.name,
        assigned_to_id=person.id,
        points=1,
        is_daily=True,
        completed=False,
        deleted=False,
    )
    db.session.add(chore)
    db.session.commit()
    return chore


def test_sound_delete_cannot_remove_a_file_outside_the_sounds_folder():
    app.config['TESTING'] = True
    client = app.test_client()
    fd, sentinel = tempfile.mkstemp(prefix='cr-sentinel-')
    os.write(fd, b'keep-me')
    os.close(fd)
    try:
        anonymous = client.post('/api/sounds/delete', json={'filename': sentinel})
        assert anonymous.status_code == 403
        assert os.path.exists(sentinel)

        with client.session_transaction() as sess:
            sess['authenticated'] = True
            sess['adult_mode'] = True
        escaped = client.post('/api/sounds/delete', json={'filename': sentinel})
        assert escaped.status_code == 404
        assert os.path.exists(sentinel)

        relative = os.path.relpath(sentinel, os.path.join(app.root_path, 'static', 'sounds'))
        traversed = client.post('/api/sounds/delete', json={'filename': relative})
        assert traversed.status_code == 404
        assert os.path.exists(sentinel)
    finally:
        if os.path.exists(sentinel):
            os.remove(sentinel)


def test_adult_can_still_delete_a_sound_inside_the_folder():
    app.config['TESTING'] = True
    client = app.test_client()
    sounds_dir = os.path.join(app.root_path, 'static', 'sounds')
    os.makedirs(sounds_dir, exist_ok=True)
    filename = f'test-keep-{uuid.uuid4().hex[:8]}.mp3'
    path = os.path.join(sounds_dir, filename)
    with open(path, 'wb') as handle:
        handle.write(b'not-audio')
    try:
        with client.session_transaction() as sess:
            sess['adult_mode'] = True
        denied = app.test_client().post('/api/sounds/delete', json={'filename': filename})
        assert denied.status_code == 403
        assert os.path.exists(path)

        removed = client.post('/api/sounds/delete', json={'filename': filename})
        assert removed.status_code == 200
        assert removed.get_json()['success'] is True
        assert not os.path.exists(path)
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_anonymous_upload_of_a_sound_is_rejected():
    app.config['TESTING'] = True
    client = app.test_client()
    response = client.post('/api/sounds/upload', data={})
    assert response.status_code == 403


def test_child_session_cannot_permanently_delete_a_daily_chore():
    app.config['TESTING'] = True
    client = app.test_client()
    with app.app_context():
        person = _person('Chore Kid')
        chore = _daily_chore(person)
        person_id, chore_id = person.id, chore.id
    try:
        anonymous = client.post('/delete_daily_chore', json={'chore_id': chore_id})
        assert anonymous.status_code == 403
        with app.app_context():
            assert db.session.get(Chore, chore_id).deleted is False

        with client.session_transaction() as sess:
            sess['authenticated'] = True
            sess['adult_mode'] = False
        child = client.post('/delete_daily_chore', json={'chore_id': chore_id})
        assert child.status_code == 403
        with app.app_context():
            assert db.session.get(Chore, chore_id).deleted is False

        with client.session_transaction() as sess:
            sess['adult_mode'] = True
        adult = client.post('/delete_daily_chore', json={'chore_id': chore_id})
        assert adult.status_code == 200
        assert adult.get_json()['success'] is True
        with app.app_context():
            assert db.session.get(Chore, chore_id).deleted is True
    finally:
        with app.app_context():
            chore = db.session.get(Chore, chore_id)
            if chore:
                db.session.delete(chore)
            person = db.session.get(Person, person_id)
            if person:
                db.session.delete(person)
            db.session.commit()


def test_child_session_cannot_open_settings_or_promote_themselves():
    app.config['TESTING'] = True
    client = app.test_client()
    with app.app_context():
        person = _person('Promote Kid')
        person_id = person.id
    try:
        with client.session_transaction() as sess:
            sess['authenticated'] = True
            sess['adult_mode'] = False
        page = client.get('/settings')
        assert page.status_code == 302

        promoted = client.post('/settings', data={
            'toggle_admin': '1',
            'person_id': str(person_id),
            'is_admin': 'true',
        })
        assert promoted.status_code == 302
        with app.app_context():
            assert db.session.get(Person, person_id).is_admin is False

        with client.session_transaction() as sess:
            sess['adult_mode'] = True
        adult_page = client.get('/settings')
        assert adult_page.status_code == 200
        adult_promote = client.post('/settings', data={
            'toggle_admin': '1',
            'person_id': str(person_id),
            'is_admin': 'true',
        })
        assert adult_promote.status_code == 200
        with app.app_context():
            assert db.session.get(Person, person_id).is_admin is True
    finally:
        with app.app_context():
            person = db.session.get(Person, person_id)
            if person:
                db.session.delete(person)
            db.session.commit()
