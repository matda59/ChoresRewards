"""Today at a Glance should not call a free day finished work."""

import uuid
from datetime import date, datetime, timedelta

from app import app, db
from models import Chore, Person


def _tasks_row(html, name):
    marker = f'class="dash-person-name">{name}</div>'
    marker_at = html.find(marker)
    assert marker_at != -1, name
    start = html.rfind('dash-person-row', 0, marker_at)
    assert start != -1
    end = html.find('dash-person-row', marker_at)
    if end == -1:
        end = html.find('dash-tile-resize', marker_at)
    return html[start:end]


def test_glance_distinguishes_a_free_day_from_finished_chores():
    app.config['TESTING'] = True
    client = app.test_client()
    today = date.today()
    other_day = (today + timedelta(days=1)).strftime('%A').lower()
    created = {'people': [], 'chores': []}

    def add_person(label):
        person = Person(
            name=f'Glance {label} {uuid.uuid4().hex[:6]}',
            points=0,
            bonus_points=0,
        )
        db.session.add(person)
        db.session.flush()
        created['people'].append(person.id)
        return person

    def add_chore(person, title, **kwargs):
        chore = Chore(
            title=title,
            assigned_to=person.name,
            assigned_to_id=person.id,
            points=1,
            deleted=False,
            **kwargs,
        )
        db.session.add(chore)
        db.session.flush()
        created['chores'].append(chore.id)
        return chore

    with app.app_context():
        free_person = add_person('Free')
        open_person = add_person('Open')
        done_person = add_person('Done')
        off_person = add_person('Off')
        add_chore(open_person, 'Feed the dog', completed=False, is_daily=False)
        add_chore(
            done_person,
            'Make the bed',
            completed=True,
            is_daily=True,
            date_completed=datetime.combine(today, datetime.min.time()),
            due_date=today,
        )
        add_chore(
            off_person,
            'Take the bins out',
            completed=False,
            is_daily=True,
            days_of_week=other_day,
            due_date=today,
        )
        db.session.commit()
        names = {
            'free': free_person.name,
            'open': open_person.name,
            'done': done_person.name,
            'off': off_person.name,
        }

    try:
        html = client.get('/').get_data(as_text=True)
        free_row = _tasks_row(html, names['free'])
        open_row = _tasks_row(html, names['open'])
        done_row = _tasks_row(html, names['done'])
        off_row = _tasks_row(html, names['off'])

        assert 'No chores today' in free_row
        assert 'All done today' not in free_row
        assert 'dash-free-day' in free_row
        assert 'dash-all-done' not in free_row

        assert 'Feed the dog' in open_row
        assert '1 left' in open_row
        assert 'No chores today' not in open_row
        assert 'All done today' not in open_row

        assert 'All done today' in done_row
        assert 'dash-all-done' in done_row
        assert 'No chores today' not in done_row

        assert 'No chores today' in off_row
        assert 'Take the bins out' not in off_row
        assert 'All done today' not in off_row
        assert 'dash-free-day' in off_row
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
