"""A general shopping item is unique per store, not across the whole list.

Milk at Aldi and milk at Woolworths are both needed. Saving the list used to
keep only the first name, so the second store's line disappeared.
"""

from pathlib import Path

from app import app, db
from models import AppSetting


def test_quick_add_matches_name_and_store():
    text = Path('templates/index.html').read_text()
    start = text.index('const doQuickAddGeneral')
    chunk = text[start:start + 700]
    assert 'sameGeneralItem' in chunk
    assert 'shoppingNotice' in chunk


def test_same_name_is_kept_at_each_store_and_in_the_archive():
    app.config['TESTING'] = True
    client = app.test_client()
    with app.app_context():
        row = AppSetting.query.filter_by(key='shopping_list_json').first()
        previous = row.value if row else None

    payload = {
        'checked': {
            'general::aldi::milk': True,
            'general::woolworths::milk': False,
        },
        'general': [
            {'name': 'Milk', 'store': 'aldi'},
            {'name': 'milk', 'store': 'woolworths'},
            {'name': 'Milk', 'store': 'aldi'},
            {'name': 'Bread', 'store': 'aldi'},
        ],
        'archived': [
            {'name': 'Milk', 'store': 'aldi'},
            {'name': 'Milk', 'store': 'woolworths'},
            {'name': 'Milk', 'store': 'aldi'},
        ],
        'hidden': {},
        'active': [],
        'meal_order': [],
    }
    try:
        response = client.post('/api/shopping_list', json=payload)
        body = response.get_json()
        assert response.status_code == 200
        assert body['success'] is True
        assert body['general'] == [
            {'name': 'Milk', 'store': 'aldi'},
            {'name': 'milk', 'store': 'woolworths'},
            {'name': 'Bread', 'store': 'aldi'},
        ]
        assert body['archived'] == [
            {'name': 'Milk', 'store': 'aldi'},
            {'name': 'Milk', 'store': 'woolworths'},
        ]
        assert body['checked']['general::aldi::milk'] is True
        assert body['checked']['general::woolworths::milk'] is False

        again = client.get('/api/shopping_list')
        stored = again.get_json()
        assert stored['general'] == body['general']
        assert stored['archived'] == body['archived']
    finally:
        with app.app_context():
            row = AppSetting.query.filter_by(key='shopping_list_json').first()
            if previous is None:
                if row:
                    db.session.delete(row)
                    db.session.commit()
            else:
                AppSetting.set('shopping_list_json', previous)
