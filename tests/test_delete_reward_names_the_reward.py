"""Deleting a reward should name that reward in the confirmation."""

import uuid
from datetime import datetime

from app import app, db
from models import Person, Reward


def _last_function(html, name):
    marker = 'function {}'.format(name)
    start = html.rfind(marker)
    assert start != -1, name
    next_fn = html.find('\nfunction ', start + len(marker))
    assert next_fn != -1
    return html[start:next_fn]


def test_delete_confirm_names_the_reward():
    app.config['TESTING'] = True
    client = app.test_client()
    suffix = uuid.uuid4().hex[:6]
    available_title = 'Ice cream {}'.format(suffix)
    redeemed_title = 'Movie night {}'.format(suffix)
    created_people = []
    created_rewards = []
    with app.app_context():
        person = Person(name='Reward Delete {}'.format(suffix), points=10, bonus_points=0)
        db.session.add(person)
        db.session.commit()
        created_people.append(person.id)
        available = Reward(
            title=available_title,
            points_required=5,
            assigned_to_id=person.id,
            assigned_to=person.name,
            completed=False,
        )
        redeemed = Reward(
            title=redeemed_title,
            points_required=20,
            assigned_to_id=person.id,
            assigned_to=person.name,
            completed=True,
            date_completed=datetime(2026, 9, 1, 18, 30),
        )
        db.session.add(available)
        db.session.add(redeemed)
        db.session.commit()
        created_rewards.extend([available.id, redeemed.id])

    try:
        html = client.get('/').get_data(as_text=True)
        assert 'data-title="{}"'.format(available_title) in html
        assert 'data-title="{}"'.format(redeemed_title) in html
        live = _last_function(html, 'confirmDeleteReward')
        assert 'rewardTitleFromCard' in live
        assert "querySelector('.reward-title')" not in live
        helper = _last_function(html, 'rewardTitleFromCard')
        assert "getAttribute('data-title')" in helper
        assert '.reward-title-modern' in helper
        assert 'this reward' in helper
    finally:
        with app.app_context():
            for reward_id in created_rewards:
                reward = db.session.get(Reward, reward_id)
                if reward:
                    db.session.delete(reward)
            for person_id in created_people:
                person = db.session.get(Person, person_id)
                if person:
                    db.session.delete(person)
            db.session.commit()
