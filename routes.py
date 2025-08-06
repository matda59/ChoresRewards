from flask import Blueprint, render_template, request, redirect, url_for, jsonify, current_app
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta, timezone, date
import os
import uuid
import random
from collections import defaultdict
from zoneinfo import ZoneInfo
from extensions import db
from models import Person, Chore, Reward, ActivityLog, log_activity
from flask import session, redirect, url_for
from flask import session
from collections import defaultdict

# Create a single Blueprint for all routes
routes_bp = Blueprint('routes', __name__)

@routes_bp.route('/api/bonus_settings', methods=['GET'])
def api_bonus_settings():
    from models import AppSetting
    bonus_mode = AppSetting.get('bonus_mode', 'static')
    bonus_static = AppSetting.get('bonus_static', '10')
    bonus_min = AppSetting.get('bonus_min', '2')
    bonus_max = AppSetting.get('bonus_max', '8')
    return jsonify({
        'bonus_mode': bonus_mode,
        'bonus_static': bonus_static,
        'bonus_min': bonus_min,
        'bonus_max': bonus_max
    })

import bcrypt
from flask import session

# Remove the old get_master_pin endpoint
# @routes_bp.route('/api/get_master_pin', methods=['GET'])
# def api_get_master_pin():
#     from models import AppSetting
#     master_pin = AppSetting.get('master_pin')
#     if master_pin is None:
#         return jsonify({'success': False, 'error': 'Master PIN not set'}), 404
#     return jsonify({'success': True, 'master_pin': master_pin})

# Configure upload folder and allowed extensions
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_person_by_name(name):
    """
    Retrieve a person object from the database by name.
    """
    return Person.query.filter_by(name=name).first()


def reset_daily_chores():
    """
    For each daily chore, if its due_date is before today then:
      - Mark it as not completed (so it reappears), and
      - Update its due_date to today.
    This ensures daily chores reoccur each day until deleted, and allows skipping a day.
    IMPORTANT: Only resets chores that are daily AND NOT marked as deleted.
    """
    today = date.today()
    print(f"[reset_daily_chores] Running daily chore reset for {today}")

    # Only select chores that are:
    # 1. Daily chores (is_daily=True)
    # 2. NOT marked as deleted (deleted=False)
    daily_chores = Chore.query.filter_by(is_daily=True, deleted=False).all()

    # Debug print each daily chore
    for chore in daily_chores:
        print(f"[reset_daily_chores] Found daily chore: ID={chore.id}, Title='{chore.title}', deleted={chore.deleted}, due_date={chore.due_date}")

    updated = False
    reset_count = 0

    for chore in daily_chores:
        # Ensure the due_date is a date object (not datetime)
        chore_date = chore.due_date.date() if isinstance(chore.due_date, datetime) else chore.due_date

        if chore_date is None or chore_date < today:
            print(f"[reset_daily_chores] Resetting chore: ID={chore.id}, Title='{chore.title}'")
            chore.completed = False
            chore.due_date = today
            updated = True
            reset_count += 1

    if updated:
        db.session.commit()
        print(f"[reset_daily_chores] Reset {reset_count} daily chores")
        if reset_count > 0:
            log_activity('daily_chores_reset', f"{reset_count} daily chores were reset for today")
    else:
        print("[reset_daily_chores] No chores needed to be reset")

@routes_bp.route('/')
def index():
    from models import AppSetting
    master_pin = AppSetting.get('master_pin')
    # First-run setup wizard: if no people exist, redirect to setup
    if Person.query.count() == 0:
        return redirect(url_for('routes.setup_wizard'))
    reset_daily_chores()
    from datetime import date
    chores = Chore.query.filter(
        Chore.deleted == False,
        ((Chore.is_daily == False) | (Chore.due_date <= date.today()))
    ).order_by(Chore.due_date).all()
    rewards = Reward.query.all()
    family = Person.query.all()

    family_progress = {}
    for person in family:
        completed, total = Chore.calculate_weekly_progress(person.name)
        family_progress[person.name] = {
            'completed': completed,
            'total': total
        }

    # --- Celebration: pop the session flag and pass to template ---
    celebrate_person = session.pop('celebrate_person', None)
    celebrate_avatar = session.pop('celebrate_avatar', None)

    return render_template(
        'index.html',
        chores=chores,
        rewards=rewards,
        family=family,
        family_progress=family_progress,
        get_person_by_name=get_person_by_name,
        celebrate_person=celebrate_person,
        celebrate_avatar=celebrate_avatar,
        master_pin_set=bool(master_pin)
    )

@routes_bp.route('/setup', methods=['GET', 'POST'])
def setup_wizard():
    import bcrypt
    # Check if master PIN is set in app settings
    from models import AppSetting
    master_pin = AppSetting.get('master_pin')
    if master_pin:
        # Master PIN already set, redirect to index
        return redirect(url_for('routes.index'))

    if request.method == 'POST':
        people = request.form.getlist('people[]')
        master_pin = request.form.get('master_pin')
        # Hash the master pin before saving
        hashed_pin = bcrypt.hashpw(master_pin.encode('utf-8'), bcrypt.gensalt())
        hashed_pin_str = hashed_pin.decode('utf-8')
        for name in people:
            person = Person(name=name)
            db.session.add(person)
        # Save hashed master PIN in app settings
        AppSetting.set('master_pin', hashed_pin_str)
        db.session.commit()
        return redirect(url_for('routes.index'))
    # Pass existing people to the template
    people = Person.query.all()
    master_pin_set = bool(master_pin)
    return render_template('setup_wizard.html', people=people, master_pin_set=master_pin_set)

@routes_bp.route('/api/login', methods=['POST'])
def api_login():
    # New login endpoint to verify pin and create session
    from models import AppSetting
    import bcrypt
    data = request.get_json()
    if not data or 'pin' not in data:
        return jsonify({'success': False, 'error': 'PIN is required'}), 400
    pin = data['pin']
    master_pin_hash = AppSetting.get('master_pin')
    if not master_pin_hash:
        return jsonify({'success': False, 'error': 'Master PIN not set'}), 500
    if bcrypt.checkpw(pin.encode('utf-8'), master_pin_hash.encode('utf-8')):
        session['authenticated'] = True
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': 'Incorrect PIN'}), 401

@routes_bp.route('/complete_chore', methods=['POST'])
def complete_chore():
    try:
        chore_id = request.json.get('chore_id')
        chore = Chore.query.get(chore_id)
        if not chore:
            return jsonify({
                'success': False,
                'error': 'Chore not found'
            }), 404

        chore.completed = True
        chore.date_completed = datetime.utcnow()

        person = Person.query.filter_by(name=chore.assigned_to).first()

        points_awarded = 0
        bonus_awarded = 0
        if person:
            person.points += chore.points
            points_awarded = chore.points
            db.session.commit()
            session['celebrate_person'] = chore.assigned_to
            if person.avatar:
                session['celebrate_avatar'] = person.avatar
            else:
                session['celebrate_avatar'] = 'default_avatar.png'
            log_activity(
                'chore_completed',
                f"Chore '{chore.title}' was completed and {chore.points} points were awarded",
                user_name=chore.assigned_to
            )
        db.session.commit()

        completed, total = Chore.calculate_weekly_progress(chore.assigned_to)

        return jsonify({
            'success': True,
            'assigned_to': chore.assigned_to,
            'progress': {
                'completed': completed,
                'total': total
            },
            'new_points': (person.points + person.bonus_points) if person else 0,
            'points_awarded': points_awarded,
            'bonus_awarded': bonus_awarded
        })

    except Exception as e:
        db.session.rollback()
        log_activity('system_error', f"Error completing chore: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@routes_bp.route('/add_person', methods=['POST'])
def add_person():
    try:
        if request.is_json:
            data = request.get_json()
            name = data.get('name', '').strip()
            if not name:
                return jsonify({'success': False, 'error': 'Name is required'}), 400
            names = [name]
        else:
            names = request.form.getlist('people[]')
            if not names:
                name = request.form.get('name', '').strip()
                if not name:
                    return jsonify({'success': False, 'error': 'Name is required'}), 400
                names = [name]

        added_people = []
        for name in names:
            name = name.strip()
            if not name:
                continue
            if Person.query.filter_by(name=name).first():
                continue
            person = Person(name=name)
            db.session.add(person)
            added_people.append(person)

        if not added_people:
            return jsonify({'success': False, 'error': 'No valid new names to add'}), 400

        db.session.commit()

        for person in added_people:
            log_activity('family_member_added', f"Family member '{person.name}' was added to the system")

        return jsonify({
            'success': True,
            'people': [{'id': p.id, 'name': p.name, 'points': p.points, 'avatar': p.avatar, 'color': p.color} for p in added_people]
        })
    except Exception as e:
        db.session.rollback()
        print(f"[add_person] Exception: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@routes_bp.route('/delete_person', methods=['POST'])
def delete_person():
    try:
        data = request.get_json()
        print(f"[delete_person] Received data: {data}")
        person_id = data.get('person_id')
        person = Person.query.get(person_id)
        if not person:
            print(f"[delete_person] Person id {person_id} not found.")
            return jsonify({'success': False, 'error': 'Person not found'}), 404
        db.session.delete(person)
        db.session.commit()
        log_activity('family_member_deleted', f"Family member '{person.name}' was deleted from the system")
        print(f"[delete_person] Person '{person.name}' deleted successfully.")
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        print(f"[delete_person] Exception: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@routes_bp.route('/activity_log')
def activity_log():
    """Display all activity logs in chronological order (newest first) and provide chart data."""
    try:
        # Get filter parameters
        filter_type = request.args.get('type', '')
        filter_user = request.args.get('user', '')
        
        # Base query
        query = ActivityLog.query
        
        # Apply filters if provided
        if filter_type:
            query = query.filter(ActivityLog.type == filter_type)
        if filter_user:
            query = query.filter(ActivityLog.user_name == filter_user)
        
        # Get all logs ordered by date (newest first)
        logs = query.order_by(ActivityLog.date.desc()).all()
        # Convert timestamps to Australia/Sydney timezone for display
        syd = ZoneInfo("Australia/Sydney")
        for lg in logs:
            # Ensure datetime is timezone-aware in UTC
            if lg.date.tzinfo is None:
                aware = lg.date.replace(tzinfo=timezone.utc)
            else:
                aware = lg.date.astimezone(timezone.utc)
            lg.local_date = aware.astimezone(syd)
        
        # Get unique types and users for filter dropdowns
        all_types = db.session.query(ActivityLog.type).distinct().all()
        all_users = db.session.query(ActivityLog.user_name).filter(ActivityLog.user_name.isnot(None)).distinct().all()
        
        activity_types = [t[0] for t in all_types]
        activity_users = [u[0] for u in all_users]

        # --- CHART DATA SECTION ---

        # 1. Chores Completed by Person
        people = Person.query.all()
        chores_by_person_raw = {p.name: 0 for p in people}
        completed_chores = Chore.query.filter(
            Chore.completed == True,
            Chore.deleted == False
        ).all()
        for chore in completed_chores:
            person_name = chore.assigned_to
            if person_name in chores_by_person_raw:
                chores_by_person_raw[person_name] += 1

        # Convert chores_by_person to Chart.js pie chart data format
        chores_by_person = {
            'labels': list(chores_by_person_raw.keys()),
            'datasets': [{
                'data': list(chores_by_person_raw.values()),
                'backgroundColor': [
                    '#FF6384', '#36A2EB', '#FFCE56', '#8BC34A',
                    '#FF9800', '#9C27B0', '#607D8B', '#795548'
                ],
                'hoverBackgroundColor': [
                    '#FF6384', '#36A2EB', '#FFCE56', '#8BC34A',
                    '#FF9800', '#9C27B0', '#607D8B', '#795548'
                ]
            }]
        }

        # 2. Monthly Summary (Chores per Person)
        today_date = date.today()
        first_of_month = today_date.replace(day=1)
        monthly_chores_by_person_raw = defaultdict(int)
        for chore in completed_chores:
            if chore.date_completed and chore.date_completed.date() >= first_of_month:
                if chore.assigned_to:
                    monthly_chores_by_person_raw[chore.assigned_to] += 1

        # Convert monthly_chores_by_person to Chart.js bar chart data format
        monthly_chores_by_person = {
            'labels': list(monthly_chores_by_person_raw.keys()),
            'datasets': [{
                'label': 'Chores Completed',
                'data': list(monthly_chores_by_person_raw.values()),
                'backgroundColor': '#36A2EB'
            }]
        }

        # 3. Top Tasks Trend (per Person, last 4 weeks)
        trend_weeks = []
        week_starts = []
        for i in range(4, 0, -1):
            week_start = today_date - timedelta(days=today_date.weekday() + 7 * (i - 1))
            week_starts.append(week_start)
            trend_weeks.append(week_start.strftime('%Y-%m-%d'))

        person_task_week_counts = defaultdict(lambda: defaultdict(lambda: [0, 0, 0, 0]))
        for chore in completed_chores:
            if chore.assigned_to and chore.date_completed:
                for idx, week_start in enumerate(week_starts):
                    week_end = week_start + timedelta(days=6)
                    if week_start <= chore.date_completed.date() <= week_end:
                        person_task_week_counts[chore.assigned_to][chore.title][idx] += 1

        # Convert top_tasks_trend to Chart.js line chart data format
        top_tasks_trend = {
            person: {
                'labels': trend_weeks,
                'datasets': []
            } for person in person_task_week_counts.keys()
        }
        color_palette = [
            '#FF6384', '#36A2EB', '#FFCE56', '#8BC34A',
            '#FF9800', '#9C27B0', '#607D8B', '#795548'
        ]
        for person, task_counts in person_task_week_counts.items():
            task_totals = {task: sum(counts) for task, counts in task_counts.items()}
            top_tasks = sorted(task_totals.items(), key=lambda x: x[1], reverse=True)[:3]
            for idx, (task, _) in enumerate(top_tasks):
                color = color_palette[idx % len(color_palette)]
                top_tasks_trend[person]['datasets'].append({
                    'label': task,
                    'data': task_counts[task],
                    'borderColor': color,
                    'backgroundColor': color,
                    'fill': False,
                    'tension': 0.1
                })

        # 4. All Chores Each Year
        chores_per_year = defaultdict(int)
        for chore in completed_chores:
            if chore.date_completed:
                year = chore.date_completed.year
                chores_per_year[year] += 1

        # Convert defaultdicts to dicts for JSON serialization in Jinja
        monthly_chores_by_person = dict(monthly_chores_by_person)
        chores_per_year = dict(chores_per_year)

        return render_template(
            'activity_log.html', 
            activity_logs=logs,
            activity_types=activity_types,
            activity_users=activity_users,
            current_type_filter=filter_type,
            current_user_filter=filter_user,
            chores_by_person=chores_by_person,
            monthly_chores_by_person=monthly_chores_by_person,
            top_tasks_trend=top_tasks_trend,
            trend_weeks=trend_weeks,
            chores_per_year=chores_per_year
        )
    except Exception as e:
        log_activity('system_error', f"Error loading activity log: {str(e)}")
        # Always pass chart variables as empty to avoid template errors
        return render_template(
            'activity_log.html',
            activity_logs=[],
            error=str(e),
            activity_types=[],
            activity_users=[],
            current_type_filter='',
            current_user_filter='',
            chores_by_person={},
            monthly_chores_by_person={},
            top_tasks_trend={},
            trend_weeks=[],
            chores_per_year={}
        )

@routes_bp.route('/add_reward', methods=['POST'])
def add_reward():
    title = request.form.get('title')
    points_required = int(request.form.get('points_required'))
    assigned_to = request.form.get('assigned_to')
    
    new_reward = Reward(title=title, points_required=points_required, assigned_to=assigned_to)
    db.session.add(new_reward)
    db.session.commit()
    
    # Log the activity
    log_activity(
        'reward_added',
        f"Reward '{title}' worth {points_required} points was added for {assigned_to}",
        user_name=assigned_to
    )
    
    return redirect(url_for('routes.index'))

from models import AppSetting

@routes_bp.route('/award_bonus_points', methods=['POST'])
def award_bonus_points():
    try:
        data = request.get_json()
        person_id = data.get('person_id')
        bonus_points = data.get('bonus_points')

        if not person_id or bonus_points is None:
            return jsonify({'success': False, 'message': 'Missing person_id or bonus_points'}), 400

        # Get bonus settings
        bonus_mode = AppSetting.get('bonus_mode', 'static')
        bonus_static = AppSetting.get('bonus_static')
        bonus_min = AppSetting.get('bonus_min')
        bonus_max = AppSetting.get('bonus_max')

        # Validate bonus_points against settings
        if bonus_mode == 'static':
            try:
                allowed = int(bonus_static)
            except (TypeError, ValueError):
                allowed = 10  # fallback default
            if int(bonus_points) != allowed:
                return jsonify({'success': False, 'message': f'Bonus must be exactly {allowed} points.'}), 400
        elif bonus_mode == 'range':
            try:
                min_val = int(bonus_min)
                max_val = int(bonus_max)
            except (TypeError, ValueError):
                min_val, max_val = 2, 8  # fallback default
            if not (min_val <= int(bonus_points) <= max_val):
                return jsonify({'success': False, 'message': f'Bonus must be between {min_val} and {max_val} points.'}), 400
        else:
            return jsonify({'success': False, 'message': 'Invalid bonus mode.'}), 400

        # Find the person in your database
        person = Person.query.get(person_id)
        if not person:
            return jsonify({'success': False, 'message': 'Person not found'}), 404

        # Add bonus points to permanent points and reset bonus_points
        person.points += int(bonus_points)
        person.bonus_points = 0
        db.session.commit()
        # Log the bonus points activity
        log_activity(
            'bonus_points_awarded',
            f"{bonus_points} bonus points were awarded to {person.name}",
            user_name=person.name
        )
        return jsonify({
            'success': True,
            'new_points': person.points,
            'bonus_awarded': bonus_points
        })

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@routes_bp.route('/add_chore', methods=['POST'])
def add_chore():
    try:
        if request.is_json:
            data = request.get_json()
            title = data.get('title')
            assigned_to = data.get('assigned_to')
            points = int(data.get('points', 1))
            is_daily = str(data.get('is_daily', '')).lower() in ('on', 'true', '1')
        else:
            title = request.form.get('title')
            assigned_to = request.form.get('assigned_to')
            points = int(request.form.get('points', 1))
            is_daily = request.form.get('is_daily', '').lower() in ('on', 'true', '1')
        
        if not title or not assigned_to:
            return jsonify(success=False, error="Title and Assigned To are required fields.")
        
        # Look up the person by name
        person = Person.query.filter_by(name=assigned_to).first()
        if not person:
            return jsonify(success=False, error="Assigned person not found.")

        new_chore = Chore(
            title=title,
            assigned_to=person.name,
            assigned_to_id=person.id,
            points=points,
            is_daily=is_daily,
            completed=False,
            date_completed=None,
            due_date=date.today() if is_daily else None
        )
        
        db.session.add(new_chore)
        db.session.commit()
        
        # Log the activity
        chore_type = "daily chore" if is_daily else "chore"
        log_activity(
            'chore_added',
            f"{chore_type.title()} '{title}' worth {points} points was added for {assigned_to}",
            user_name=assigned_to
        )
        
        return jsonify({
            'success': True,
            'chore_id': new_chore.id,
            'is_daily': new_chore.is_daily
        })
        
    except Exception as e:
        db.session.rollback()
        log_activity('system_error', f"Error adding chore: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
    
@routes_bp.route('/upload_avatar/<int:person_id>', methods=['POST'])
def upload_avatar(person_id):
    person = Person.query.get(person_id)
    if not person:
        return jsonify(success=False, message="Person not found")

    if 'avatar' not in request.files:
        return jsonify(success=False, message="No file uploaded")

    file = request.files['avatar']
    if file.filename == '':
        return jsonify(success=False, message="No file selected")

    if file and allowed_file(file.filename):
        # Ensure the upload folder exists
        upload_folder = os.path.join(current_app.root_path, current_app.config.get('UPLOAD_FOLDER', UPLOAD_FOLDER))
        os.makedirs(upload_folder, exist_ok=True)
        
        # Generate a unique filename
        ext = os.path.splitext(secure_filename(file.filename))[1]
        unique_filename = f"{person_id}_{uuid.uuid4().hex}{ext}"
        filepath = os.path.join(upload_folder, unique_filename)
        file.save(filepath)
        
        # Optionally, delete the old avatar file if it exists and isn't a default
        if person.avatar and not person.avatar.startswith('default_'):
            old_path = os.path.join(upload_folder, person.avatar)
            if os.path.exists(old_path):
                try:
                    os.remove(old_path)
                except Exception:
                    pass

        person.avatar = unique_filename
        db.session.commit()
        
        # Log the activity
        log_activity(
            'avatar_updated',
            f"Avatar was updated for {person.name}",
            user_name=person.name
        )

        # Add cache-busting query param
        avatar_url = url_for('static', filename=f'uploads/{unique_filename}') + f'?v={uuid.uuid4().hex[:8]}'
        return jsonify(success=True, avatar_url=avatar_url)
    else:
        return jsonify(success=False, message="Invalid file type")

@routes_bp.route('/settings', methods=['GET', 'POST'])
def settings():
    import bcrypt
    from models import AppSetting, Person
    error = None
    success = None
    if request.method == 'POST':
        # Save bonus points settings
        if 'bonus_mode' in request.form:
            bonus_mode = request.form.get('bonus_mode', 'static')
            AppSetting.set('bonus_mode', bonus_mode)
            if bonus_mode == 'static':
                AppSetting.set('bonus_static', request.form.get('bonus_static', '10'))
                AppSetting.set('bonus_min', '')
                AppSetting.set('bonus_max', '')
            elif bonus_mode == 'range':
                AppSetting.set('bonus_min', request.form.get('bonus_min', '2'))
                AppSetting.set('bonus_max', request.form.get('bonus_max', '8'))
                AppSetting.set('bonus_static', '')
            log_activity('settings_updated', f"Bonus points configuration was updated")
        elif 'chores' in request.form:
            chores = request.form.get('chores').split(',')
            log_activity('settings_updated', f"Chores configuration was updated")
        elif 'reset_day' in request.form:
            reset_day = int(request.form.get('reset_day'))
            log_activity('settings_updated', f"Reset day was changed to {reset_day}")
        elif 'change_pin' in request.form:
            current_pin = request.form.get('current_pin')
            new_pin = request.form.get('new_pin')
            confirm_pin = request.form.get('confirm_pin')

            master_pin = AppSetting.get('master_pin')

            print(f"[settings] change_pin POST received: current_pin={current_pin}, new_pin={new_pin}, confirm_pin={confirm_pin}, stored_master_pin={master_pin}")

            if not current_pin or not new_pin or not confirm_pin:
                error = "All fields are required."
            elif new_pin != confirm_pin:
                error = "New PIN and confirmation do not match."
            elif not bcrypt.checkpw(current_pin.encode('utf-8'), master_pin.encode('utf-8')):
                error = "Current PIN is incorrect."
            else:
                hashed_new_pin = bcrypt.hashpw(new_pin.encode('utf-8'), bcrypt.gensalt())
                hashed_new_pin_str = hashed_new_pin.decode('utf-8')
                AppSetting.set('master_pin', hashed_new_pin_str)
                db.session.commit()
                log_activity('master_pin_changed', "Master PIN was changed")
                success = "Master PIN changed successfully."

    # Load bonus points settings
    bonus_mode = AppSetting.get('bonus_mode', 'static')
    bonus_static = AppSetting.get('bonus_static', '10')
    bonus_min = AppSetting.get('bonus_min', '2')
    bonus_max = AppSetting.get('bonus_max', '8')

    daily_chores = Chore.query.filter_by(is_daily=True, deleted=False).all()
    family = Person.query.all()

    return render_template(
        'settings.html',
        daily_chores=daily_chores,
        bonus_mode=bonus_mode,
        bonus_static=bonus_static,
        bonus_min=bonus_min,
        bonus_max=bonus_max,
        family=family,
        error=error,
        success=success
    )

# New API endpoint to list all sound files in static/sounds
@routes_bp.route('/api/sounds', methods=['GET'])
def list_sounds():
    sounds_dir = os.path.join(current_app.root_path, 'static', 'sounds')
    try:
        files = os.listdir(sounds_dir)
        # Filter for supported audio files (mp3, wav, ogg)
        supported_exts = ('.mp3', '.wav', '.ogg')
        sound_files = [f for f in files if f.lower().endswith(supported_exts)]
        return jsonify({'success': True, 'sounds': sound_files})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# New API endpoint to upload a sound file to static/sounds
@routes_bp.route('/api/sounds/upload', methods=['POST'])
def upload_sound():
    if 'sound_file' not in request.files:
        return jsonify({'success': False, 'error': 'No file part'}), 400
    file = request.files['sound_file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No selected file'}), 400
    # Validate file extension
    allowed_exts = ('.mp3', '.wav', '.ogg')
    if not file.filename.lower().endswith(allowed_exts):
        return jsonify({'success': False, 'error': 'Unsupported file type'}), 400
    sounds_dir = os.path.join(current_app.root_path, 'static', 'sounds')
    os.makedirs(sounds_dir, exist_ok=True)
    filename = secure_filename(file.filename)
    filepath = os.path.join(sounds_dir, filename)
    # Save file
    file.save(filepath)
    return jsonify({'success': True, 'filename': filename})

# New API endpoint to delete a sound file from static/sounds
@routes_bp.route('/api/sounds/delete', methods=['POST'])
def delete_sound():
    data = request.get_json()
    filename = data.get('filename')
    if not filename:
        return jsonify({'success': False, 'error': 'Filename required'}), 400
    sounds_dir = os.path.join(current_app.root_path, 'static', 'sounds')
    filepath = os.path.join(sounds_dir, filename)
    if not os.path.exists(filepath):
        return jsonify({'success': False, 'error': 'File not found'}), 404
    try:
        os.remove(filepath)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@routes_bp.route('/add_daily_chore', methods=['POST'])
def add_daily_chore():
    try:
        if request.is_json:
            data = request.get_json()
            title = data.get('title')
            assigned_to = data.get('assigned_to')
            points = int(data.get('points', 1))
        else:
            title = request.form.get('title')
            assigned_to = request.form.get('assigned_to')
            points = int(request.form.get('points', 1))
        if not title or not assigned_to:
            return jsonify({
                'success': False,
                'error': "Title and Assigned To are required fields."
            }), 400
        # Default to today's date for daily chores
        due_date = date.today()
        # Look up the person by name to get their ID
        person = Person.query.filter_by(name=assigned_to).first()
        assigned_to_id = person.id if person else None
        new_chore = Chore(
            title=title,
            assigned_to=assigned_to,
            assigned_to_id=assigned_to_id,
            points=points,
            completed=False,
            date_completed=None,
            is_daily=True,
            due_date=due_date
        )
        db.session.add(new_chore)
        db.session.commit()
        # Log the activity
        log_activity(
            'daily_chore_added',
            f"Daily chore '{title}' worth {points} points was added for {assigned_to}",
            user_name=assigned_to
        )
        completed, total = Chore.calculate_weekly_progress(assigned_to)
        return jsonify({
            'success': True,
            'chore_id': new_chore.id,
            'progress': {
                'completed': completed,
                'total': total
            }
        })
    except Exception as e:
        db.session.rollback()
        log_activity('system_error', f"Error adding daily chore: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

# --- EDIT DAILY CHORE ROUTE ---
@routes_bp.route('/edit_daily_chore', methods=['POST'])
def edit_daily_chore():
    try:
        if not request.is_json:
            return jsonify({'success': False, 'error': 'JSON required'}), 400
        data = request.get_json()
        chore_id = data.get('chore_id')
        title = data.get('title')
        assigned_to = data.get('assigned_to')
        points = int(data.get('points', 1))
        if not chore_id or not title or not assigned_to:
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400
        chore = Chore.query.get(chore_id)
        if not chore or not chore.is_daily:
            return jsonify({'success': False, 'error': 'Daily chore not found'}), 404
        chore.title = title
        chore.assigned_to = assigned_to
        # Update assigned_to_id based on assigned_to name
        person = Person.query.filter_by(name=assigned_to).first()
        chore.assigned_to_id = person.id if person else None
        chore.points = points
        db.session.commit()
        log_activity('daily_chore_edited', f"Daily chore '{title}' was edited for {assigned_to}", user_name=assigned_to)
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        log_activity('system_error', f"Error editing daily chore: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 400

# --- DELETE DAILY CHORE ROUTE ---
@routes_bp.route('/delete_daily_chore', methods=['POST'])
def delete_daily_chore():
    """
    Delete a daily chore permanently by marking it as deleted.
    This is a specialized endpoint for daily chores only.
    """
    try:
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No JSON data provided'}), 400
            
        chore_id = data.get('chore_id')
        
        print(f"[delete_daily_chore] Received data: chore_id={chore_id}")
        
        # Validate chore_id
        if not chore_id:
            return jsonify({'success': False, 'error': 'Chore ID is required'}), 400
            
        # Find the chore
        chore = Chore.query.get(chore_id)
        if not chore:
            return jsonify({'success': False, 'error': 'Chore not found'}), 404
            
        # Verify it's a daily chore
        if not chore.is_daily:
            return jsonify({'success': False, 'error': 'This endpoint is only for daily chores'}), 400
        
        # Store chore details for logging
        chore_title = chore.title
        chore_assigned_to = chore.assigned_to
        
        print(f"[delete_daily_chore] Processing daily chore: '{chore_title}' (ID: {chore_id})")
        
        # Mark daily chore as deleted
        chore.deleted = True
        db.session.commit()
        
        # Log the activity
        log_activity(
            'daily_chore_deleted', 
            f"Daily chore '{chore_title}' was permanently deleted for {chore_assigned_to}", 
            user_name=chore_assigned_to
        )
        
        message = f"Daily chore '{chore_title}' has been permanently deleted"
        print(f"[delete_daily_chore] Success: {message}")
        
        return jsonify({
            'success': True,
            'message': message,
            'chore_id': chore_id
        })
        
    except Exception as e:
        db.session.rollback()
        error_msg = f"Error deleting daily chore: {str(e)}"
        print(f"[delete_daily_chore] Exception: {error_msg}")
        log_activity('system_error', error_msg)
        return jsonify({'success': False, 'error': error_msg}), 500

@routes_bp.route('/delete_chore', methods=['POST'])
def delete_chore():
    """
    Delete a chore (daily or non-daily).
    For daily chores: permanent=True marks as deleted, permanent=False skips for today only.
    For non-daily chores: always permanently deleted from database.
    """
    try:
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No JSON data provided'}), 400
            
        chore_id = data.get('chore_id')
        permanent = data.get('permanent', False)

        print(f"[delete_chore] Received data: chore_id={chore_id}, permanent={permanent}")
        
        # Validate chore_id
        if not chore_id:
            return jsonify({'success': False, 'error': 'Chore ID is required'}), 400

        # Find the chore
        chore = Chore.query.get(chore_id)
        if not chore:
            return jsonify({'success': False, 'error': 'Chore not found'}), 404
        
        # Store chore details for logging
        chore_title = chore.title
        chore_assigned_to = chore.assigned_to
        is_daily = chore.is_daily
        
        print(f"[delete_chore] Processing chore: '{chore_title}' (ID: {chore_id}, Daily: {is_daily})")
        
        # Handle deletion based on chore type
        if is_daily:
            if permanent:
                # Permanently delete daily chore by marking as deleted
                print("[delete_chore] Permanently deleting daily chore")
                chore.deleted = True
                db.session.commit()
                
                log_activity(
                    'daily_chore_deleted',
                    f"Daily chore '{chore_title}' was permanently deleted for {chore_assigned_to}",
                    user_name=chore_assigned_to
                )
                message = f"Daily chore '{chore_title}' has been permanently deleted"
            else:
                # Skip daily chore for today only
                print("[delete_chore] Skipping daily chore for today")
                chore.due_date = date.today() + timedelta(days=1)
                db.session.commit()
                
                log_activity(
                    'daily_chore_skipped',
                    f"Daily chore '{chore_title}' was skipped\deleted for today for {chore_assigned_to}",
                    user_name=chore_assigned_to
                )
                message = f"Daily chore '{chore_title}' has been skipped for today"
        else:
            # Permanently delete non-daily chore from database
            print("[delete_chore] Permanently deleting non-daily chore")
            db.session.delete(chore)
            db.session.commit()
            
            log_activity(
                'chore_deleted',
                f"Chore '{chore_title}' was permanently deleted for {chore_assigned_to}",
                user_name=chore_assigned_to
            )
            message = f"Chore '{chore_title}' has been permanently deleted"

        print(f"[delete_chore] Success: {message}")
        return jsonify({
            'success': True, 
            'message': message,
            'chore_id': chore_id
        })
        
    except Exception as e:
        db.session.rollback()
        error_msg = f"Error deleting chore: {str(e)}"
        print(f"[delete_chore] Exception: {error_msg}")
        log_activity('system_error', error_msg)
        return jsonify({'success': False, 'error': error_msg}), 500

@routes_bp.route('/get_chores', methods=['GET'])
def get_chores():
    chores = Chore.query.filter(Chore.deleted == False).all()
    chore_list = [chore.to_dict() for chore in chores]
    return jsonify({'success': True, 'chores': chore_list})

@routes_bp.route('/delete_reward', methods=['POST'])
def delete_reward():
    """
    Delete a reward permanently from the database.
    """
    try:
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No JSON data provided'}), 400
            
        reward_id = data.get('reward_id')
        
        print(f"[delete_reward] Received data: reward_id={reward_id}")
        
        # Validate reward_id
        if not reward_id:
            return jsonify({'success': False, 'error': 'Reward ID is required'}), 400

        # Find the reward
        reward = Reward.query.get(reward_id)
        if not reward:
            return jsonify({'success': False, 'error': 'Reward not found'}), 404
        
        # Store reward details for logging
        reward_title = reward.title
        reward_assigned_to = reward.assigned_to
        
        print(f"[delete_reward] Processing reward: '{reward_title}' (ID: {reward_id})")
        
        # Delete the reward from database
        db.session.delete(reward)
        db.session.commit()
        
        # Log the activity
        log_activity(
            'reward_deleted',
            f"Reward '{reward_title}' was deleted for {reward_assigned_to}",
            user_name=reward_assigned_to
        )
        
        message = f"Reward '{reward_title}' has been permanently deleted"
        print(f"[delete_reward] Success: {message}")
        
        return jsonify({
            'success': True,
            'message': message,
            'reward_id': reward_id
        })
        
    except Exception as e:
        db.session.rollback()
        error_msg = f"Error deleting reward: {str(e)}"
        print(f"[delete_reward] Exception: {error_msg}")
        log_activity('system_error', error_msg)
        return jsonify({'success': False, 'error': error_msg}), 500

@routes_bp.route('/save_column_color', methods=['POST'])
def save_column_color():
    try:
        data = request.get_json()
        person_id = data.get('person_id')
        color = data.get('color')
        
        person = Person.query.get(person_id)
        if not person:
            return jsonify({
                'success': False,
                'error': 'Person not found'
            }), 404
        
        person.color = color
        db.session.commit()
        
        # Log the activity
        log_activity(
            'color_updated',
            f"Column color was changed to {color} for {person.name}",
            user_name=person.name
        )
        
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        log_activity('system_error', f"Error updating color: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 400

@routes_bp.route('/get_column_color/<int:person_id>', methods=['GET'])
def get_column_color(person_id):
    try:
        person = Person.query.get(person_id)
        if not person:
            return jsonify({
                'success': False,
                'error': 'Person not found'
            }), 404
        
        return jsonify({
            'success': True,
            'color': person.color
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@routes_bp.route('/update_order', methods=['POST'])
def update_order():
    try:
        data = request.get_json()
        person_id = data.get('person_id')
        new_order = int(data.get('order'))
        
        person = Person.query.get(person_id)
        if not person:
            return jsonify({'success': False, 'error': 'Person not found'}), 404
            
        person.order = new_order
        db.session.commit()
        
        # Log the activity
        log_activity(
            'order_updated',
            f"Column order was updated to position {new_order} for {person.name}",
            user_name=person.name
        )
        
        return jsonify({
            'success': True, 
            'message': f"Order updated to {new_order} for {person.name}"
        })
        
    except Exception as e:
        db.session.rollback()
        log_activity('system_error', f"Error updating order: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 400

@routes_bp.route('/update_name', methods=['POST'])
def update_name():
    try:
        data = request.get_json()
        person_id = data.get('person_id')
        new_name = data.get('new_name', '').strip()
        
        if not new_name:
            return jsonify({'success': False, 'error': 'New name cannot be empty'}), 400
        
        person = Person.query.get(person_id)
        if not person:
            return jsonify({'success': False, 'error': 'Person not found'}), 404
        
        old_name = person.name
        person.name = new_name
        db.session.commit()
        
        # Log the activity
        log_activity(
            'name_updated',
            f"Name was changed from '{old_name}' to '{new_name}'",
            user_name=new_name
        )
        
        return jsonify({
            'success': True,
            'message': f'Name updated successfully',
            'new_name': new_name
        })
        
    except Exception as e:
        db.session.rollback()
        log_activity('system_error', f"Error updating name: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 400

@routes_bp.route('/reset_points', methods=['POST'])
def reset_points():
    try:
        data = request.get_json()
        person_id = data.get('person_id')
        new_points = data.get('new_points')
        
        if new_points is None:
            new_points = 0
        
        person = Person.query.get(person_id)
        if not person:
            return jsonify({'success': False, 'error': 'Person not found'}), 404
        
        # Validate the new_points value
        try:
            new_points = int(new_points)
            if new_points < 0:
                return jsonify({'success': False, 'error': 'Points cannot be negative'}), 400
        except (ValueError, TypeError):
            return jsonify({'success': False, 'error': 'Invalid points value. It must be an integer.'}), 400
        
        old_points = person.points
        person.points = new_points
        person.bonus_points = 0
        db.session.commit()
        
        # Log the activity
        log_activity(
            'points_reset',
            f"Points were reset from {old_points} to {new_points} for {person.name} (bonus points also reset)",
            user_name=person.name
        )
        
        return jsonify({
            'success': True,
            'message': f'Points for {person.name} have been set to {person.points} (bonus points reset to 0)',
            'new_points': person.points + person.bonus_points
        })
        
    except Exception as e:
        db.session.rollback()
        log_activity('system_error', f"Error resetting points: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 400
    
@routes_bp.route('/complete_reward', methods=['POST'])
def complete_reward():
    try:
        data = request.get_json()
        reward_id = data.get('reward_id')

        print(f"[complete_reward] Received data: {data}")

        reward = Reward.query.get(reward_id)
        if not reward:
            print(f"[complete_reward] Reward id {reward_id} not found.")
            return jsonify({'success': False, 'error': 'Reward not found'}), 404

        print(f"[complete_reward] Found reward: ID={reward.id}, Title='{reward.title}', assigned_to='{reward.assigned_to}', assigned_to_id={reward.assigned_to_id}")

        # Try multiple approaches to find the person
        person = None

        # Approach 1: Use assigned_to_id from the reward if it exists
        if reward.assigned_to_id:
            person = Person.query.get(reward.assigned_to_id)
            if person:
                print(f"[complete_reward] Found person by assigned_to_id: {person.name}")

        # Approach 2: Use assigned_to name from the reward
        if not person and reward.assigned_to:
            person = Person.query.filter_by(name=reward.assigned_to).first()
            if person:
                print(f"[complete_reward] Found person by name: {person.name}")

        # Approach 3: Use assigned_to_id from the request data
        if not person and data.get('assigned_to_id'):
            person = Person.query.get(data.get('assigned_to_id'))
            if person:
                print(f"[complete_reward] Found person by request assigned_to_id: {person.name}")

        # If still no person found, return an error
        if not person:
            error_msg = f"Person not found for reward '{reward.title}'. assigned_to='{reward.assigned_to}', assigned_to_id={reward.assigned_to_id}"
            print(f"[complete_reward] ERROR: {error_msg}")
            return jsonify({'success': False, 'error': error_msg}), 404

        print(f"[complete_reward] Person {person.name} has {person.points} points, reward requires {reward.points_required} points")

        if person.points < reward.points_required:
            return jsonify({'success': False, 'error': f'Not enough points to complete this reward. {person.name} has {person.points} points but needs {reward.points_required}'}), 400

        # Update the reward and person
        person.points -= reward.points_required
        reward.completed = True
        reward.date_completed = datetime.utcnow()

        db.session.commit()
        
        # Log the activity
        log_activity(
            'reward_redeemed',
            f"Reward '{reward.title}' was redeemed for {reward.points_required} points by {person.name}",
            user_name=person.name
        )

        return jsonify({
            'success': True,
            'message': f'Reward "{reward.title}" has been completed by {person.name}',
            'new_points': person.points
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"[complete_reward] Exception: {e}")
        log_activity('system_error', f"Error completing reward: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 400

@routes_bp.route('/chore_history')
def chore_history():
    # Get all completed chores
    completed_chores = Chore.query.filter(
        Chore.completed == True,
        Chore.deleted == False
    ).order_by(Chore.date_completed.desc()).all()

    # Statistics: Chores completed per person (for pie chart)
    people = Person.query.all()
    chores_by_person = {p.name: 0 for p in people}
    points_by_person = {p.name: 0 for p in people}
    
    for chore in completed_chores:
        person_name = chore.assigned_to
        if person_name in chores_by_person:
            chores_by_person[person_name] += 1
            points_by_person[person_name] += chore.points

    # Statistics: Chores completed per day (last 7 days)
    today = datetime.utcnow().date()
    days = [(today - timedelta(days=i)) for i in range(6, -1, -1)]
    chores_per_day = {d.strftime('%Y-%m-%d'): 0 for d in days}
    
    for chore in completed_chores:
        if chore.date_completed:
            day = chore.date_completed.date().strftime('%Y-%m-%d')
            if day in chores_per_day:
                chores_per_day[day] += 1

    # Format days for display
    formatted_days = [d.strftime('%a %d/%m') for d in days]
    
    # Monthly summary: chores per person for current month
    today_date = date.today()
    first_of_month = today_date.replace(day=1)
    monthly_chores_by_person = defaultdict(int)
    for chore in completed_chores:
        if chore.date_completed and chore.date_completed.date() >= first_of_month:
            if chore.assigned_to:
                monthly_chores_by_person[chore.assigned_to] += 1

    # Top tasks trend: for each person, top 3 tasks and their completion counts over the last 4 weeks
    # Prepare week labels (last 4 weeks)
    trend_weeks = []
    week_starts = []
    for i in range(4, 0, -1):
        week_start = today_date - timedelta(days=today_date.weekday() + 7 * (i - 1))
        week_starts.append(week_start)
        trend_weeks.append(week_start.strftime('%Y-%m-%d'))

    # Gather completions per person per task per week
    person_task_week_counts = defaultdict(lambda: defaultdict(lambda: [0, 0, 0, 0]))
    for chore in completed_chores:
        if chore.assigned_to and chore.date_completed:
            for idx, week_start in enumerate(week_starts):
                week_end = week_start + timedelta(days=6)
                if week_start <= chore.date_completed.date() <= week_end:
                    person_task_week_counts[chore.assigned_to][chore.title][idx] += 1

    # For each person, find their top 3 tasks overall (by total completions in 4 weeks)
    top_tasks_trend = {}
    color_palette = [
        '#FF6384', '#36A2EB', '#FFCE56', '#8BC34A', '#FF9800', '#9C27B0', '#607D8B', '#795548'
    ]
    for person, task_counts in person_task_week_counts.items():
        # Sum total completions for each task
        task_totals = {task: sum(counts) for task, counts in task_counts.items()}
        top_tasks = sorted(task_totals.items(), key=lambda x: x[1], reverse=True)[:3]
        trend_list = []
        for idx, (task, _) in enumerate(top_tasks):
            color = color_palette[idx % len(color_palette)]
            trend_list.append({
                'title': task,
                'counts': task_counts[task],
                'color': color
            })
        top_tasks_trend[person] = trend_list
    
    return render_template(
        'chore_history.html',
        completed_chores=completed_chores,
        chores_by_person=chores_by_person,
        points_by_person=points_by_person,
        chores_per_day=chores_per_day,
        days=formatted_days,
        day_keys=[d.strftime('%Y-%m-%d') for d in days],
        monthly_chores_by_person=monthly_chores_by_person,
        top_tasks_trend=top_tasks_trend,
        trend_weeks=trend_weeks
    )
