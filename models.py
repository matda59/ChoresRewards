from datetime import datetime, timedelta, date, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from zoneinfo import ZoneInfo

from sqlalchemy import func

from extensions import db  # Import db from extensions.py
import bcrypt

REWARD_SYSTEMS = ('points', 'cash', 'tech_time')
# Used only when Settings has no timezone. A saved timezone is the week boundary.
TECH_TIME_DEFAULT_ZONE = 'Australia/Melbourne'


class AppSetting(db.Model):
    @staticmethod
    def get_reward_system():
        # Returns 'points', 'cash', or 'tech_time'. Anything else is points.
        val = AppSetting.get('reward_system', 'points')
        return val if val in REWARD_SYSTEMS else 'points'

    @staticmethod
    def set_reward_system(system):
        if system not in REWARD_SYSTEMS:
            raise ValueError('Invalid reward system')
        AppSetting.set('reward_system', system)
    __tablename__ = 'app_settings'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.String(500), nullable=False)

    @staticmethod
    def get(key, default=None):
        setting = AppSetting.query.filter_by(key=key).first()
        return setting.value if setting else default

    @staticmethod
    def set(key, value):
        setting = AppSetting.query.filter_by(key=key).first()
        if setting:
            setting.value = value
        else:
            setting = AppSetting(key=key, value=value)
            db.session.add(setting)
        db.session.commit()

class Person(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    points = db.Column(db.Float, default=0.0)
    bonus_points = db.Column(db.Float, default=0.0)  # Track bonus points separately
    last_reset = db.Column(db.DateTime, default=datetime.utcnow)
    last_bonus_awarded = db.Column(db.DateTime, nullable=True)  # Track last bonus awarding date
    last_daily_chores_added = db.Column(db.DateTime, default=datetime.utcnow)  # New column
    avatar = db.Column(db.String(100), default='default_avatar.png')  # Add this line
    color = db.Column(db.String(7), default='#ffffff')  # Add this line
    order = db.Column(db.Integer, default=0)  # New field for kanban ordering
    pin = db.Column(db.String(20), nullable=True)  # PIN for person (setup wizard)
    is_admin = db.Column(db.Boolean, default=False)  # Is this person the adult/admin
    age = db.Column(db.Integer, nullable=True)  # Age for quiz difficulty filtering
    
    # Relationships to chores and rewards
    chores = db.relationship('Chore', backref='person', lazy=True)
    rewards = db.relationship('Reward', backref='person', lazy=True)

    def set_pin(self, raw_pin):
        """Hash and store a PIN or passphrase for this person."""
        hashed = bcrypt.hashpw(str(raw_pin).encode('utf-8'), bcrypt.gensalt())
        self.pin = hashed.decode('utf-8')

    def check_pin(self, raw_pin):
        """Return True if raw_pin matches the stored bcrypt hash."""
        from auth_guard import pin_matches
        return pin_matches(raw_pin, self.pin)

    def set_points(self, new_points):
        """
        Reset points to a specified value.
        Accepts a non-negative float as new_points.
        """
        try:
            new_points = float(new_points)
        except (ValueError, TypeError):
            raise ValueError("Points must be a number.")

        if new_points < 0:
            raise ValueError("Points cannot be negative.")

        self.points = new_points
        self.last_reset = datetime.utcnow()
        db.session.commit()
                
class Chore(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    assigned_to_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=True)
    assigned_to = db.Column(db.String(50))  # Keep for backward compatibility
    points = db.Column(db.Float, default=1.0)
    completed = db.Column(db.Boolean, default=False)
    date_completed = db.Column(db.DateTime)
    is_daily = db.Column(db.Boolean, default=False)  # Properly define is_daily as a Boolean
    days_of_week = db.Column(db.String(64), nullable=True)  # Comma-separated days, e.g. "Monday,Wednesday"
    due_date = db.Column(db.Date, nullable=True)  # For daily chore scheduling
    due_datetime = db.Column(db.DateTime, nullable=True)  # New field for due date and time
    deleted = db.Column(db.Boolean, default=False)  # New field to track deletion for daily chores
    icon = db.Column(db.String(20), nullable=True)  # Optional custom emoji icon
    is_extra = db.Column(db.Boolean, default=False)  # Claimed from the extra-chore catalog
    extra_id = db.Column(db.String(32), nullable=True)  # Catalog template id when is_extra
    
    def __init__(self, **kwargs):
        super(Chore, self).__init__(**kwargs)
        # Validate points are positive
        if self.points < 0:
            self.points = 0

    def to_dict(self):
        # ...existing code...
        days_of_week = self.days_of_week.split(',') if self.days_of_week else []
        """
        Convert chore object to dictionary for JSON responses.
        """
        return {
            'id': self.id,
            'title': self.title,
            'assigned_to': self.assigned_to,
            'points': self.points,
            'completed': self.completed,
            'is_daily': self.is_daily,
            'days_of_week': days_of_week,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'date_completed': self.date_completed.isoformat() if self.date_completed else None,
            'icon': self.icon
        }

    @staticmethod
    def calculate_weekly_progress(person_name):
        """
        Calculate weekly progress for a person by name.
        Returns (completed_chores, total_chores) for the current week.
        """
        today = datetime.utcnow().date()
        start_of_week = today - timedelta(days=today.weekday())  # Monday of the current week
        chores = Chore.query.filter_by(assigned_to=person_name).filter(
            Chore.date_completed >= start_of_week
        ).all()
        total_chores = len(chores)
        completed_chores = len([chore for chore in chores if chore.completed])
        return completed_chores, total_chores

    @staticmethod
    def clear_old_daily_chores():
        """
        Remove daily chores that have expired (i.e. their due_date is before today)
        to ensure only one set of daily chores exists for the current day.
        """
        today = datetime.utcnow().date()
        
        # Delete any daily chore with a due_date before today.
        old_daily_chores = Chore.query.filter(
            Chore.is_daily == True,
            Chore.due_date < today
        ).all()
        
        for chore in old_daily_chores:
            db.session.delete(chore)
        db.session.commit()

class Reward(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    points_required = db.Column(db.Float, nullable=False)
    image_url = db.Column(db.String(255), nullable=True)  # Added image_url field
    description = db.Column(db.Text, nullable=True)  # Added description field
    assigned_to_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=True)
    assigned_to = db.Column(db.String(50))  # Keep for backward compatibility
    completed = db.Column(db.Boolean, default=False)
    date_completed = db.Column(db.DateTime)

class ActivityLog(db.Model):
    """
    Model to track all activities/actions performed in the application.
    """
    __tablename__ = 'activity_log'
    
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    type = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(500), nullable=False)
    user_name = db.Column(db.String(100))
    
    def __repr__(self):
        return f'<ActivityLog {self.type}: {self.description}>'

# ── Badge / Streak models ──────────────────────────────────────────────────
BADGE_DEFINITIONS = {
    'first_chore': {'emoji': '⭐', 'name': 'First Steps',    'desc': 'Completed your very first chore!'},
    'chores_10':   {'emoji': '💪', 'name': '10 Chores!',     'desc': 'Completed 10 chores in total!'},
    'chores_50':   {'emoji': '🥇', 'name': 'Chore Champion', 'desc': 'Completed 50 chores!'},
    'chores_100':  {'emoji': '👑', 'name': 'Centurion',      'desc': '100 chores completed!'},
    'perfect_day': {'emoji': '🌟', 'name': 'Perfect Day',    'desc': 'All chores done in one day!'},
    'early_bird':  {'emoji': '🌅', 'name': 'Early Bird',     'desc': 'All chores finished before noon!'},
    'streak_3':    {'emoji': '🔥', 'name': '3-Day Streak',   'desc': '3 days in a row!'},
    'streak_7':    {'emoji': '🏅', 'name': 'On Fire!',       'desc': '7 days in a row!'},
    'streak_30':   {'emoji': '🏆', 'name': 'Legend',         'desc': '30-day streak!'},
}

class PersonStreak(db.Model):
    __tablename__ = 'person_streak'
    id = db.Column(db.Integer, primary_key=True)
    person_id = db.Column(db.Integer, db.ForeignKey('person.id'), unique=True, nullable=False)
    current_streak = db.Column(db.Integer, default=0)
    longest_streak = db.Column(db.Integer, default=0)
    last_completed_date = db.Column(db.Date, nullable=True)

class PersonBadge(db.Model):
    __tablename__ = 'person_badge'
    id = db.Column(db.Integer, primary_key=True)
    person_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=False)
    badge_key = db.Column(db.String(50), nullable=False)
    earned_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('person_id', 'badge_key', name='uq_person_badge'),)

class OrganiseItem(db.Model):
    __tablename__ = 'organise_item'
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(80), nullable=False, default='General')
    title = db.Column(db.String(200), nullable=False)
    provider = db.Column(db.String(200), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    due_date = db.Column(db.Date, nullable=True)
    last_date = db.Column(db.Date, nullable=True)
    paid = db.Column(db.Boolean, default=False)
    cost = db.Column(db.Float, nullable=True)
    reminder_days = db.Column(db.Integer, default=30)
    icon = db.Column(db.String(20), nullable=True)
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    photo_filename = db.Column(db.String(255), nullable=True)
    vehicle_make = db.Column(db.String(100), nullable=True)
    vehicle_model = db.Column(db.String(100), nullable=True)
    vehicle_year = db.Column(db.Integer, nullable=True)
    vehicle_rego = db.Column(db.String(20), nullable=True)
    current_odometer = db.Column(db.Integer, nullable=True)
    next_service_date = db.Column(db.Date, nullable=True)
    next_service_mileage = db.Column(db.Integer, nullable=True)
    # True once the next-service widget is saved. Empty date and km then mean
    # "no plan", including after the fields are cleared. Until then a car with
    # no plan of its own can still show the latest service log.
    next_service_explicit = db.Column(db.Boolean, default=False, nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('organise_item.id', ondelete='CASCADE'), nullable=True)
    vehicle_services = db.relationship('VehicleService', backref='vehicle', lazy=True,
                                       cascade='all, delete-orphan',
                                       order_by='VehicleService.service_date.desc()')

    def to_dict(self):
        today = date.today()
        status = 'ok'
        days_until_due = None
        if self.due_date:
            days_until_due = (self.due_date - today).days
            if not self.paid:
                if days_until_due < 0:
                    status = 'overdue'
                elif days_until_due <= (self.reminder_days or 30):
                    status = 'due_soon'
        return {
            'id': self.id,
            'category': self.category,
            'title': self.title,
            'provider': self.provider,
            'notes': self.notes,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'last_date': self.last_date.isoformat() if self.last_date else None,
            'paid': self.paid,
            'cost': self.cost,
            'reminder_days': self.reminder_days,
            'icon': self.icon,
            'sort_order': self.sort_order,
            'status': status,
            'days_until_due': days_until_due,
            'photo_url': f'/static/uploads/organise/{self.photo_filename}' if self.photo_filename else None,
            'vehicle_make': self.vehicle_make,
            'vehicle_model': self.vehicle_model,
            'vehicle_year': self.vehicle_year,
            'vehicle_rego': self.vehicle_rego,
            'current_odometer': self.current_odometer,
            'next_service_date': self.next_service_date.isoformat() if self.next_service_date else None,
            'next_service_mileage': self.next_service_mileage,
            'next_service_explicit': bool(self.next_service_explicit),
            'parent_id': self.parent_id,
        }


class OrganiseArchive(db.Model):
    """A paid period kept after a document is renewed or moved off the current list."""
    __tablename__ = 'organise_archive'
    id = db.Column(db.Integer, primary_key=True)
    organise_item_id = db.Column(db.Integer, db.ForeignKey('organise_item.id', ondelete='SET NULL'), nullable=True)
    title = db.Column(db.String(200), nullable=False)
    car_label = db.Column(db.String(200), nullable=True)
    provider = db.Column(db.String(200), nullable=True)
    icon = db.Column(db.String(20), nullable=True)
    cost = db.Column(db.Float, nullable=True)
    covered_until = db.Column(db.Date, nullable=True)
    paid_on = db.Column(db.Date, nullable=True)
    next_due = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'organise_item_id': self.organise_item_id,
            'title': self.title,
            'car_label': self.car_label or '',
            'provider': self.provider,
            'icon': self.icon,
            'cost': self.cost,
            'covered_until': self.covered_until.isoformat() if self.covered_until else None,
            'paid_on': self.paid_on.isoformat() if self.paid_on else None,
            'next_due': self.next_due.isoformat() if self.next_due else None,
        }


class VehicleService(db.Model):
    __tablename__ = 'vehicle_service'
    id = db.Column(db.Integer, primary_key=True)
    organise_item_id = db.Column(db.Integer, db.ForeignKey('organise_item.id', ondelete='CASCADE'), nullable=False)
    service_type = db.Column(db.String(200), nullable=False)
    service_date = db.Column(db.Date, nullable=True)
    next_service_date = db.Column(db.Date, nullable=True)
    next_service_mileage = db.Column(db.Integer, nullable=True)
    mileage = db.Column(db.Integer, nullable=True)
    cost = db.Column(db.Float, nullable=True)
    provider = db.Column(db.String(200), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'organise_item_id': self.organise_item_id,
            'service_type': self.service_type,
            'service_date': self.service_date.isoformat() if self.service_date else None,
            'next_service_date': self.next_service_date.isoformat() if self.next_service_date else None,
            'next_service_mileage': self.next_service_mileage,
            'mileage': self.mileage,
            'cost': self.cost,
            'provider': self.provider,
            'notes': self.notes,
        }


class TechTimeEntry(db.Model):
    """One credit or debit of weekend tech-time minutes.

    The balance for a week is the sum of rows with that Monday's ``week_start``.
    Older weeks stay in the table and simply stop counting, so expiry does not
    delete anything and does not touch the daily chore reset.
    """
    __tablename__ = 'tech_time_entry'
    id = db.Column(db.Integer, primary_key=True)
    person_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=False, index=True)
    minutes = db.Column(db.Integer, nullable=False)
    week_start = db.Column(db.Date, nullable=False, index=True)
    source = db.Column(db.String(32), nullable=False)
    chore_id = db.Column(db.Integer, nullable=True)
    note = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


def tech_time_zone():
    """Zone that starts and ends a tech-time week.

    A timezone saved in Settings is the site clock (the same one chore
    completions are stored in). With nothing saved, the week is
    Australia/Melbourne: unused minutes expire at Monday 00:00 there.
    """
    stored = (AppSetting.get('timezone') or '').strip()
    if stored:
        try:
            return ZoneInfo(stored)
        except Exception:
            pass
    return ZoneInfo(TECH_TIME_DEFAULT_ZONE)


def week_start_for_date(day):
    """Monday of the calendar week that contains ``day``."""
    return day - timedelta(days=day.weekday())


def week_start_for_instant(instant):
    """Monday for a completion instant.

    An aware instant is converted into the tech-time zone. A naive instant is
    already a wall time in that zone, which is how ``date_completed`` is stored.
    """
    if instant is None:
        instant = datetime.now(timezone.utc)
    if instant.tzinfo is None:
        local_day = instant.date()
    else:
        local_day = instant.astimezone(tech_time_zone()).date()
    return week_start_for_date(local_day)


def current_tech_week_start():
    return week_start_for_instant(datetime.now(timezone.utc))


def minutes_from_points(value):
    """Whole minutes a chore value is worth in Tech Time mode.

    Points and cash share this column. Half a point rounds up to one minute.
    Zero and anything that is not a number award nothing.
    """
    try:
        amount = Decimal(str(0 if value is None else value))
    except (InvalidOperation, ValueError, TypeError):
        return 0
    if not amount.is_finite() or amount <= 0:
        return 0
    return int(amount.quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def format_tech_minutes(minutes):
    """``130`` becomes ``2h 10m``. Zero is ``0m``. A negative balance keeps the sign."""
    try:
        total = int(minutes)
    except (TypeError, ValueError):
        total = 0
    sign = '-' if total < 0 else ''
    remaining = abs(total)
    hours, mins = divmod(remaining, 60)
    if hours and mins:
        return f'{sign}{hours}h {mins}m'
    if hours:
        return f'{sign}{hours}h'
    return f'{sign}{mins}m'


def tech_time_balance(person_id, week_start=None):
    if week_start is None:
        week_start = current_tech_week_start()
    total = db.session.query(func.sum(TechTimeEntry.minutes)).filter(
        TechTimeEntry.person_id == person_id,
        TechTimeEntry.week_start == week_start,
    ).scalar()
    return int(total or 0)


def tech_time_balances(person_ids, week_start=None):
    """Current-week minutes keyed by person id. Missing people are 0."""
    ids = [person_id for person_id in person_ids if person_id is not None]
    if week_start is None:
        week_start = current_tech_week_start()
    totals = {person_id: 0 for person_id in ids}
    if not ids:
        return totals
    rows = db.session.query(
        TechTimeEntry.person_id,
        func.sum(TechTimeEntry.minutes),
    ).filter(
        TechTimeEntry.person_id.in_(ids),
        TechTimeEntry.week_start == week_start,
    ).group_by(TechTimeEntry.person_id).all()
    for person_id, total in rows:
        totals[person_id] = int(total or 0)
    return totals


def log_activity(action_type, description, user_name=None):
    """
    Log an activity to the database.
    
    Args:
        action_type (str): Type of action (e.g., 'chore_added', 'chore_completed')
        description (str): Description of the action
        user_name (str, optional): Name of the user who performed the action
    """
    try:
        log_entry = ActivityLog(
            type=action_type,
            description=description,
            user_name=user_name
        )
        db.session.add(log_entry)
        db.session.commit()
        # Also print to stdout for container logs
        log_str = f"[ActivityLog] type={action_type} user={user_name} desc={description}"
        print(log_str, flush=True)
    except Exception as e:
        db.session.rollback()
        print(f"Error logging activity: {e}", flush=True)