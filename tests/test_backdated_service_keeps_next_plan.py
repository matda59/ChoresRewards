"""Adding an older service receipt must not replace the car's current next service."""

import uuid
from datetime import date, timedelta

from app import app, db
from models import ActivityLog, OrganiseItem, VehicleService


def test_backdated_service_keeps_the_current_plan_and_a_new_visit_updates_it():
    app.config['TESTING'] = True
    client = app.test_client()
    suffix = uuid.uuid4().hex[:8]
    today = date.today()
    planned = today + timedelta(days=180)
    with app.app_context():
        car = OrganiseItem(
            category='Car', title=f'Elgrand {suffix}',
            vehicle_make='Nissan', vehicle_model=f'Elgrand {suffix}',
            current_odometer=140000,
            next_service_date=planned,
            next_service_mileage=150000,
        )
        db.session.add(car)
        db.session.flush()
        latest = VehicleService(
            organise_item_id=car.id,
            service_type=f'Major service {suffix}',
            service_date=today - timedelta(days=20),
            mileage=140000,
            next_service_date=planned,
            next_service_mileage=150000,
        )
        db.session.add(latest)
        db.session.commit()
        car_id, latest_id = car.id, latest.id

    created_ids = []
    try:
        with client.session_transaction() as sess:
            sess['adult_mode'] = True

        older = client.post(f'/api/organise/{car_id}/services', json={
            'service_type': f'Old oil change {suffix}',
            'service_date': (today - timedelta(days=400)).isoformat(),
            'mileage': 90000,
            'next_service_date': (today - timedelta(days=200)).isoformat(),
            'next_service_mileage': 100000,
        })
        assert older.status_code == 200, older.get_json()
        created_ids.append(older.get_json()['service']['id'])
        with app.app_context():
            car = db.session.get(OrganiseItem, car_id)
            assert car.next_service_date == planned
            assert car.next_service_mileage == 150000
            assert car.current_odometer == 140000
            saved = db.session.get(VehicleService, created_ids[0])
            assert saved.next_service_mileage == 100000

        visit = client.post(f'/api/organise/{car_id}/services', json={
            'service_type': f'Brake fluid {suffix}',
            'service_date': today.isoformat(),
            'mileage': 141000,
            'next_service_date': (today + timedelta(days=300)).isoformat(),
            'next_service_mileage': 155000,
        })
        assert visit.status_code == 200, visit.get_json()
        created_ids.append(visit.get_json()['service']['id'])
        with app.app_context():
            car = db.session.get(OrganiseItem, car_id)
            assert car.next_service_date == today + timedelta(days=300)
            assert car.next_service_mileage == 155000
            assert car.current_odometer == 141000
    finally:
        with app.app_context():
            for service_id in created_ids + [latest_id]:
                row = db.session.get(VehicleService, service_id)
                if row:
                    db.session.delete(row)
            car = db.session.get(OrganiseItem, car_id)
            if car:
                db.session.delete(car)
            ActivityLog.query.filter(ActivityLog.description.contains(suffix)).delete(synchronize_session=False)
            db.session.commit()
