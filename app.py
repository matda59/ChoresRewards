from flask import Flask
from extensions import db

# Initialize Flask app
app = Flask(__name__)
app.secret_key = '22342342356655676787899787654323456789876543212345678901234567890'  # Set a secret key for session management
# Configure SQLite database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'  # Add this line

db.init_app(app)  # Initialize db with the app

# Import routes after app is created (to avoid circular imports)

# Import quiz questions
import sys
import os
quiz_path = os.path.join(os.path.dirname(__file__), 'quiz_questions.py')
if quiz_path not in sys.path:
    sys.path.append(os.path.dirname(__file__))
from quiz_questions import quiz_questions

from routes import routes_bp


# Register the Blueprint

# Main route: pass quiz_questions to template

app.register_blueprint(routes_bp)

# TEMPORARY DEBUG ROUTE: View chores with 'sat' in the title and their days_of_week
@app.route('/debug/satchores')
def debug_satchores():
    from flask import Markup
    from models import Chore
    from extensions import db
    chores = Chore.query.filter(Chore.title.ilike('%sat%')).all()
    rows = []
    for c in chores:
        rows.append(f"<tr><td>{c.id}</td><td>{c.title}</td><td>{c.days_of_week}</td><td>{c.is_daily}</td><td>{c.due_date}</td><td>{c.assigned_to}</td><td>{c.completed}</td></tr>")
    table = """
    <table border='1' style='border-collapse:collapse;'>
        <tr><th>ID</th><th>Title</th><th>days_of_week</th><th>is_daily</th><th>due_date</th><th>assigned_to</th><th>completed</th></tr>
        {} 
    </table>
    <p>Remove this route after debugging!</p>
    """.format('\n'.join(rows))
    return Markup(table)

# Create database tables
with app.app_context():
    db.create_all()
    # Safe migration: add age column to person table if it doesn't exist
    from sqlalchemy import inspect, text
    inspector = inspect(db.engine)
    existing_columns = [col['name'] for col in inspector.get_columns('person')]
    if 'age' not in existing_columns:
        db.session.execute(text('ALTER TABLE person ADD COLUMN age INTEGER'))
        db.session.commit()
        # One-time data migration from person_ages.json
        import json as _json, os as _os
        age_file = _os.path.join(_os.path.dirname(__file__), 'person_ages.json')
        if _os.path.exists(age_file):
            from models import Person
            with open(age_file) as f:
                ages = _json.load(f)
            for person in Person.query.all():
                age_val = ages.get(str(person.id))
                if age_val is not None:
                    person.age = int(age_val)
            db.session.commit()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000)
