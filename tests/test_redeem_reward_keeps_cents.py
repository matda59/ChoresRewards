"""Redeeming a reward should use the full cost, including cents."""

import uuid

from app import app, db
from models import Person, Reward


def _last_function(html, name):
    marker = 'function {}'.format(name)
    start = html.rfind(marker)
    assert start != -1, name
    next_fn = html.find('\nfunction ', start + len(marker))
    assert next_fn != -1
    return html[start:next_fn]


def test_redeem_confirm_reads_the_full_cost():
    app.config['TESTING'] = True
    client = app.test_client()
    suffix = uuid.uuid4().hex[:6]
    title = 'Ice cream {}'.format(suffix)
    created_people = []
    created_rewards = []
    with app.app_context():
        person = Person(name='Redeem Cents {}'.format(suffix), points=2, bonus_points=0)
        db.session.add(person)
        db.session.commit()
        created_people.append(person.id)
        reward = Reward(
            title=title,
            points_required=2.5,
            assigned_to_id=person.id,
            assigned_to=person.name,
            completed=False,
        )
        db.session.add(reward)
        db.session.commit()
        created_rewards.append(reward.id)

    try:
        html = client.get('/').get_data(as_text=True)
        assert 'data-points="2.5"' in html
        assert 'data-title="{}"'.format(title) in html
        live = _last_function(html, 'completeReward')
        assert "getAttribute('data-points')" in live
        assert 'rewardAmountCents' in live
        assert 'parseInt' not in live
        assert 'Math.floor' not in live
        assert '.points-display .chore-points-value' in live
        label = _last_function(html, 'rewardAmountLabel')
        assert 'padStart(2' in label
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
