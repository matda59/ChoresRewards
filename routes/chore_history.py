from flask import Blueprint, render_template
from datetime import datetime, timedelta
from models import Chore, Person

chore_history_bp = Blueprint('chore_history', __name__)

@chore_history_bp.route('/chore_history')
def chore_history():
    # Get all completed chores
    completed_chores = Chore.query.filter(
        Chore.completed == True,
        Chore.deleted == False
    ).order_by(Chore.date_completed.desc()).all()

    # Statistics: Chores completed per person
    people = Person.query.all()
    chores_by_person = {p.name: 0 for p in people}
    for chore in completed_chores:
        if chore.assigned_to:
            chores_by_person[chore.assigned_to] = chores_by_person.get(chore.assigned_to, 0) + 1

    # Statistics: Chores completed per day (last 7 days)
    today = datetime.utcnow().date()
    days = [(today - timedelta(days=i)) for i in range(6, -1, -1)]
    chores_per_day = {d.strftime('%Y-%m-%d'): 0 for d in days}
    for chore in completed_chores:
        if chore.date_completed:
            day = chore.date_completed.date().strftime('%Y-%m-%d')
            if day in chores_per_day:
                chores_per_day[day] += 1

    return render_template(
        'chore_history.html',
        completed_chores=completed_chores,
        chores_by_person=chores_by_person,
        chores_per_day=chores_per_day
    )