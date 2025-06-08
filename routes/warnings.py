import sqlite3
from flask import Blueprint, request, jsonify, session, current_app, render_template
from db import get_db
from decorators import role_required
import datetime
from datetime import timezone # Importiere timezone

print("warnings.py wird geladen...")

warnings_bp = Blueprint('warnings', __name__)

# WICHTIG: Die Route muss '/' sein, da der Blueprint bereits den Präfix '/warnings' hat.
@warnings_bp.route('/', methods=['GET', 'POST'])
@role_required(['Administrator', 'Verwarner'])
def warnings_page():
    """Rendert die Verwarnungsübersicht und verarbeitet neue Verwarnungen."""
    print("warnings_page Funktion wird aufgerufen!")
    if request.method == 'GET':
        dark_mode_enabled = session.get('dark_mode_enabled', False)
        # Stell sicher, dass warnings.html im 'templates'-Ordner liegt!
        return render_template('warnings.html', dark_mode_enabled=dark_mode_enabled)
    
    if request.method == 'POST':
        db = get_db()
        cursor = db.cursor()
        data = request.get_json() 
        stand_id = data.get('stand_id')
        comment = data.get('comment', '').strip()
        user_id = session['user_id']

        if not stand_id or not comment:
            message = "Bitte wählen Sie einen Stand aus und geben Sie einen Kommentar ein."
            return jsonify(success=False, message=message), 400
        else:
            try:
                cursor.execute("INSERT INTO warnings (stand_id, user_id, comment) VALUES (?, ?, ?)",
                               (stand_id, user_id, comment))
                db.commit()
                message = "Verwarnung erfolgreich eingegeben!"
                return jsonify(success=True, message=message)
            except sqlite3.Error as e:
                message = f"Fehler beim Eingeben der Verwarnung: {e}"
                db.rollback()
                return jsonify(success=False, message=message), 500

@warnings_bp.route('/api/warnings_data', methods=['GET'])
@role_required(['Administrator', 'Verwarner'])
def api_warnings_data():
    """Gibt alle Verwarnungsdaten als JSON zurück."""
    print("api_warnings_data Funktion wird aufgerufen!")
    db = get_db()
    cursor = db.cursor()

    try:
        stands_with_warnings = cursor.execute('''
            SELECT DISTINCT s.id, s.name
            FROM stands s
            JOIN warnings w ON s.id = w.stand_id
            ORDER BY s.name
        ''').fetchall()

        grouped_warnings = {}
        for stand in stands_with_warnings:
            grouped_warnings[stand['id']] = {
                'stand_id': stand['id'],
                'stand_name': stand['name'],
                'total_warnings': 0, 
                'warnings': []
            }
        
        all_warnings = cursor.execute('''
            SELECT
                w.id,
                w.stand_id,
                s.name AS stand_name,
                u.display_name AS warner_name,
                w.comment,
                w.timestamp,
                w.is_invalidated,
                iu.display_name AS invalidated_by_user_name,
                w.invalidation_comment,
                w.invalidation_timestamp
            FROM warnings w
            JOIN stands s ON w.stand_id = s.id
            JOIN users u ON w.user_id = u.id
            LEFT JOIN users iu ON w.invalidated_by_user_id = iu.id
            ORDER BY s.name, w.timestamp DESC
        ''').fetchall()

        for warning in all_warnings:
            stand_id = warning['stand_id']
            if stand_id in grouped_warnings: 
                warning_dict = dict(warning) # Convert row to dict for modification
                
                # Convert timestamps to timezone-aware ISO 8601 strings
                if warning_dict['timestamp']:
                    dt_object = datetime.datetime.fromisoformat(warning_dict['timestamp'])
                    if dt_object.tzinfo is None:
                        dt_object = dt_object.replace(tzinfo=timezone.utc)
                    warning_dict['timestamp'] = dt_object.isoformat()
                
                if warning_dict['invalidation_timestamp']:
                    dt_object_inval = datetime.datetime.fromisoformat(warning_dict['invalidation_timestamp'])
                    if dt_object_inval.tzinfo is None:
                        dt_object_inval = dt_object_inval.replace(tzinfo=timezone.utc)
                    warning_dict['invalidation_timestamp'] = dt_object_inval.isoformat()

                grouped_warnings[stand_id]['warnings'].append(warning_dict)
                if not warning_dict['is_invalidated']: # Use modified dict for status check
                    grouped_warnings[stand_id]['total_warnings'] += 1
        
        grouped_warnings_list = list(grouped_warnings.values())

        grouped_warnings_list.sort(key=lambda x: x['stand_name'])

        all_stands_for_dropdown = cursor.execute("SELECT id, name FROM stands ORDER BY name").fetchall()

        return jsonify({
            'success': True,
            'stands_for_dropdown': [dict(s) for s in all_stands_for_dropdown],
            'grouped_warnings': grouped_warnings_list
        })
    except sqlite3.Error as e:
        # Im Fehlerfall immer JSON zurückgeben
        return jsonify(success=False, message=f"Datenbankfehler beim Abrufen der Verwarnungsdaten: {e}"), 500
    except Exception as e:
        # Allgemeine Fehler abfangen und als JSON zurückgeben
        return jsonify(success=False, message=f"Ein unerwarteter Serverfehler ist aufgetreten: {e}"), 500

@warnings_bp.route('/invalidate_warning/<int:warning_id>', methods=['POST'])
@role_required(['Administrator', 'Verwarner'])
def invalidate_warning(warning_id):
    """Invalidiert eine bestimmte Verwarnung."""
    print(f"invalidate_warning Funktion für ID {warning_id} wird aufgerufen!")
    db = get_db()
    cursor = db.cursor()
    
    data = request.get_json()
    invalidation_comment = data.get('invalidation_comment', '').strip()
    user_id = session['user_id']

    try:
        # Use timezone-aware datetime for CURRENT_TIMESTAMP equivalent
        current_time_utc = datetime.datetime.now(timezone.utc).isoformat()
        cursor.execute("UPDATE warnings SET is_invalidated = 1, invalidated_by_user_id = ?, invalidation_comment = ?, invalidation_timestamp = ? WHERE id = ?",
                       (user_id, invalidation_comment, current_time_utc, warning_id))
        db.commit()
        return jsonify(success=True, message="Verwarnung erfolgreich als ungültig markiert.")
    except sqlite3.Error as e:
        db.rollback()
        return jsonify(success=False, message=f"Fehler beim Ungültigmachen der Verwarnung: {e}"), 500

@warnings_bp.route('/make_warning_valid/<int:warning_id>', methods=['POST'])
@role_required(['Administrator', 'Verwarner'])
def make_warning_valid(warning_id):
    """Macht eine bestimmte Verwarnung wieder gültig."""
    print(f"make_warning_valid Funktion für ID {warning_id} wird aufgerufen!")
    db = get_db()
    cursor = db.cursor()
    
    try:
        cursor.execute("UPDATE warnings SET is_invalidated = 0, invalidated_by_user_id = NULL, invalidation_comment = NULL, invalidation_timestamp = NULL WHERE id = ?",
                       (warning_id,))
        db.commit()
        return jsonify(success=True, message="Verwarnung erfolgreich als gültig markiert.")
    except sqlite3.Error as e:
        db.rollback()
        return jsonify(success=False, message=f"Fehler beim Gültigmachen der Verwarnung: {e}"), 500

@warnings_bp.route('/get_warning_count/<int:stand_id>')
@role_required(['Administrator', 'Bewerter', 'Betrachter', 'Inspektor', 'Verwarner'])
def get_warning_count(stand_id):
    """Gibt die Anzahl der GÜLTIGEN Verwarnungen für einen Stand zurück."""
    print(f"get_warning_count Funktion für Stand ID {stand_id} wird aufgerufen!")
    db = get_db()
    cursor = db.cursor()
    count_row = cursor.execute("SELECT COUNT(*) FROM warnings WHERE stand_id = ? AND is_invalidated = 0", (stand_id,)).fetchone()
    count = count_row[0] if count_row else 0
    return jsonify(count=count)
