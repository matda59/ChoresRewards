"""Cash amounts on chore and reward cards should show cents, like the balance."""

import uuid
from datetime import datetime, time

from app import app, db
from models import AppSetting, Chore, Person, Reward
from routes import _family_today


def _around(html, marker, window=1600):
    at = html.find(marker)
    assert at != -1, marker
    return html[max(0, at - window):at + window]


def test_cash_cards_show_two_decimals_and_points_mode_does_not():
    app.config['TESTING'] = True
    client = app.test_client()
    suffix = uuid.uuid4().hex[:6]
    chore_title = 'Wash up {}'.format(suffix)
    done_title = 'Folding {}'.format(suffix)
    reward_title = 'Ice cream {}'.format(suffix)
    redeemed_title = 'Mini golf {}'.format(suffix)
    created_people = []
    created_chores = []
    created_rewards = []

    with app.app_context():
        saved_system = AppSetting.get('reward_system', 'points')
        person = Person(name='Cash Cards {}'.format(suffix), points=10, bonus_points=0)
        db.session.add(person)
        db.session.commit()
        created_people.append(person.id)
        done_at = datetime.combine(_family_today(), time(15, 0))
        open_chore = Chore(
            title=chore_title,
            assigned_to=person.name,
            assigned_to_id=person.id,
            points=2.5,
            completed=False,
            deleted=False,
        )
        done_chore = Chore(
            title=done_title,
            assigned_to=person.name,
            assigned_to_id=person.id,
            points=1.5,
            completed=True,
            date_completed=done_at,
            deleted=False,
        )
        db.session.add(open_chore)
        db.session.add(done_chore)
        db.session.commit()
        created_chores.extend([open_chore.id, done_chore.id])
        available = Reward(
            title=reward_title,
            points_required=3.25,
            assigned_to_id=person.id,
            assigned_to=person.name,
            completed=False,
        )
        redeemed = Reward(
            title=redeemed_title,
            points_required=4.5,
            assigned_to_id=person.id,
            assigned_to=person.name,
            completed=True,
            date_completed=done_at,
        )
        db.session.add(available)
        db.session.add(redeemed)
        db.session.commit()
        created_rewards.extend([available.id, redeemed.id])
        AppSetting.set_reward_system('cash')

    try:
        html = client.get('/').get_data(as_text=True)
        chore_card = _around(html, 'class="chore-title">{}'.format(chore_title))
        done_card = _around(html, done_title)
        reward_card = _around(html, 'class="reward-title-modern">{}'.format(reward_title))
        redeemed_card = _around(html, 'class="reward-title-modern">{}'.format(redeemed_title))
        assert '>$2.50<' in chore_card
        assert '>$2.5<' not in chore_card
        assert '>$1.50<' in done_card
        assert '>$1.5<' not in done_card
        assert reward_card.count('>$3.25<') >= 2
        assert 'fa-money-bill-wave' in reward_card
        assert redeemed_card.count('>$4.50<') >= 2
        assert '>$4.5<' not in redeemed_card
        assert 'data-points="3.25"' in html
        assert 'isCash ? points.toFixed(2)' in html

        fragment = client.get('/completed_chores_fragment').get_data(as_text=True)
        done_fragment = _around(fragment, done_title)
        assert '>$1.50<' in done_fragment
        assert '>$1.5<' not in done_fragment

        with app.app_context():
            AppSetting.set_reward_system('points')
        points_html = client.get('/').get_data(as_text=True)
        points_chore = _around(points_html, 'class="chore-title">{}'.format(chore_title))
        points_reward = _around(points_html, 'class="reward-title-modern">{}'.format(reward_title))
        assert '>2.5<' in points_chore
        assert '$2.50' not in points_chore
        assert '>3.25<' in points_reward
        assert '$3.25' not in points_reward
    finally:
        with app.app_context():
            AppSetting.set('reward_system', saved_system if saved_system in ('points', 'cash') else 'points')
            for chore_id in created_chores:
                chore = db.session.get(Chore, chore_id)
                if chore:
                    db.session.delete(chore)
            for reward_id in created_rewards:
                reward = db.session.get(Reward, reward_id)
                if reward:
                    db.session.delete(reward)
            for person_id in created_people:
                person = db.session.get(Person, person_id)
                if person:
                    db.session.delete(person)
            db.session.commit()
