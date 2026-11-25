"""The kanban Adjust control must be a real button, only in Tech Time mode.

The first version put {{ name|tojson }} inside a double-quoted onclick. The
browser ended the handler at the name, so the click threw and nothing opened.
"""

import uuid

from app import app, db
from models import AppSetting, Person


def _adult():
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['authenticated'] = True
        sess['adult_mode'] = True
    return client


def test_tech_time_adjust_button_is_clickable_and_points_mode_hides_it():
    app.config['TESTING'] = True
    client = _adult()
    suffix = uuid.uuid4().hex[:8]
    name = "O'Brien {}".format(suffix)
    with app.app_context():
        saved = AppSetting.get('reward_system')
        AppSetting.set_reward_system('tech_time')
        person = Person(name=name, points=3, bonus_points=0)
        db.session.add(person)
        db.session.commit()
        person_id = person.id
    try:
        page = client.get('/').get_data(as_text=True)
        assert 'tech_time_adjust.js' in page
        assert 'onclick="adjustTechTime' not in page
        assert 'data-person-id="{}"'.format(person_id) in page
        assert 'data-person-name="{}"'.format(name.replace("'", '&#39;')) in page or (
            'data-person-name="{}"'.format(name) in page
        )
        assert 'class="admin-only adjust-tech-time-btn"' in page
        assert 'data-tech-minutes-for="{}"'.format(person_id) in page

        settings = client.get('/settings').get_data(as_text=True)
        assert 'tech_time_adjust.js' in settings
        assert 'onclick="adjustTechTime' not in settings
        assert 'class="adjust-tech-time-btn"' in settings

        with app.app_context():
            AppSetting.set_reward_system('points')
        points_page = client.get('/').get_data(as_text=True)
        assert 'adjust-tech-time-btn' not in points_page
        cash = client.get('/settings')
        with app.app_context():
            AppSetting.set_reward_system('cash')
        cash_page = client.get('/').get_data(as_text=True)
        assert 'adjust-tech-time-btn' not in cash_page
        assert cash.status_code == 200
    finally:
        with app.app_context():
            row = db.session.get(Person, person_id)
            if row:
                db.session.delete(row)
            if saved is None:
                setting = AppSetting.query.filter_by(key='reward_system').first()
                if setting:
                    db.session.delete(setting)
            else:
                AppSetting.set('reward_system', saved)
            db.session.commit()
