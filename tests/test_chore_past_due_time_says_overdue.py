"""A chore past its due time today is overdue, on the board and in the bell.

Finishing it already awards no points. The card and the header bell kept
calling that chore due until the calendar day changed.
"""

import uuid
from datetime import date, datetime, timedelta, timezone

from app import app, db
from models import AppSetting, Chore, Person


def _add_person(created, label):
    person = Person(name=f'{label} {uuid.uuid4().hex[:6]}', points=0, bonus_points=0)
    db.session.add(person)
    db.session.flush()
    created['people'].append(person.id)
    return person


def _add_chore(created, person, title, due_datetime):
    chore = Chore(
        title=title,
        assigned_to=person.name,
        assigned_to_id=person.id,
        points=5,
        completed=False,
        deleted=False,
        is_daily=True,
        due_date=due_datetime.date(),
        due_datetime=due_datetime,
    )
    db.session.add(chore)
    db.session.flush()
    created['chores'].append(chore.id)
    return chore


def _cleanup(created):
    with app.app_context():
        for chore_id in created['chores']:
            chore = db.session.get(Chore, chore_id)
            if chore:
                db.session.delete(chore)
        for person_id in created['people']:
            person = db.session.get(Person, person_id)
            if person:
                db.session.delete(person)
        db.session.commit()


def test_past_due_time_is_overdue_on_the_board_and_in_the_bell():
    app.config['TESTING'] = True
    client = app.test_client()
    today = date.today()
    now = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
    past = now - timedelta(minutes=30)
    if past.date() != today:
        past = datetime.combine(today, datetime.min.time())
    future = now + timedelta(minutes=30)
    future_is_today = future.date() == today
    suffix = uuid.uuid4().hex[:8]
    past_title = f'Pack lunch {suffix}'
    future_title = f'Set the table {suffix}'
    created = {'people': [], 'chores': []}

    with app.app_context():
        AppSetting.set('timezone', 'UTC')
        person = _add_person(created, 'Due')
        _add_chore(created, person, past_title, past)
        if future_is_today:
            _add_chore(created, person, future_title, future)
        db.session.commit()

    try:
        page = client.get('/')
        assert page.status_code == 200
        html = page.get_data(as_text=True)

        def board_card(title):
            marker = f'class="chore-title">{title}</span>'
            at = html.find(marker)
            assert at != -1, title
            return html[at:at + 1200]

        past_card = board_card(past_title)
        assert 'chore-tag-overdue' in past_card
        assert 'Overdue' in past_card
        assert 'Due Today' not in past_card

        if future_is_today:
            future_card = board_card(future_title)
            assert 'chore-tag-due' in future_card
            assert 'Due Today' in future_card
            assert 'chore-tag-overdue' not in future_card

        notes = client.get('/api/notifications')
        assert notes.status_code == 200
        payload = notes.get_json()
        alerts = {alert['title']: alert for alert in payload['alerts'] if alert.get('kind') == 'chore'}
        past_alert = alerts[past_title]
        assert past_alert['severity'] == 'overdue'
        assert 'Past due' in past_alert['detail']
        if future_is_today:
            future_alert = alerts[future_title]
            assert future_alert['severity'] == 'due_soon'
            assert 'Due today' in future_alert['detail']
    finally:
        _cleanup(created)
