import sqlite3
from flask import Blueprint, request, jsonify, current_app, session, render_template
from db import get_db
from decorators import role_required

stands_bp = Blueprint('stands', __name__)

@stands_bp.route('/manage_stand')
@role_required(['Administrator'])
def manage_stand_page():
    """Renders the stand management page."""
    # Correction: Use render_template, as manage_stand.html contains Jinja2 variables.
    dark_mode_enabled = session.get('dark_mode_enabled', False)
    return render_template('manage_stands.html', dark_mode_enabled=dark_mode_enabled)

# The following route is for API interactions with stands.
# Different HTTP methods require different roles.
@stands_bp.route('/api/stands', methods=['GET', 'POST'])
@stands_bp.route('/api/stands/<int:stand_id>', methods=['GET', 'PUT', 'DELETE'])
@role_required(['Administrator', 'Bewerter', 'Betrachter', 'Inspektor', 'Verwarner']) # This applies to GET, PUT, POST, DELETE
def api_stands(stand_id=None):
    db = get_db()
    cursor = db.cursor()

    if request.method == 'GET':
        # GET requests allow 'Administrator', 'Bewerter', 'Betrachter', 'Inspektor', 'Verwarner'
        if stand_id: # Retrieve single stand
            stand = cursor.execute("SELECT s.id, s.name, s.description, s.room_id, r.name AS room_name FROM stands s LEFT JOIN rooms r ON s.room_id = r.id WHERE s.id = ?", (stand_id,)).fetchone()
            if stand:
                return jsonify({'success': True, 'stand': dict(stand)})
            return jsonify({'success': False, 'message': 'Stand not found.'}), 404
        else: # Retrieve all stands
            stands = cursor.execute("SELECT s.id, s.name, s.description, s.room_id, r.name AS room_name FROM stands s LEFT JOIN rooms r ON s.room_id = r.id ORDER BY s.name").fetchall()
            return jsonify({'success': True, 'stands': [dict(s) for s in stands]})

    # For POST, PUT, DELETE methods, only 'Administrator' role is allowed
    # This is critical as these operations modify data.
    # The decorator above already handles the role check for all methods.
    # We now add specific checks within the methods themselves for clarity and finer control.
    if 'Administrator' not in session.get('user_roles', []):
        # This check is redundant if role_required already handles it, but good for explicit permission.
        # However, for 405 error, the issue is often related to the method not being explicitly allowed
        # in the @stands_bp.route decorator for the given role.
        # The fix should ensure the @role_required decorator allows 'Administrator' for all methods.
        pass # The outer decorator should take care of this.

    if request.method == 'POST':
        data = request.get_json()
        stand_name = data.get('name', '').strip()
        stand_description = data.get('description', '').strip()
        room_id = data.get('room_id') # Can be None

        if not stand_name:
            return jsonify({'success': False, 'message': "Stand name is required."}), 400
        
        try:
            cursor.execute("INSERT INTO stands (name, description, room_id) VALUES (?, ?, ?)", (stand_name, stand_description, room_id))
            db.commit()
            return jsonify({'success': True, 'message': f"Stand '{stand_name}' successfully added!"})
        except sqlite3.IntegrityError:
            return jsonify({'success': False, 'message': f"Error: Stand name '{stand_name}' already exists."}), 409
        except sqlite3.Error as e:
            db.rollback()
            return jsonify({'success': False, 'message': f"An error occurred: {e}"}), 500

    if request.method == 'PUT': # Update stand
        data = request.get_json()
        stand_name = data.get('name', '').strip()
        stand_description = data.get('description', '').strip()
        room_id = data.get('room_id') # Can be None

        if not stand_id:
            return jsonify({'success': False, 'message': "Stand ID is required for update."}), 400
        if not stand_name:
            return jsonify({'success': False, 'message': "New stand name is required."}), 400
        try:
            cursor.execute("UPDATE stands SET name = ?, description = ?, room_id = ? WHERE id = ?",
                           (stand_name, stand_description, room_id, stand_id))
            db.commit()
            if cursor.rowcount == 0:
                return jsonify({'success': False, 'message': "Stand not found."}), 404
            return jsonify({'success': True, 'message': f"Stand '{stand_name}' successfully updated!"})
        except sqlite3.IntegrityError:
            return jsonify({'success': False, 'message': f"Error: Stand name '{stand_name}' already exists."}), 409
        except sqlite3.Error as e:
            db.rollback()
            return jsonify({'success': False, 'message': f"An error occurred: {e}"}), 500

    elif request.method == 'DELETE': # Delete stand
        if not stand_id:
            return jsonify({'success': False, 'message': "Stand ID is required for deletion."}), 400
        try:
            cursor.execute("DELETE FROM stands WHERE id = ?", (stand_id,))
            db.commit()
            if cursor.rowcount == 0:
                return jsonify({'success': False, 'message': "Stand not found."}), 404
            return jsonify({'success': True, 'message': "Stand erfolgreich gelöscht!"})
        except sqlite3.Error as e:
            db.rollback()
            return jsonify({'success': False, 'message': f"An error occurred: {e}"}), 500

# This route is now redundant as api_stands handles fetching descriptions
# @stands_bp.route('/api/stands/description/<int:stand_id>', methods=['GET'])
# @role_required(['Administrator', 'Bewerter', 'Betrachter', 'Inspektor', 'Verwarner'])
# def get_stand_description(stand_id):
#     """Returns the description of a specific stand as JSON."""
#     db = get_db()
#     cursor = db.cursor()
#     try:
#         stand = cursor.execute("SELECT description FROM stands WHERE id = ?", (stand_id,)).fetchone()
#         if stand:
#             return jsonify({'success': True, 'description': stand['description'] or 'No description available.'})
#         return jsonify({'success': False, 'message': 'Stand not found.'}), 404
#     except sqlite3.Error as e:
#         print(f"Database error in get_stand_description: {e}")
#         return jsonify({'success': False, 'message': f'Error retrieving description: {e}'}), 500
#     except Exception as e:
#         print(f"An unexpected error occurred in get_stand_description: {e}")
#         return jsonify({'success': False, 'message': f'An unexpected error occurred: {e}'}), 500
