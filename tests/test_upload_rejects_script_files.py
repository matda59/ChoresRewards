"""Public uploads must not store or serve a script.

Reward images used to keep the caller's filename, so shell.php and
shell.php.jpg were written under static/uploads and could be fetched.
Gunicorn does not run PHP, but that file is still a script sitting in the
web root. Image uploads now keep a generated name and an allowlisted
extension, and the uploads tree refuses to serve a script name.
"""

import gc
import io
import os
import time
import uuid

from app import app, db
from models import ActivityLog, Reward


def _remove_file(path):
    """OneDrive can briefly lock a file that was just served."""
    for _ in range(20):
        try:
            if os.path.isfile(path):
                os.remove(path)
            return
        except PermissionError:
            gc.collect()
            time.sleep(0.1)
    if os.path.isfile(path):
        os.remove(path)


def _adult_client():
    app.config['TESTING'] = True
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['authenticated'] = True
        sess['adult_mode'] = True
    return client


def _post_reward_image(client, filename, body=b'<?php echo 1; ?>'):
    return client.post(
        '/add_reward',
        data={
            'title': f'Script reward {uuid.uuid4().hex[:8]}',
            'points_required': '5',
            'assigned_to': 'Nobody',
            'reward_image_file': (io.BytesIO(body), filename),
        },
        content_type='multipart/form-data',
    )


def _cleanup_reward(title):
    with app.app_context():
        for reward in Reward.query.filter_by(title=title).all():
            if reward.image_url and reward.image_url.startswith('/static/uploads/'):
                relative = reward.image_url.split('/static/', 1)[-1].split('?', 1)[0]
                path = os.path.join(app.root_path, 'static', relative.replace('/', os.sep))
                if os.path.isfile(path):
                    os.remove(path)
            db.session.delete(reward)
        for row in ActivityLog.query.filter(ActivityLog.description.contains(title)).all():
            db.session.delete(row)
        db.session.commit()


def test_reward_upload_rejects_a_php_file():
    client = _adult_client()
    response = _post_reward_image(client, 'shell.php')
    assert response.status_code == 400
    assert response.get_json()['success'] is False
    planted = os.path.join(app.root_path, 'static', 'uploads', 'rewards', 'shell.php')
    assert not os.path.isfile(planted)


def test_reward_upload_rejects_a_php_suffix_hidden_before_an_image_extension():
    client = _adult_client()
    response = _post_reward_image(client, 'shell.php.jpg')
    assert response.status_code == 400
    folder = os.path.join(app.root_path, 'static', 'uploads', 'rewards')
    if os.path.isdir(folder):
        assert all('shell.php' not in name for name in os.listdir(folder))


def test_reward_upload_stores_a_png_under_a_generated_name():
    client = _adult_client()
    title = f'Picnic {uuid.uuid4().hex[:8]}'
    try:
        response = client.post(
            '/add_reward',
            data={
                'title': title,
                'points_required': '5',
                'assigned_to': 'Nobody',
                'reward_image_file': (io.BytesIO(b'\x89PNG\r\n'), 'family photo.php.png'),
            },
            content_type='multipart/form-data',
        )
        # The .php segment is rejected even though the name ends in .png.
        assert response.status_code == 400

        response = client.post(
            '/add_reward',
            data={
                'title': title,
                'points_required': '5',
                'assigned_to': 'Nobody',
                'reward_image_file': (io.BytesIO(b'\x89PNG\r\n'), 'family photo.png'),
            },
            content_type='multipart/form-data',
        )
        assert response.status_code in (302, 303)
        with app.app_context():
            reward = Reward.query.filter_by(title=title).one()
            assert reward.image_url.startswith('/static/uploads/rewards/reward_')
            assert reward.image_url.endswith('.png')
            assert 'family' not in reward.image_url
            relative = reward.image_url.split('/static/', 1)[-1]
            stored = os.path.join(app.root_path, 'static', relative.replace('/', os.sep))
            assert os.path.isfile(stored)
    finally:
        _cleanup_reward(title)


def test_editing_a_reward_image_rejects_php():
    client = _adult_client()
    title = f'Edit me {uuid.uuid4().hex[:8]}'
    with app.app_context():
        reward = Reward(title=title, points_required=1, assigned_to='Nobody', completed=False)
        db.session.add(reward)
        db.session.commit()
        reward_id = reward.id
    try:
        response = client.post(
            '/edit_reward_image',
            data={
                'reward_id': str(reward_id),
                'image': (io.BytesIO(b'<?php echo 1; ?>'), 'shell.phtml'),
            },
            content_type='multipart/form-data',
        )
        assert response.status_code == 400
        with app.app_context():
            assert db.session.get(Reward, reward_id).image_url is None
        upload_root = os.path.join(app.root_path, 'static', 'uploads')
        assert not os.path.isfile(os.path.join(upload_root, 'shell.phtml'))
    finally:
        _cleanup_reward(title)


def test_sound_upload_rejects_a_php_suffix():
    client = _adult_client()
    filename = f'cmd.php.{uuid.uuid4().hex[:6]}.mp3'
    response = client.post(
        '/api/sounds/upload',
        data={'sound_file': (io.BytesIO(b'not-audio'), filename)},
        content_type='multipart/form-data',
    )
    assert response.status_code == 400
    stored = os.path.join(app.root_path, 'static', 'uploads', 'sounds', filename)
    assert not os.path.isfile(stored)


def test_uploads_tree_does_not_serve_a_script_that_is_already_on_disk():
    client = app.test_client()
    folder = os.path.join(app.root_path, 'static', 'uploads')
    os.makedirs(folder, exist_ok=True)
    php_name = f'planted-{uuid.uuid4().hex}.php'
    html_name = f'planted-{uuid.uuid4().hex}.html'
    double_name = f'planted-{uuid.uuid4().hex}.php.jpg'
    png_name = f'planted-{uuid.uuid4().hex}.png'
    ini_name = '.user.ini'
    paths = []
    ini_path = os.path.join(folder, ini_name)
    ini_before = None
    if os.path.isfile(ini_path):
        with open(ini_path, 'rb') as handle:
            ini_before = handle.read()
    try:
        for name, body in (
            (php_name, b'<?php echo 1; ?>'),
            (html_name, b'<script>alert(1)</script>'),
            (double_name, b'<?php echo 1; ?>'),
            (png_name, b'\x89PNG\r\n'),
            (ini_name, b'auto_prepend_file=shell.php'),
        ):
            path = os.path.join(folder, name)
            with open(path, 'wb') as handle:
                handle.write(body)
            paths.append(path)

        for name in (php_name, html_name, double_name, ini_name):
            response = client.get('/static/uploads/' + name)
            body = response.get_data()
            status = response.status_code
            response.close()
            assert status == 404
            assert b'<?php' not in body
            assert b'auto_prepend_file' not in body
            assert b'<script>' not in body

        image = client.get('/static/uploads/' + png_name)
        image_body = image.get_data()
        image_status = image.status_code
        image.close()
        assert image_status == 200
        assert image_body.startswith(b'\x89PNG')

        icon = client.get('/static/images/rewards/reward_movie.svg')
        assert icon.status_code == 200
        icon.close()
    finally:
        for path in paths:
            if path == ini_path:
                continue
            _remove_file(path)
        if ini_before is None:
            _remove_file(ini_path)
        else:
            with open(ini_path, 'wb') as handle:
                handle.write(ini_before)
