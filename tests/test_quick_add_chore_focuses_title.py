"""Quick Add should open the chore title, and only for an unlocked adult."""

import uuid

from app import app, db
from models import Person


def test_quick_add_chore_focuses_the_title_and_stays_adult_only():
    app.config['TESTING'] = True
    client = app.test_client()
    with app.app_context():
        person = Person(
            name='Quick Add {}'.format(uuid.uuid4().hex[:6]),
            points=0,
            bonus_points=0,
        )
        db.session.add(person)
        db.session.commit()
        person_id = person.id
    try:
        html = client.get('/').get_data(as_text=True)
        start = html.find('function quickNavAction')
        assert start != -1
        end = html.find("document.addEventListener('click'", start)
        assert end != -1
        live = html[start:end]
        assert "getElementById('chore-title-input')" in live
        assert "getElementById('title')" not in live
        assert '#add-chores-section input[type="text"]' not in live

        section_at = html.find('id="add-chores-section"')
        suggestion_at = html.find('id="new-chore-suggestion"', section_at)
        title_at = html.find('id="chore-title-input"', section_at)
        assert section_at != -1
        assert suggestion_at != -1 and title_at != -1
        assert suggestion_at < title_at

        button_at = html.find("quickNavAction('chore')")
        button = html[html.rfind('<button', 0, button_at):html.find('>', button_at)]
        assert 'admin-only' in button
        assert 'data-display="flex"' in button
    finally:
        with app.app_context():
            row = db.session.get(Person, person_id)
            if row:
                db.session.delete(row)
                db.session.commit()
