"""Today at a Glance is today's work, not a chore that is still ahead.

A one-off due later in the week stays on the chore board. The glance used to
list it as something to do today, and a day with only that chore looked busy.
"""

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


def test_glance_leaves_a_future_one_off_off_today():
    app.config['TESTING'] = True
    client = app.test_client()
    today = date.today()
    created = {'people': [], 'chores': []}

    def add_person(label):
        person = Person(
            name=f'Later {label} {uuid.uuid4().hex[:6]}',
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
            completed=kwargs.pop('completed', False),
            **kwargs,
        )
        db.session.add(chore)
        db.session.flush()
        created['chores'].append(chore.id)
        return chore

    with app.app_context():
        later_person = add_person('Only')
        mixed_person = add_person('Mixed')
        overdue_person = add_person('Overdue')
        done_person = add_person('Done')
        add_chore(
            later_person,
            'Wash the car',
            is_daily=False,
            due_date=today + timedelta(days=4),
        )
        add_chore(mixed_person, 'Feed the dog', is_daily=False, due_date=today)
        add_chore(
            mixed_person,
            'Mow the lawn',
            is_daily=False,
            due_date=today + timedelta(days=3),
        )
        add_chore(
            overdue_person,
            'Return the library books',
            is_daily=False,
            due_date=today - timedelta(days=2),
        )
        add_chore(
            done_person,
            'Make the bed',
            completed=True,
            is_daily=True,
            date_completed=datetime.combine(today, datetime.min.time()),
            due_date=today,
        )
        add_chore(
            done_person,
            'Pack for Saturday',
            is_daily=False,
            due_date=today + timedelta(days=5),
        )
        db.session.commit()
        names = {
            'later': later_person.name,
            'mixed': mixed_person.name,
            'overdue': overdue_person.name,
            'done': done_person.name,
        }

    try:
        html = client.get('/').get_data(as_text=True)
        later_row = _tasks_row(html, names['later'])
        mixed_row = _tasks_row(html, names['mixed'])
        overdue_row = _tasks_row(html, names['overdue'])
        done_row = _tasks_row(html, names['done'])

        assert 'Wash the car' not in later_row
        assert 'No chores today' in later_row
        assert 'dash-free-day' in later_row
        assert 'All done today' not in later_row
        assert html.count('Wash the car') == 1

        assert 'Feed the dog' in mixed_row
        assert 'Mow the lawn' not in mixed_row
        assert '1 left' in mixed_row
        assert '2 left' not in mixed_row

        assert 'Return the library books' in overdue_row
        assert '1 left' in overdue_row
        assert 'No chores today' not in overdue_row

        assert 'All done today' in done_row
        assert 'Pack for Saturday' not in done_row
        assert 'dash-all-done' in done_row
        assert 'No chores today' not in done_row
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
