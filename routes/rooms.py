import sqlite3
from flask import Blueprint, request, jsonify, current_app, session, render_template # session und render_template hinzugefügt
from db import get_db
from decorators import role_required

rooms_bp = Blueprint('rooms', __name__)

@rooms_bp.route('/manage_rooms')
@role_required(['Administrator'])
def manage_rooms_page():
    """Rendert die Raumverwaltungsseite."""
    # Korrektur: Verwende render_template, da manage_rooms.html Jinja2-Variablen enthält.
    # Übergebe dark_mode_enabled, falls die Vorlage es benötigt.
    dark_mode_enabled = session.get('dark_mode_enabled', False)
    return render_template('manage_rooms.html', dark_mode_enabled=dark_mode_enabled)

@rooms_bp.route('/api/rooms', methods=['GET', 'POST'])
@rooms_bp.route('/api/rooms/<int:room_id>', methods=['GET', 'PUT', 'DELETE'])
@role_required(['Administrator'])
def api_rooms(room_id=None):
    db = get_db()
    cursor = db.cursor()

    if request.method == 'GET':
        if room_id: # Einzelnen Raum abrufen
            room = cursor.execute("SELECT id, name FROM rooms WHERE id = ?", (room_id,)).fetchone()
            if room:
                return jsonify({'success': True, 'room': dict(room)})
            return jsonify({'success': False, 'message': 'Raum nicht gefunden.'}), 404
        else: # Alle Räume abrufen
            rooms = cursor.execute("SELECT id, name FROM rooms ORDER BY name").fetchall()
            return jsonify({'success': True, 'rooms': [dict(r) for r in rooms]})

    data = {}
    if request.method in ['POST', 'PUT']:
        if not request.is_json:
            return jsonify({'success': False, 'message': 'Anfrage muss JSON sein.'}), 400
        data = request.get_json()
    
    if request.method == 'POST': # Neuen Raum hinzufügen
        room_name = data.get('name', '').strip()
        if not room_name:
            return jsonify({'success': False, 'message': "Raumname ist erforderlich."}), 400
        try:
            cursor.execute("INSERT INTO rooms (name) VALUES (?)", (room_name,))
            db.commit()
            return jsonify({'success': True, 'message': f"Raum '{room_name}' erfolgreich hinzugefügt!", 'room_id': cursor.lastrowid}), 201
        except sqlite3.IntegrityError:
            return jsonify({'success': False, 'message': f"Fehler: Raum '{room_name}' existiert bereits."}), 409
        except sqlite3.Error as e:
            db.rollback()
            return jsonify({'success': False, 'message': f"Ein Fehler ist aufgetreten: {e}"}), 500

    elif request.method == 'PUT': # Raum aktualisieren
        if not room_id:
            return jsonify({'success': False, 'message': "Raum-ID ist für die Aktualisierung erforderlich."}), 400
        new_room_name = data.get('name', '').strip()
        if not new_room_name:
            return jsonify({'success': False, 'message': "Neuer Raumname ist erforderlich."}), 400
        try:
            cursor.execute("UPDATE rooms SET name = ? WHERE id = ?", (new_room_name, room_id))
            db.commit()
            if cursor.rowcount == 0:
                return jsonify({'success': False, 'message': "Raum nicht gefunden."}), 404
            return jsonify({'success': True, 'message': f"Raum aktualisiert zu '{new_room_name}'."})
        except sqlite3.IntegrityError:
            return jsonify({'success': False, 'message': f"Fehler: Raum '{new_room_name}' existiert bereits."}), 409
        except sqlite3.Error as e:
            db.rollback()
            return jsonify({'success': False, 'message': f"Ein Fehler ist aufgetreten: {e}"}), 500

    elif request.method == 'DELETE': # Raum löschen
        if not room_id:
            return jsonify({'success': False, 'message': "Raum-ID ist für die Löschung erforderlich."}), 400
        try:
            cursor.execute("DELETE FROM rooms WHERE id = ?", (room_id,))
            db.commit()
            if cursor.rowcount == 0:
                return jsonify({'success': False, 'message': "Raum nicht gefunden."}), 404
            return jsonify({'success': True, 'message': "Raum erfolgreich gelöscht! Zugeordnete Stände haben jetzt keinen Raum."})
        except sqlite3.Error as e:
            db.rollback()
            return jsonify({'success': False, 'message': f"Ein Fehler ist aufgetreten: {e}"}), 500
