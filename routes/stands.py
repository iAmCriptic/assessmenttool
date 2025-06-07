import sqlite3
from flask import Blueprint, request, jsonify, current_app, session, render_template # render_template wurde hinzugefügt
from db import get_db
from decorators import role_required

stands_bp = Blueprint('stands', __name__)

@stands_bp.route('/manage_stand')
@role_required(['Administrator'])
def manage_stand_page():
    """Rendert die Standverwaltungsseite."""
    # Korrektur: Verwende render_template, da manage_stand.html Jinja2-Variablen enthält.
    dark_mode_enabled = session.get('dark_mode_enabled', False)
    return render_template('manage_stands.html', dark_mode_enabled=dark_mode_enabled)

@stands_bp.route('/api/stands', methods=['GET', 'POST'])
@stands_bp.route('/api/stands/<int:stand_id>', methods=['GET', 'PUT', 'DELETE'])
# Angepasste Rollen für GET-Anfragen, um Bewertern und Betrachtern das Abrufen von Standdetails zu ermöglichen
@role_required(['Administrator', 'Bewerter', 'Betrachter']) # Hier angepasst
def api_stands(stand_id=None):
    db = get_db()
    cursor = db.cursor()

    if request.method == 'GET':
        if stand_id: # Einzelnen Stand abrufen
            stand = cursor.execute("SELECT s.id, s.name, s.description, s.room_id, r.name AS room_name FROM stands s LEFT JOIN rooms r ON s.room_id = r.id WHERE s.id = ?", (stand_id,)).fetchone()
            if stand:
                return jsonify({'success': True, 'stand': dict(stand)})
            return jsonify({'success': False, 'message': 'Stand nicht gefunden.'}), 404
        else: # Alle Stände abrufen
            stands = cursor.execute("SELECT s.id, s.name, s.description, s.room_id, r.name AS room_name FROM stands s LEFT JOIN rooms r ON s.room_id = r.id ORDER BY s.name").fetchall()
            return jsonify({'success': True, 'stands': [dict(s) for s in stands]})

    # Für POST, PUT, DELETE Methoden bleiben die Rollen Administrator
    # Dies ist wichtig, da diese Operationen Änderungen an den Daten vornehmen.
    if request.method == 'POST':
        # Sicherstellen, dass nur Administratoren POST-Anfragen stellen können
        if 'Administrator' not in session.get('user_roles', []):
            return jsonify({'success': False, 'message': 'Zugriff verweigert: Nur Administratoren können Stände hinzufügen.'}), 403

        data = request.get_json()
        stand_name = data.get('name', '').strip()
        stand_description = data.get('description', '').strip()
        room_id = data.get('room_id') # Kann None sein

        if not stand_name:
            return jsonify({'success': False, 'message': "Standname ist erforderlich."}), 400
        
        try:
            cursor.execute("INSERT INTO stands (name, description, room_id) VALUES (?, ?, ?)", (stand_name, stand_description, room_id))
            db.commit()
            return jsonify({'success': True, 'message': f"Stand '{stand_name}' erfolgreich hinzugefügt!"})
        except sqlite3.IntegrityError:
            return jsonify({'success': False, 'message': f"Fehler: Standname '{stand_name}' existiert bereits."}), 409
        except sqlite3.Error as e:
            db.rollback()
            return jsonify({'success': False, 'message': f"Ein Fehler ist aufgetreten: {e}"}), 500

    data = request.get_json()
    stand_name = data.get('name', '').strip()
    stand_description = data.get('description', '').strip()
    room_id = data.get('room_id') # Kann None sein

    if request.method == 'PUT': # Stand aktualisieren
        # Sicherstellen, dass nur Administratoren PUT-Anfragen stellen können
        if 'Administrator' not in session.get('user_roles', []):
            return jsonify({'success': False, 'message': 'Zugriff verweigert: Nur Administratoren können Stände aktualisieren.'}), 403

        if not stand_id:
            return jsonify({'success': False, 'message': "Stand-ID ist für die Aktualisierung erforderlich."}), 400
        if not stand_name:
            return jsonify({'success': False, 'message': "Neuer Standname ist erforderlich."}), 400
        try:
            cursor.execute("UPDATE stands SET name = ?, description = ?, room_id = ? WHERE id = ?",
                           (stand_name, stand_description, room_id, stand_id))
            db.commit()
            if cursor.rowcount == 0:
                return jsonify({'success': False, 'message': "Stand nicht gefunden."}), 404
            return jsonify({'success': True, 'message': f"Stand '{stand_name}' erfolgreich aktualisiert!"})
        except sqlite3.IntegrityError:
            return jsonify({'success': False, 'message': f"Fehler: Standname '{stand_name}' existiert bereits."}), 409
        except sqlite3.Error as e:
            db.rollback()
            return jsonify({'success': False, 'message': f"Ein Fehler ist aufgetreten: {e}"}), 500

    elif request.method == 'DELETE': # Stand löschen
        # Sicherstellen, dass nur Administratoren DELETE-Anfragen stellen können
        if 'Administrator' not in session.get('user_roles', []):
            return jsonify({'success': False, 'message': 'Zugriff verweigert: Nur Administratoren können Stände löschen.'}), 403

        if not stand_id:
            return jsonify({'success': False, 'message': "Stand-ID ist für die Löschung erforderlich."}), 400
        try:
            cursor.execute("DELETE FROM stands WHERE id = ?", (stand_id,))
            db.commit()
            if cursor.rowcount == 0:
                return jsonify({'success': False, 'message': "Stand nicht gefunden."}), 404
            return jsonify({'success': True, 'message': "Stand erfolgreich gelöscht!"})
        except sqlite3.Error as e:
            db.rollback()
            return jsonify({'success': False, 'message': f"Ein Fehler ist aufgetreten: {e}"}), 500

# This route is now redundant as api_stands handles fetching descriptions
# @stands_bp.route('/api/stands/description/<int:stand_id>', methods=['GET'])
# @role_required(['Administrator', 'Bewerter', 'Betrachter', 'Inspektor', 'Verwarner'])
# def get_stand_description(stand_id):
#     """Gibt die Beschreibung eines bestimmten Stands als JSON zurück."""
#     db = get_db()
#     cursor = db.cursor()
#     try:
#         stand = cursor.execute("SELECT description FROM stands WHERE id = ?", (stand_id,)).fetchone()
#         if stand:
#             return jsonify({'success': True, 'description': stand['description'] or 'No description available.'})
#         return jsonify({'success': False, 'message': 'Stand nicht gefunden.'}), 404
#     except sqlite3.Error as e:
#         print(f"Database error in get_stand_description: {e}")
#         return jsonify({'success': False, 'message': f'Fehler beim Abrufen der Beschreibung: {e}'}), 500
#     except Exception as e:
#         print(f"An unexpected error occurred in get_stand_description: {e}")
#         return jsonify({'success': False, 'message': f'Ein unerwarteter Fehler ist aufgetreten: {e}'}), 500
