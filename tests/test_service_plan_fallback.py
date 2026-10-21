"""The live service plan is the latest visit, or a plan the car saved itself.

An older receipt keeps the next-service date that followed that visit. The
bell used the earliest of those dates, so logging a later visit with no new
plan — or clearing the plan on the car — still announced the old date as overdue.
"""

import uuid
from datetime import date, timedelta

from app import app, db
from models import AppSetting, OrganiseItem, VehicleService


def _service_alerts(client, label):
    response = client.get('/api/notifications')
    assert response.status_code == 200
    payload = response.get_json()
    assert payload['success'] is True
    return [
        alert for alert in payload['alerts']
        if alert.get('kind') == 'service' and label in (alert.get('detail') or '')
    ]


def test_an_older_receipt_does_not_revive_a_finished_service_plan():
    app.config['TESTING'] = True
    client = app.test_client()
    today = date.today()
    label = f'Fallback {uuid.uuid4().hex[:8]}'
    with app.app_context():
        AppSetting.set('timezone', 'UTC')
        car = OrganiseItem(
            category='Car', title=label, vehicle_make='Toyota', vehicle_model=label,
            reminder_days=30, current_odometer=140000,
        )
        db.session.add(car)
        db.session.flush()
        older = VehicleService(
            organise_item_id=car.id,
            service_type='Major service',
            service_date=today - timedelta(days=400),
            mileage=100000,
            next_service_date=today - timedelta(days=200),
            next_service_mileage=110000,
        )
        latest = VehicleService(
            organise_item_id=car.id,
            service_type='Oil change',
            service_date=today - timedelta(days=5),
            mileage=140000,
        )
        db.session.add(older)
        db.session.add(latest)
        db.session.commit()
        car_id = car.id
        service_ids = [older.id, latest.id]

    try:
        assert _service_alerts(client, label) == []
    finally:
        with app.app_context():
            for service_id in service_ids:
                row = db.session.get(VehicleService, service_id)
                if row:
                    db.session.delete(row)
            car = db.session.get(OrganiseItem, car_id)
            if car:
                db.session.delete(car)
            db.session.commit()


def test_the_latest_visit_supplies_the_plan_when_the_car_has_none():
    app.config['TESTING'] = True
    client = app.test_client()
    today = date.today()
    label = f'Latest {uuid.uuid4().hex[:8]}'
    with app.app_context():
        AppSetting.set('timezone', 'UTC')
        car = OrganiseItem(
            category='Car', title=label, vehicle_make='Honda', vehicle_model=label,
            reminder_days=30,
        )
        db.session.add(car)
        db.session.flush()
        older = VehicleService(
            organise_item_id=car.id,
            service_type='Old service',
            service_date=today - timedelta(days=500),
            mileage=80000,
            next_service_date=today - timedelta(days=180),
            next_service_mileage=90000,
        )
        latest = VehicleService(
            organise_item_id=car.id,
            service_type='Recent service',
            service_date=today - timedelta(days=20),
            mileage=120000,
            next_service_date=today + timedelta(days=10),
            next_service_mileage=130000,
        )
        db.session.add(older)
        db.session.add(latest)
        db.session.commit()
        car_id = car.id
        service_ids = [older.id, latest.id]

    try:
        alerts = _service_alerts(client, label)
        assert len(alerts) == 1
        assert alerts[0]['severity'] == 'due_soon'
        assert '10d away' in alerts[0]['detail']
        assert 'overdue' not in alerts[0]['detail']
    finally:
        with app.app_context():
            for service_id in service_ids:
                row = db.session.get(VehicleService, service_id)
                if row:
                    db.session.delete(row)
            car = db.session.get(OrganiseItem, car_id)
            if car:
                db.session.delete(car)
            db.session.commit()


def test_clearing_the_next_service_plan_does_not_restore_the_log():
    app.config['TESTING'] = True
    client = app.test_client()
    today = date.today()
    label = f'Cleared {uuid.uuid4().hex[:8]}'
    with app.app_context():
        AppSetting.set('timezone', 'UTC')
        car = OrganiseItem(
            category='Car', title=label, vehicle_make='Mazda', vehicle_model=label,
            reminder_days=30,
            next_service_date=today + timedelta(days=3),
            next_service_mileage=150000,
            current_odometer=140000,
        )
        db.session.add(car)
        db.session.flush()
        logged = VehicleService(
            organise_item_id=car.id,
            service_type='Service',
            service_date=today - timedelta(days=30),
            mileage=140000,
            next_service_date=today + timedelta(days=3),
            next_service_mileage=150000,
        )
        db.session.add(logged)
        db.session.commit()
        car_id = car.id
        service_id = logged.id

    try:
        assert len(_service_alerts(client, label)) == 1
        with client.session_transaction() as sess:
            sess['adult_mode'] = True
        cleared = client.put(f'/api/organise/{car_id}', json={
            'next_service_date': None,
            'next_service_mileage': None,
        })
        assert cleared.status_code == 200
        body = cleared.get_json()
        assert body['success'] is True
        assert body['item']['next_service_date'] is None
        assert body['item']['next_service_mileage'] is None
        assert body['item']['next_service_explicit'] is True
        assert _service_alerts(client, label) == []
    finally:
        with app.app_context():
            row = db.session.get(VehicleService, service_id)
            if row:
                db.session.delete(row)
            car = db.session.get(OrganiseItem, car_id)
            if car:
                db.session.delete(car)
            db.session.commit()
