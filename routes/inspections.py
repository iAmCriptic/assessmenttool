import sqlite3
from flask import Blueprint, request, jsonify, session, current_app, render_template
from db import get_db
from decorators import role_required
import datetime
from datetime import timezone # Importiere timezone

inspections_bp = Blueprint('inspections', __name__)

# Die Route für die HTML-Seite der Rauminspektionen
# Der Name dieser Funktion ('manage_room_inspections_page') wird in url_for verwendet.
@inspections_bp.route('/room_inspections', methods=['GET'])
@role_required(['Administrator', 'Inspektor'])
def manage_room_inspections_page():
    """Rendert die Rauminspektionsseite."""
    print("DEBUG: manage_room_inspections_page wurde aufgerufen!") # <<< WICHTIG: Diese Debug-Ausgabe sollte im Terminal erscheinen
    dark_mode_enabled = session.get('dark_mode_enabled', False) # Dark Mode Status aus der Session holen
    # Stell sicher, dass 'room_inspections.html' im 'static'-Ordner liegt!
    return render_template('room_inspections.html', dark_mode_enabled=dark_mode_enabled)

# Die API-Route für die Daten der Rauminspektionen
@inspections_bp.route('/api/room_inspections', methods=['GET', 'POST'])
@role_required(['Administrator', 'Inspektor'])
def api_room_inspections():
    db = get_db()
    cursor = db.cursor()

    if request.method == 'GET':
        rooms_raw_data = cursor.execute('''
            SELECT
                r.id AS room_id,
                r.name AS room_name,
                ri.is_clean,
                ri.inspection_timestamp,
                u.display_name AS inspector_display_name,
                ri.comment
            FROM rooms r
            LEFT JOIN room_inspections ri ON r.id = ri.room_id
            LEFT JOIN users u ON ri.inspector_user_id = u.id
            ORDER BY r.name
        ''').fetchall()

        rooms_data = []
        for room_row in rooms_raw_data:
            room_dict = dict(room_row)
            
            # Konvertiere den Zeitstempel in ISO 8601 UTC
            if room_dict['inspection_timestamp']:
                dt_object = datetime.datetime.fromisoformat(room_dict['inspection_timestamp'])
                if dt_object.tzinfo is None:
                    dt_object = dt_object.replace(tzinfo=timezone.utc)
                room_dict['inspection_timestamp'] = dt_object.isoformat()
            
            stands_for_room = cursor.execute("SELECT id, name FROM stands WHERE room_id = ?", (room_dict['room_id'],)).fetchall()
            room_dict['stands'] = [dict(s) for s in stands_for_room]
            rooms_data.append(room_dict)
        return jsonify({'success': True, 'room_inspections': rooms_data})

    elif request.method == 'POST': # Inspektion aktualisieren oder einfügen
        data = request.get_json()
        room_id = data.get('room_id')
        is_clean = data.get('is_clean')
        comment = data.get('comment')
        inspector_user_id = session['user_id']
        
        # Erzeuge den Zeitstempel als UTC und konvertiere ihn in einen ISO-String
        # CURRENT_TIMESTAMP in SQLite speichert in UTC, also ist fromisoformat() und replace(tzinfo=timezone.utc) hier korrekt.
        inspection_timestamp = datetime.datetime.now(timezone.utc).isoformat()

        if room_id is None or is_clean is None:
            return jsonify({'success': False, 'message': "Raum-ID und Sauberkeitsstatus sind erforderlich."}), 400
        
        try:
            cursor.execute("SELECT room_id FROM room_inspections WHERE room_id = ? LIMIT 1", (room_id,))
            existing_inspection = cursor.fetchone()

            if existing_inspection:
                cursor.execute("""
                    UPDATE room_inspections
                    SET inspector_user_id = ?, inspection_timestamp = ?, is_clean = ?, comment = ?
                    WHERE room_id = ?
                """, (inspector_user_id, inspection_timestamp, is_clean, comment, room_id))
                message = "Rauminspektion erfolgreich aktualisiert!"
            else:
                cursor.execute("""
                    INSERT INTO room_inspections (room_id, inspector_user_id, inspection_timestamp, is_clean, comment)
                    VALUES (?, ?, ?, ?, ?)
                """, (room_id, inspector_user_id, inspection_timestamp, is_clean, comment))
                message = "Rauminspektion erfolgreich gespeichert!"
            
            db.commit()
            return jsonify({'success': True, 'message': message})
        except sqlite3.Error as e:
            db.rollback()
            return jsonify({'success': False, 'message': f"Fehler beim Speichern der Rauminspektion: {e}"}), 500
