from flask import Blueprint, request, jsonify
from models import db, Chore  # assuming Chore is your SQLAlchemy model

chore_bp = Blueprint('chore_routes', __name__)

# Example: Adding a 'deleted' column to your Chore model is assumed:
# class Chore(db.Model):
#     id = db.Column(db.Integer, primary_key=True)
#     title = db.Column(db.String(100))
#     points = db.Column(db.Integer)
#     is_daily = db.Column(db.Boolean, default=False)
#     deleted = db.Column(db.Boolean, default=False)  # New field for permanent deletion
#     date_completed = db.Column(db.DateTime)
#     assigned_to = db.Column(db.String(50))
#     ... other fields ...

@chore_bp.route('/delete_chore', methods=['POST'])
def delete_chore():
    data = request.get_json()
    chore_id = data.get('chore_id')
    if not chore_id:
        return jsonify({'success': False, 'message': 'Chore ID required'}), 400
    chore = Chore.query.get(chore_id)
    if not chore:
        return jsonify({'success': False, 'message': 'Chore not found'}), 404
    
    # If it is a daily chore then mark it as deleted so it does not reappear
    if chore.is_daily:
        chore.deleted = True
    else:
        # Otherwise, simply remove it from the database
        db.session.delete(chore)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Chore deleted successfully'})

@chore_bp.route('/get_chores', methods=['GET'])
def get_chores():
    # Ensure that the chores returned do not include daily chores that have been deleted.
    # Modify the query to check that deleted flag is False.
    chores = Chore.query.filter(Chore.deleted == False).all()
    # Convert chores to dictionary for JSON response (implementation may vary)
    chore_list = [chore.to_dict() for chore in chores]
    return jsonify({'success': True, 'chores': chore_list})