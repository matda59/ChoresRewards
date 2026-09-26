"""Renaming a family member must not strand their chores or rewards."""

import uuid

import pytest

from app import app, db
from models import Chore, Person, Reward


@pytest.fixture
def client():
    app.config['TESTING'] = True
    test_client = app.test_client()
    created = {'people': [], 'chores': [], 'rewards': []}

    def add_person(points=0):
        with app.app_context():
            person = Person(
                name=f'Test Kid {uuid.uuid4().hex[:8]}',
                points=points,
                bonus_points=0,
            )
            db.session.add(person)
            db.session.commit()
            created['people'].append(person.id)
            return person.id, person.name

    def add_chore(person_id, person_name, points=5):
        with app.app_context():
            chore = Chore(
                title='Dishes',
                assigned_to=person_name,
                assigned_to_id=person_id,
                points=points,
                is_daily=False,
                completed=False,
            )
            db.session.add(chore)
            db.session.commit()
            created['chores'].append(chore.id)
            return chore.id

    def add_reward(person_id, person_name):
        with app.app_context():
            reward = Reward(
                title=f'Movie {uuid.uuid4().hex[:6]}',
                points_required=10,
                assigned_to=person_name,
                assigned_to_id=person_id,
                completed=False,
            )
            db.session.add(reward)
            db.session.commit()
            created['rewards'].append(reward.id)
            return reward.id, reward.title

    test_client.add_person = add_person
    test_client.add_chore = add_chore
    test_client.add_reward = add_reward

    with test_client.session_transaction() as sess:
        sess['authenticated'] = True

    yield test_client

    with app.app_context():
        for chore_id in created['chores']:
            chore = db.session.get(Chore, chore_id)
            if chore:
                db.session.delete(chore)
        for reward_id in created['rewards']:
            reward = db.session.get(Reward, reward_id)
            if reward:
                db.session.delete(reward)
        for person_id in created['people']:
            person = db.session.get(Person, person_id)
            if person:
                db.session.delete(person)
        db.session.commit()


def _points(person_id):
    with app.app_context():
        return db.session.get(Person, person_id).points


def _assigned_to(model, row_id):
    with app.app_context():
        return db.session.get(model, row_id).assigned_to


def test_rename_updates_chore_and_reward_names_and_completion_still_awards(client):
    person_id, old_name = client.add_person()
    chore_id = client.add_chore(person_id, old_name)
    reward_id, _title = client.add_reward(person_id, old_name)
    new_name = old_name + ' Renamed'

    renamed = client.post('/update_name', json={'person_id': person_id, 'new_name': new_name})
    assert renamed.status_code == 200
    assert renamed.get_json()['success'] is True
    assert _assigned_to(Chore, chore_id) == new_name
    assert _assigned_to(Reward, reward_id) == new_name

    completed = client.post('/complete_chore', json={'chore_id': chore_id})
    assert completed.status_code == 200
    assert completed.get_json()['success'] is True
    assert _points(person_id) == 5

    undone = client.post('/undo_complete_chore', json={'chore_id': chore_id})
    assert undone.status_code == 200
    assert undone.get_json()['success'] is True
    assert _points(person_id) == 0


def test_stale_assigned_name_still_completes_and_reward_card_uses_current_name(client):
    person_id, current_name = client.add_person(points=12)
    chore_id = client.add_chore(person_id, current_name)
    reward_id, title = client.add_reward(person_id, current_name)

    with app.app_context():
        chore = db.session.get(Chore, chore_id)
        reward = db.session.get(Reward, reward_id)
        chore.assigned_to = 'Name Before Rename'
        reward.assigned_to = 'Name Before Rename'
        db.session.commit()

    completed = client.post('/complete_chore', json={'chore_id': chore_id})
    body = completed.get_json()
    assert completed.status_code == 200, body
    assert body['success'] is True
    assert body['points_awarded'] == 5
    assert _points(person_id) == 17
    assert _assigned_to(Chore, chore_id) == current_name

    undone = client.post('/undo_complete_chore', json={'chore_id': chore_id})
    assert undone.status_code == 200
    assert _points(person_id) == 12

    page = client.get('/')
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    marker = f'data-title="{title}"'
    idx = html.find(marker)
    assert idx != -1
    card = html[idx - 250:idx]
    assert f'data-assigned-to="{current_name}"' in card
    assert f'data-assigned-to-id="{person_id}"' in card
    assert 'data-assigned-to="Name Before Rename"' not in html


def test_rename_rejects_a_name_already_in_use(client):
    first_id, first_name = client.add_person()
    _second_id, second_name = client.add_person()
    chore_id = client.add_chore(first_id, first_name)

    renamed = client.post('/update_name', json={'person_id': first_id, 'new_name': second_name})
    assert renamed.status_code == 400
    assert renamed.get_json()['success'] is False
    assert _assigned_to(Chore, chore_id) == first_name
    with app.app_context():
        assert db.session.get(Person, first_id).name == first_name
