"""Organise reminders use each item's notice period, including service by kilometres."""

import uuid
from datetime import date, timedelta

from app import app, db
from models import AppSetting, OrganiseItem, VehicleService


def _alerts(client):
    response = client.get('/api/notifications')
    assert response.status_code == 200
    payload = response.get_json()
    assert payload['success'] is True
    return payload['alerts']


def test_bell_respects_reminder_days_and_service_kilometres():
    app.config['TESTING'] = True
    client = app.test_client()
    today = date.today()
    suffix = uuid.uuid4().hex[:8]
    created = []
    service_ids = []

    soon = f'Rego {suffix}'
    quiet = f'Insurance quiet {suffix}'
    paid = f'Paid rego {suffix}'
    by_date = f'Elgrand {suffix}'
    by_km = f'ix35 {suffix}'
    far = f'Camry {suffix}'
    from_log = f'Mazda {suffix}'

    with app.app_context():
        AppSetting.set('timezone', 'UTC')
        rows = [
            OrganiseItem(category='Car', title=soon, due_date=today + timedelta(days=20), reminder_days=30, paid=False),
            OrganiseItem(category='Car', title=quiet, due_date=today + timedelta(days=20), reminder_days=7, paid=False),
            OrganiseItem(category='Car', title=paid, due_date=today + timedelta(days=2), reminder_days=30, paid=True),
            OrganiseItem(
                category='Car', title=by_date, vehicle_make='Nissan', vehicle_model=by_date,
                reminder_days=30, next_service_date=today + timedelta(days=20),
                current_odometer=100000, next_service_mileage=120000,
            ),
            OrganiseItem(
                category='Car', title=by_km, vehicle_make='Hyundai', vehicle_model=by_km,
                reminder_days=30, next_service_date=today + timedelta(days=90),
                current_odometer=140000, next_service_mileage=141000,
            ),
            OrganiseItem(
                category='Car', title=far, vehicle_make='Toyota', vehicle_model=far,
                reminder_days=30, next_service_date=today + timedelta(days=90),
                current_odometer=100000, next_service_mileage=120000,
            ),
            OrganiseItem(
                category='Car', title=from_log, vehicle_make='Mazda', vehicle_model=from_log,
                reminder_days=14,
            ),
        ]
        for row in rows:
            db.session.add(row)
        db.session.flush()
        created.extend(row.id for row in rows)
        logged = rows[-1]
        svc = VehicleService(
            organise_item_id=logged.id,
            service_type='Oil change',
            service_date=today - timedelta(days=300),
            mileage=130000,
            next_service_date=today + timedelta(days=3),
            next_service_mileage=140000,
        )
        db.session.add(svc)
        db.session.flush()
        service_ids.append(svc.id)
        db.session.commit()

    try:
        matched = [
            alert for alert in _alerts(client)
            if suffix in (alert.get('title') or '') or suffix in (alert.get('detail') or '')
        ]
        by_title = {alert['title']: alert for alert in matched if alert['kind'] == 'organise'}
        assert soon in by_title
        assert by_title[soon]['severity'] == 'due_soon'
        assert quiet not in by_title
        assert paid not in by_title

        date_alert = next(alert for alert in matched if by_date in alert['detail'] and alert['kind'] == 'service')
        assert '20d away' in date_alert['detail']
        assert 'km' not in date_alert['detail']

        km_alert = next(alert for alert in matched if by_km in alert['detail'])
        assert '1,000 km to go' in km_alert['detail']
        assert km_alert['severity'] == 'due_soon'

        assert not any(far in alert['detail'] and alert['kind'] == 'service' for alert in matched)

        logged_alert = next(alert for alert in matched if from_log in alert['detail'])
        assert logged_alert['kind'] == 'service'
        assert '3d away' in logged_alert['detail']
    finally:
        with app.app_context():
            for service_id in service_ids:
                svc = db.session.get(VehicleService, service_id)
                if svc:
                    db.session.delete(svc)
            for item_id in created:
                item = db.session.get(OrganiseItem, item_id)
                if item:
                    db.session.delete(item)
            db.session.commit()


def test_deleting_a_car_document_leaves_the_car():
    app.config['TESTING'] = True
    client = app.test_client()
    suffix = uuid.uuid4().hex[:8]
    with app.app_context():
        car = OrganiseItem(
            category='Car', title=f'Family car {suffix}',
            vehicle_make='Nissan', vehicle_model='Elgrand', vehicle_year=2008,
        )
        db.session.add(car)
        db.session.flush()
        doc = OrganiseItem(
            category='Car', title=f'Insurance {suffix}', parent_id=car.id,
            due_date=date.today() + timedelta(days=40), reminder_days=30,
        )
        db.session.add(doc)
        db.session.commit()
        car_id, doc_id = car.id, doc.id

    try:
        with client.session_transaction() as sess:
            sess['adult_mode'] = True
        response = client.delete(f'/api/organise/{doc_id}')
        assert response.status_code == 200
        assert response.get_json()['success'] is True
        with app.app_context():
            assert db.session.get(OrganiseItem, doc_id) is None
            assert db.session.get(OrganiseItem, car_id) is not None
    finally:
        with app.app_context():
            for item_id in (doc_id, car_id):
                item = db.session.get(OrganiseItem, item_id)
                if item:
                    db.session.delete(item)
            db.session.commit()
