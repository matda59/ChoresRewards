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
from routes import routes_bp

# Register the Blueprint
app.register_blueprint(routes_bp)

# Create database tables
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000)
