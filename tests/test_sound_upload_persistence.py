"""Uploaded celebration sounds must live on the uploads volume, not in the image."""

import io
import json
import os

from app import app
from routes import _bundled_sounds_dir, _custom_sounds_dir, _hidden_sounds_path

FILENAME = 'persist-test-tone.mp3'


def _cleanup_custom():
    path = os.path.join(_custom_sounds_dir(), FILENAME)
    if os.path.isfile(path):
        os.remove(path)


def test_upload_sound_is_stored_on_uploads_volume():
    client = app.test_client()
    hidden_path = None
    hidden_before = None
    try:
        with app.app_context():
            hidden_path = _hidden_sounds_path()
            if os.path.isfile(hidden_path):
                with open(hidden_path, 'r', encoding='utf-8') as f:
                    hidden_before = f.read()
            bundled = os.path.join(_bundled_sounds_dir(), FILENAME)
            custom = os.path.join(_custom_sounds_dir(), FILENAME)
            assert not os.path.isfile(bundled)

        response = client.post(
            '/api/sounds/upload',
            data={'sound_file': (io.BytesIO(b'not-a-real-mp3'), FILENAME)},
            content_type='multipart/form-data',
        )
        body = response.get_json()
        assert response.status_code == 200
        assert body['success'] is True
        assert body['url'] == '/static/uploads/sounds/' + FILENAME

        with app.app_context():
            assert os.path.isfile(os.path.join(_custom_sounds_dir(), FILENAME))
            assert not os.path.isfile(os.path.join(_bundled_sounds_dir(), FILENAME))

        listed = client.get('/api/sounds').get_json()
        match = [s for s in listed['sounds'] if s['name'] == FILENAME]
        assert len(match) == 1
        assert match[0]['url'] == '/static/uploads/sounds/' + FILENAME
        assert match[0]['custom'] is True

        deleted = client.post('/api/sounds/delete', json={'filename': FILENAME})
        assert deleted.get_json()['success'] is True
        with app.app_context():
            assert not os.path.isfile(os.path.join(_custom_sounds_dir(), FILENAME))

        listed_after = client.get('/api/sounds').get_json()
        assert all(s['name'] != FILENAME for s in listed_after['sounds'])
    finally:
        with app.app_context():
            _cleanup_custom()
            if hidden_path and hidden_before is None and os.path.isfile(hidden_path):
                os.remove(hidden_path)
            elif hidden_path and hidden_before is not None:
                with open(hidden_path, 'w', encoding='utf-8') as f:
                    f.write(hidden_before)


def test_hiding_a_bundled_sound_survives_without_deleting_the_file():
    client = app.test_client()
    bundled_name = 'lion-roar.mp3'
    with app.app_context():
        bundled_path = os.path.join(_bundled_sounds_dir(), bundled_name)
        hidden_path = _hidden_sounds_path()
        assert os.path.isfile(bundled_path)
        hidden_before = None
        if os.path.isfile(hidden_path):
            with open(hidden_path, 'r', encoding='utf-8') as f:
                hidden_before = f.read()
    try:
        deleted = client.post('/api/sounds/delete', json={'filename': bundled_name})
        assert deleted.get_json()['success'] is True
        with app.app_context():
            assert os.path.isfile(os.path.join(_bundled_sounds_dir(), bundled_name))
            with open(_hidden_sounds_path(), 'r', encoding='utf-8') as f:
                hidden = json.load(f)
            assert bundled_name in hidden
        listed = client.get('/api/sounds').get_json()
        assert all(s['name'] != bundled_name for s in listed['sounds'])

        escaped = client.post(
            '/api/sounds/delete',
            json={'filename': '../instance/database.db'},
        )
        assert escaped.status_code == 400
    finally:
        with app.app_context():
            hidden_path = _hidden_sounds_path()
            if hidden_before is None:
                if os.path.isfile(hidden_path):
                    os.remove(hidden_path)
            else:
                with open(hidden_path, 'w', encoding='utf-8') as f:
                    f.write(hidden_before)
