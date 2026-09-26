from flask import Flask
from extensions import db
import mimetypes
import os
import secrets

mimetypes.add_type('video/mp4', '.mp4')
mimetypes.add_type('video/mp4', '.m4v')
mimetypes.add_type('video/webm', '.webm')
mimetypes.add_type('video/quicktime', '.mov')
mimetypes.add_type('video/ogg', '.ogv')

# Initialize Flask app
app = Flask(__name__)


def _load_secret_key(flask_app):
    """Return the Flask session signing key, without publishing it.

    The key used to be a literal in this file. Because it is committed here,
    every deployment of ChoresRewards shared the same one, and anyone could
    forge a signed session cookie for any instance. Now:

      1. CR_SECRET_KEY / SECRET_KEY from the environment, if set. This is what
         you want when running more than one process or container, since they
         all have to agree on the key.
      2. Otherwise a random key generated on first boot and persisted in the
         instance folder, next to the database. Existing installs keep working
         with no configuration, and sessions survive restarts.

    Generating without persisting would log everyone out on every restart, so
    the file is written atomically and re-read afterwards: with several workers
    starting at once, whichever wins os.replace is the key they all use.
    """
    env_key = os.environ.get('CR_SECRET_KEY') or os.environ.get('SECRET_KEY')
    if env_key:
        return env_key

    os.makedirs(flask_app.instance_path, exist_ok=True)
    key_path = os.path.join(flask_app.instance_path, 'secret_key')
    try:
        with open(key_path, 'r', encoding='utf-8') as fh:
            existing = fh.read().strip()
        if existing:
            return existing
    except OSError:
        pass

    generated = secrets.token_hex(32)
    tmp_path = '{}.{}.tmp'.format(key_path, os.getpid())
    try:
        with open(tmp_path, 'w', encoding='utf-8') as fh:
            fh.write(generated)
        os.chmod(tmp_path, 0o600)
        os.replace(tmp_path, key_path)
        with open(key_path, 'r', encoding='utf-8') as fh:
            return fh.read().strip() or generated
    except OSError:
        # Read-only instance folder: still better than a published constant,
        # at the cost of sessions not surviving a restart.
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        return generated


app.secret_key = _load_secret_key(app)
# Configure SQLite database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'  # Add this line
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB cap so oversized uploads get a clean error instead of a dropped connection

from flask import jsonify as _jsonify

@app.errorhandler(413)
def _handle_too_large(e):
    return _jsonify({'success': False, 'error': 'Upload too large. Please upload fewer/smaller files at once.'}), 413

db.init_app(app)  # Initialize db with the app

# Import routes after app is created (to avoid circular imports)

# Import quiz questions
import sys
import os
quiz_path = os.path.join(os.path.dirname(__file__), 'quiz_questions.py')
if quiz_path not in sys.path:
    sys.path.append(os.path.dirname(__file__))
from quiz_questions import quiz_questions

from routes import routes_bp


# Register the Blueprint

# Main route: pass quiz_questions to template

app.register_blueprint(routes_bp)

# Create database tables
with app.app_context():
    db.create_all()
    # Safe migration: add age column to person table if it doesn't exist
    from sqlalchemy import inspect, text
    inspector = inspect(db.engine)
    existing_columns = [col['name'] for col in inspector.get_columns('person')]
    if 'age' not in existing_columns:
        db.session.execute(text('ALTER TABLE person ADD COLUMN age INTEGER'))
        db.session.commit()
        # One-time data migration from person_ages.json
        import json as _json, os as _os
        age_file = _os.path.join(_os.path.dirname(__file__), 'person_ages.json')
        if _os.path.exists(age_file):
            from models import Person
            with open(age_file) as f:
                ages = _json.load(f)
            for person in Person.query.all():
                age_val = ages.get(str(person.id))
                if age_val is not None:
                    person.age = int(age_val)
            db.session.commit()

    # Safe migration: add vehicle and photo columns to organise_item
    if 'organise_item' in inspector.get_table_names():
        org_cols = [col['name'] for col in inspector.get_columns('organise_item')]
        _org_new = [
            ('photo_filename', 'VARCHAR(255)'),
            ('vehicle_make', 'VARCHAR(100)'),
            ('vehicle_model', 'VARCHAR(100)'),
            ('vehicle_year', 'INTEGER'),
            ('vehicle_rego', 'VARCHAR(20)'),
            ('current_odometer', 'INTEGER'),
            ('next_service_date', 'DATE'),
            ('next_service_mileage', 'INTEGER'),
            ('parent_id', 'INTEGER'),
        ]
        _org_changed = False
        for _cn, _ct in _org_new:
            if _cn not in org_cols:
                db.session.execute(text(f'ALTER TABLE organise_item ADD COLUMN {_cn} {_ct}'))
                _org_changed = True
        if _org_changed:
            db.session.commit()

    # Safe migration: add next_service_date and next_service_mileage to vehicle_service
    if 'vehicle_service' in inspector.get_table_names():
        svc_cols = [col['name'] for col in inspector.get_columns('vehicle_service')]
        _svc_new = [
            ('next_service_date', 'DATE'),
            ('next_service_mileage', 'INTEGER'),
        ]
        _svc_changed = False
        for _cn, _ct in _svc_new:
            if _cn not in svc_cols:
                db.session.execute(text(f'ALTER TABLE vehicle_service ADD COLUMN {_cn} {_ct}'))
                _svc_changed = True
        if _svc_changed:
            db.session.commit()

    # Safe migration: add icon column to chore table
    if 'chore' in inspector.get_table_names():
        chore_cols = [col['name'] for col in inspector.get_columns('chore')]
        if 'icon' not in chore_cols:
            db.session.execute(text('ALTER TABLE chore ADD COLUMN icon VARCHAR(20)'))
            db.session.commit()
        if 'is_extra' not in chore_cols:
            db.session.execute(text('ALTER TABLE chore ADD COLUMN is_extra BOOLEAN DEFAULT 0'))
            db.session.commit()
        if 'extra_id' not in chore_cols:
            db.session.execute(text('ALTER TABLE chore ADD COLUMN extra_id VARCHAR(32)'))
            db.session.commit()

    # Clear stale upload references: null any avatar/image_url that points to a
    # file that no longer exists on disk (happens after container rebuilds when
    # the uploads volume is not yet mapped).
    import os as _os
    from models import Person, Reward
    upload_folder = _os.path.join(app.root_path, 'static', 'uploads')
    changed = 0
    for person in Person.query.all():
        if person.avatar and person.avatar != 'default_avatar.png':
            path = _os.path.join(upload_folder, person.avatar)
            if not _os.path.exists(path):
                person.avatar = None
                changed += 1
    for reward in Reward.query.all():
        if reward.image_url and reward.image_url.startswith('/static/uploads/'):
            filename = reward.image_url.split('/static/uploads/')[-1]
            path = _os.path.join(upload_folder, filename)
            if not _os.path.exists(path):
                reward.image_url = None
                changed += 1
    if changed:
        db.session.commit()
        print(f"[startup] Cleared {changed} stale upload reference(s) from DB.")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000)
