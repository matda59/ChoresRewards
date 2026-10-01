"""A reward can be paid for only once.

The redeem celebration leaves the card in place and reloads a few seconds
later. Confirming twice used to subtract the cost on every request.
"""

import uuid

from app import app, db
from models import Person, Reward


def test_second_redeem_does_not_charge_again():
    app.config['TESTING'] = True
    client = app.test_client()
    suffix = uuid.uuid4().hex[:8]
    created = {'people': [], 'rewards': []}

    with app.app_context():
        person = Person(
            name=f'Redeem Once {suffix}',
            points=10,
            bonus_points=0,
        )
        db.session.add(person)
        db.session.commit()
        created['people'].append(person.id)
        reward = Reward(
            title=f'Movie {suffix}',
            points_required=4,
            assigned_to_id=person.id,
            assigned_to=person.name,
            completed=False,
        )
        db.session.add(reward)
        db.session.commit()
        created['rewards'].append(reward.id)
        person_id = person.id
        reward_id = reward.id

    with client.session_transaction() as sess:
        sess['authenticated'] = True
        sess['adult_mode'] = True

    try:
        first = client.post('/complete_reward', json={'reward_id': reward_id})
        assert first.status_code == 200
        assert first.get_json()['success'] is True
        assert first.get_json()['new_points'] == 6

        second = client.post('/complete_reward', json={'reward_id': reward_id})
        body = second.get_json()
        assert second.status_code == 409
        assert body['success'] is False

        with app.app_context():
            person = db.session.get(Person, person_id)
            reward = db.session.get(Reward, reward_id)
            assert person.points == 6
            assert reward.completed is True
    finally:
        with app.app_context():
            for reward_id in created['rewards']:
                reward = db.session.get(Reward, reward_id)
                if reward:
                    db.session.delete(reward)
            for person_id in created['people']:
                person = db.session.get(Person, person_id)
                if person:
                    db.session.delete(person)
            db.session.commit()
