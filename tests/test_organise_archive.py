"""Paid rego and insurance stay in the archive instead of being overwritten."""

import uuid
from datetime import date, timedelta

from app import app, db
from models import ActivityLog, OrganiseArchive, OrganiseItem


def test_marking_paid_keeps_the_previous_period_in_the_archive():
    app.config['TESTING'] = True
    client = app.test_client()
    suffix = uuid.uuid4().hex[:8]
    today = date.today()
    old_due = today + timedelta(days=20)
    new_due = today + timedelta(days=400)
    with app.app_context():
        car = OrganiseItem(
            category='Car', title=f'Elgrand {suffix}',
            vehicle_make='Nissan', vehicle_model=f'Elgrand {suffix}', vehicle_year=2008,
        )
        db.session.add(car)
        db.session.flush()
        rego = OrganiseItem(
            category='Car', title=f'Registration {suffix}', parent_id=car.id,
            provider='VicRoads', due_date=old_due, cost=800, reminder_days=30,
        )
        db.session.add(rego)
        db.session.commit()
        car_id, rego_id = car.id, rego.id

    archive_ids = []
    try:
        with client.session_transaction() as sess:
            sess['adult_mode'] = True
        saved = client.put(f'/api/organise/{rego_id}', json={
            'archive_payment': True,
            'paid': False,
            'last_date': today.isoformat(),
            'due_date': new_due.isoformat(),
            'cost': 842.5,
        })
        assert saved.status_code == 200
        assert saved.get_json()['success'] is True

        listed = client.get('/api/organise')
        payload = listed.get_json()
        live = next(item for item in payload['items'] if item['id'] == rego_id)
        assert live['due_date'] == new_due.isoformat()
        assert live['cost'] == 842.5
        archived = [row for row in payload['archive'] if suffix in row['title']]
        assert len(archived) == 1
        assert archived[0]['covered_until'] == old_due.isoformat()
        assert archived[0]['paid_on'] == today.isoformat()
        assert archived[0]['next_due'] == new_due.isoformat()
        assert archived[0]['cost'] == 842.5
        assert f'Elgrand {suffix}' in archived[0]['car_label']
        archive_ids.append(archived[0]['id'])

        removed = client.delete(f"/api/organise/archive/{archived[0]['id']}")
        assert removed.status_code == 200
        again = client.get('/api/organise').get_json()
        assert all(row['id'] != archived[0]['id'] for row in again['archive'])
        assert any(item['id'] == rego_id for item in again['items'])
        archive_ids.clear()
    finally:
        with app.app_context():
            for archive_id in archive_ids:
                row = db.session.get(OrganiseArchive, archive_id)
                if row:
                    db.session.delete(row)
            for item_id in (rego_id, car_id):
                item = db.session.get(OrganiseItem, item_id)
                if item:
                    db.session.delete(item)
            ActivityLog.query.filter(ActivityLog.description.contains(suffix)).delete(synchronize_session=False)
            db.session.commit()


def test_moving_a_document_to_the_archive_leaves_the_car():
    app.config['TESTING'] = True
    client = app.test_client()
    suffix = uuid.uuid4().hex[:8]
    with app.app_context():
        car = OrganiseItem(
            category='Car', title=f'ix35 {suffix}',
            vehicle_make='Hyundai', vehicle_model=f'ix35 {suffix}',
        )
        db.session.add(car)
        db.session.flush()
        doc = OrganiseItem(
            category='Car', title=f'Old rego {suffix}', parent_id=car.id,
            due_date=date.today() - timedelta(days=40), cost=700, provider='VicRoads',
        )
        db.session.add(doc)
        db.session.commit()
        car_id, doc_id = car.id, doc.id

    try:
        with client.session_transaction() as sess:
            sess['adult_mode'] = True
        blocked = client.post(f'/api/organise/{car_id}/archive')
        assert blocked.status_code == 400

        moved = client.post(f'/api/organise/{doc_id}/archive')
        assert moved.status_code == 200
        body = moved.get_json()
        assert body['success'] is True
        filed = [row for row in body['archive'] if suffix in row['title']]
        assert len(filed) == 1
        assert filed[0]['cost'] == 700
        with app.app_context():
            assert db.session.get(OrganiseItem, doc_id) is None
            assert db.session.get(OrganiseItem, car_id) is not None
            row = db.session.get(OrganiseArchive, filed[0]['id'])
            if row:
                db.session.delete(row)
            db.session.commit()
    finally:
        with app.app_context():
            item = db.session.get(OrganiseItem, car_id)
            if item:
                db.session.delete(item)
            leftover = db.session.get(OrganiseItem, doc_id)
            if leftover:
                db.session.delete(leftover)
            ActivityLog.query.filter(ActivityLog.description.contains(suffix)).delete(synchronize_session=False)
            db.session.commit()
