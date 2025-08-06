from datetime import datetime, timedelta, date
from extensions import db  # Import db from extensions.py

class AppSetting(db.Model):
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
    points = db.Column(db.Integer, default=0)
    bonus_points = db.Column(db.Integer, default=0)  # Track bonus points separately
    last_reset = db.Column(db.DateTime, default=datetime.utcnow)
    last_daily_chores_added = db.Column(db.DateTime, default=datetime.utcnow)  # New column
    avatar = db.Column(db.String(100), default='default_avatar.png')  # Add this line
    color = db.Column(db.String(7), default='#ffffff')  # Add this line
    order = db.Column(db.Integer, default=0)  # New field for kanban ordering
    pin = db.Column(db.String(20), nullable=True)  # PIN for person (setup wizard)
    is_admin = db.Column(db.Boolean, default=False)  # Is this person the adult/admin
    
    # Relationships to chores and rewards
    chores = db.relationship('Chore', backref='person', lazy=True)
    rewards = db.relationship('Reward', backref='person', lazy=True)

    def set_points(self, new_points):
        """
        Reset points to a specified value.
        Accepts a non-negative integer as new_points.
        """
        try:
            new_points = int(new_points)
        except (ValueError, TypeError):
            raise ValueError("Points must be an integer value.")

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
    points = db.Column(db.Integer, default=1)
    completed = db.Column(db.Boolean, default=False)
    date_completed = db.Column(db.DateTime)
    is_daily = db.Column(db.Boolean, default=False)  # Properly define is_daily as a Boolean
    due_date = db.Column(db.Date, nullable=True)  # For daily chore scheduling
    deleted = db.Column(db.Boolean, default=False)  # New field to track deletion for daily chores
    
    def __init__(self, **kwargs):
        super(Chore, self).__init__(**kwargs)
        # Validate points are positive
        if self.points < 0:
            self.points = 0

    def to_dict(self):
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
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'date_completed': self.date_completed.isoformat() if self.date_completed else None
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
    points_required = db.Column(db.Integer, nullable=False)
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
    except Exception as e:
        db.session.rollback()
        print(f"Error logging activity: {e}")