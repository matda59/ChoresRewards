"""Saving a shopping store must keep bundled logo paths intact."""

import json

import pytest

from app import app, db
from models import AppSetting
from routes import _clean_store_icon, _get_shopping_stores

ALDI = '/static/images/rewards/store_aldi.svg'
WOOLWORTHS = '/static/images/rewards/store_woolworths.svg'
TRUNCATED = '/static/images/'


def test_clean_store_icon_keeps_logo_and_emoji():
    assert _clean_store_icon(ALDI, 'aldi') == ALDI
    assert _clean_store_icon(WOOLWORTHS, 'custom-store') == WOOLWORTHS
    assert _clean_store_icon('🛒', 'aldi') == '🛒'
    assert _clean_store_icon('🍎', 'coles-1234') == '🍎'
    assert _clean_store_icon(None, 'coles-1234') == '🛒'
    assert _clean_store_icon('', 'aldi') == '🛒'


def test_clean_store_icon_restores_logo_cut_off_by_old_save():
    assert _clean_store_icon(TRUNCATED, 'aldi') == ALDI
    assert _clean_store_icon(TRUNCATED, 'Woolworths') == WOOLWORTHS
    assert _clean_store_icon(TRUNCATED, 'coles-1234') == '🛒'
    assert _clean_store_icon('/static/images/rewards/nope.png', 'aldi') == '🛒'


@pytest.fixture
def client():
    app.config['TESTING'] = True
    test_client = app.test_client()
    with app.app_context():
        row = AppSetting.query.filter_by(key='shopping_stores_json').first()
        previous = row.value if row else None
    with test_client.session_transaction() as sess:
        sess['authenticated'] = True
    yield test_client
    with app.app_context():
        row = AppSetting.query.filter_by(key='shopping_stores_json').first()
        if previous is None:
            if row:
                db.session.delete(row)
                db.session.commit()
        else:
            AppSetting.set('shopping_stores_json', previous)


def test_save_keeps_full_logo_paths(client):
    payload = {
        'stores': [
            {'id': 'aldi', 'name': 'Aldi', 'icon': ALDI},
            {'id': 'woolworths', 'name': 'Woolies', 'icon': WOOLWORTHS},
            {'id': 'corner-shop', 'name': 'Corner Shop', 'icon': '🏪'},
        ]
    }
    response = client.post('/api/shopping_stores', json=payload)
    body = response.get_json()
    assert response.status_code == 200
    assert body['success'] is True
    icons = {store['id']: store['icon'] for store in body['stores']}
    assert icons['aldi'] == ALDI
    assert icons['woolworths'] == WOOLWORTHS
    assert icons['corner-shop'] == '🏪'

    with app.app_context():
        stored = json.loads(AppSetting.get('shopping_stores_json'))
    stored_icons = {store['id']: store['icon'] for store in stored}
    assert stored_icons['aldi'] == ALDI
    assert stored_icons['woolworths'] == WOOLWORTHS


def test_read_repairs_icons_truncated_by_old_save(client):
    broken = [
        {'id': 'aldi', 'name': 'Aldi', 'icon': TRUNCATED},
        {'id': 'woolworths', 'name': 'Woolworths', 'icon': TRUNCATED},
        {'id': 'corner-shop', 'name': 'Corner Shop', 'icon': '🏪'},
    ]
    with app.app_context():
        AppSetting.set('shopping_stores_json', json.dumps(broken))
        stores = _get_shopping_stores()
    icons = {store['id']: store['icon'] for store in stores}
    assert icons['aldi'] == ALDI
    assert icons['woolworths'] == WOOLWORTHS
    assert icons['corner-shop'] == '🏪'

    response = client.get('/api/shopping_stores')
    body = response.get_json()
    assert body['success'] is True
    api_icons = {store['id']: store['icon'] for store in body['stores']}
    assert api_icons['aldi'] == ALDI
    assert api_icons['woolworths'] == WOOLWORTHS
