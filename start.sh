#!/bin/bash

echo "Ensuring database tables are created..."

# Execute db.create_all() within the Flask application context.
# Use triple quotes for the Python command to handle the 'with' statement correctly.
python -c """
from app import app, db
with app.app_context():
    db.create_all()
"""

echo "Database setup complete."

echo "Starting Gunicorn..."
exec gunicorn -w 4 -b 0.0.0.0:3000 app:app