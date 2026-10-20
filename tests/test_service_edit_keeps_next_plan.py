"""Editing a past service log must not replace the car's current next service."""

import uuid
from datetime import date, timedelta

from app import app, db
from models import ActivityLog, OrganiseItem, VehicleService


def test_resaving_a_service_log_keeps_the_rescheduled_plan():
    app.config['TESTING'] = True
    client = app.test_client()
    suffix = uuid.uuid4().hex[:8]
    today = date.today()
    planned = today + timedelta(days=200)
    rescheduled = today + timedelta(days=400)
    with app.app_context():
        car = OrganiseItem(
            category='Car', title=f'Elgrand {suffix}',
            vehicle_make='Nissan', vehicle_model=f'Elgrand {suffix}',
            current_odometer=100000,
            next_service_date=rescheduled,
            next_service_mileage=130000,
        )
        db.session.add(car)
        db.session.flush()
        older = VehicleService(
            organise_item_id=car.id,
            service_type=f'Oil change {suffix}',
            service_date=today - timedelta(days=400),
            mileage=80000,
            next_service_date=today - timedelta(days=200),
            next_service_mileage=90000,
            notes='old',
        )
        latest = VehicleService(
            organise_item_id=car.id,
            service_type=f'Major service {suffix}',
            service_date=today - timedelta(days=30),
            mileage=100000,
            next_service_date=planned,
            next_service_mileage=120000,
            notes='latest',
        )
        db.session.add(older)
        db.session.add(latest)
        db.session.commit()
        car_id, older_id, latest_id = car.id, older.id, latest.id

    created_id = None
    try:
        with client.session_transaction() as sess:
            sess['adult_mode'] = True

        # The edit form sends the log's own next-service fields even when
        # the only change is the notes.
        touched = client.put(f'/api/organise/{car_id}/services/{older_id}', json={
            'notes': 'used 5W-30',
            'next_service_date': (today - timedelta(days=200)).isoformat(),
            'next_service_mileage': 90000,
        })
        assert touched.status_code == 200, touched.get_json()

        with app.app_context():
            car = db.session.get(OrganiseItem, car_id)
            assert car.next_service_date == rescheduled
            assert car.next_service_mileage == 130000
            saved = db.session.get(VehicleService, older_id)
            assert saved.notes == 'used 5W-30'

        resaved = client.put(f'/api/organise/{car_id}/services/{latest_id}', json={
            'notes': 'invoice filed',
            'next_service_date': planned.isoformat(),
            'next_service_mileage': 120000,
        })
        assert resaved.status_code == 200, resaved.get_json()
        with app.app_context():
            car = db.session.get(OrganiseItem, car_id)
            assert car.next_service_date == rescheduled
            assert car.next_service_mileage == 130000

        moved = client.put(f'/api/organise/{car_id}/services/{latest_id}', json={
            'next_service_date': (today + timedelta(days=500)).isoformat(),
            'next_service_mileage': 140000,
        })
        assert moved.status_code == 200, moved.get_json()
        with app.app_context():
            car = db.session.get(OrganiseItem, car_id)
            assert car.next_service_date == today + timedelta(days=500)
            assert car.next_service_mileage == 140000

        # A new visit is the latest log, so its next service becomes the plan.
        created = client.post(f'/api/organise/{car_id}/services', json={
            'service_type': f'Brake fluid {suffix}',
            'service_date': today.isoformat(),
            'mileage': 141000,
            'next_service_date': (today + timedelta(days=600)).isoformat(),
            'next_service_mileage': 150000,
        })
        assert created.status_code == 200, created.get_json()
        created_id = created.get_json()['service']['id']
        with app.app_context():
            car = db.session.get(OrganiseItem, car_id)
            assert car.next_service_date == today + timedelta(days=600)
            assert car.next_service_mileage == 150000
            assert car.current_odometer == 141000

        # Correcting the next target stored on an older visit stays on that visit.
        corrected = client.put(f'/api/organise/{car_id}/services/{older_id}', json={
            'next_service_date': (today - timedelta(days=180)).isoformat(),
            'next_service_mileage': 95000,
        })
        assert corrected.status_code == 200, corrected.get_json()
        with app.app_context():
            car = db.session.get(OrganiseItem, car_id)
            assert car.next_service_date == today + timedelta(days=600)
            assert car.next_service_mileage == 150000
            older_row = db.session.get(VehicleService, older_id)
            assert older_row.next_service_mileage == 95000
    finally:
        with app.app_context():
            for service_id in (older_id, latest_id, created_id):
                row = db.session.get(VehicleService, service_id)
                if row:
                    db.session.delete(row)
            car = db.session.get(OrganiseItem, car_id)
            if car:
                db.session.delete(car)
            ActivityLog.query.filter(ActivityLog.description.contains(suffix)).delete(synchronize_session=False)
            db.session.commit()
