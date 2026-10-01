"""The header bell should not list a repeating chore on a day it does not run."""

import uuid
from datetime import date, datetime, timedelta, timezone

from app import app, db
from models import AppSetting, Chore, Person


def _alert_titles(payload):
    return [alert.get('title') for alert in payload.get('alerts', []) if alert.get('kind') == 'chore']


def test_bell_hides_repeating_chores_that_are_not_on_todays_board():
    app.config['TESTING'] = True
    client = app.test_client()
    today = date.today()
    today_name = today.strftime('%A').lower()
    other_day = (today + timedelta(days=1)).strftime('%A').lower()
    noon = datetime.combine(today, datetime.min.time()).replace(hour=12)
    created = {'people': [], 'chores': []}
    suffix = uuid.uuid4().hex[:8]

    titles = {
        'off': f'Pack the school bag {suffix}',
        'skipped': f'Walk the dog {suffix}',
        'today': f'Make the bed {suffix}',
        'soon': f'Clean the garage {suffix}',
    }

    with app.app_context():
        AppSetting.set('timezone', 'UTC')
        person = Person(name=f'Bell {suffix}', points=0, bonus_points=0)
        db.session.add(person)
        db.session.flush()
        created['people'].append(person.id)

        def add(title, **kwargs):
            chore = Chore(
                title=title,
                assigned_to=person.name,
                assigned_to_id=person.id,
                points=1,
                completed=False,
                deleted=False,
                **kwargs,
            )
            db.session.add(chore)
            db.session.flush()
            created['chores'].append(chore.id)

        add(
            titles['off'],
            is_daily=True,
            days_of_week=other_day,
            due_date=today,
            due_datetime=noon,
        )
        add(
            titles['skipped'],
            is_daily=True,
            days_of_week=today_name,
            due_date=today + timedelta(days=1),
            due_datetime=noon,
        )
        add(
            titles['today'],
            is_daily=True,
            days_of_week=today_name,
            due_date=today,
            due_datetime=noon,
        )
        add(
            titles['soon'],
            is_daily=False,
            due_date=today + timedelta(days=1),
            due_datetime=datetime.combine(today + timedelta(days=1), datetime.min.time()).replace(hour=9),
        )
        db.session.commit()

    try:
        response = client.get('/api/notifications')
        assert response.status_code == 200
        payload = response.get_json()
        assert payload['success'] is True
        titles_shown = _alert_titles(payload)
        assert titles['off'] not in titles_shown
        assert titles['skipped'] not in titles_shown
        assert titles['today'] in titles_shown
        assert titles['soon'] in titles_shown
        today_alert = next(alert for alert in payload['alerts'] if alert.get('title') == titles['today'])
        past_noon = datetime.now(timezone.utc) > noon.replace(tzinfo=timezone.utc)
        assert today_alert['severity'] == ('overdue' if past_noon else 'due_soon')
        assert ('Past due' if past_noon else 'Due today') in today_alert['detail']
    finally:
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
