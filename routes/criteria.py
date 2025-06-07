import sqlite3
from flask import Blueprint, request, jsonify, current_app, session, render_template # session und render_template sind hier wichtig
from db import get_db
from decorators import role_required

criteria_bp = Blueprint('criteria', __name__)

@criteria_bp.route('/manage_criteria')
@role_required(['Administrator'])
def manage_criteria_page():
    """Rendert die Kriterienverwaltungsseite."""
    # Debug-Ausgabe: Überprüfen, ob diese Funktion überhaupt erreicht wird.
    print("DEBUG: manage_criteria_page Funktion wurde aufgerufen.")
    try:
        dark_mode_enabled = session.get('dark_mode_enabled', False)
        return render_template('manage_criteria.html', dark_mode_enabled=dark_mode_enabled)
    except Exception as e:
        # Fängt jede Ausnahme während des Renderns ab und gibt sie aus
        print(f"ERROR: Ausnahme beim Rendern von manage_criteria.html: {e}")
        # Anstatt 404, geben wir hier einen 500 Internal Server Error zurück,
        # da die Route gefunden wurde, aber beim Rendern ein Problem auftrat.
        return "Internal Server Error beim Laden der Kriterienseite.", 500

@criteria_bp.route('/api/criteria', methods=['GET', 'POST'])
@criteria_bp.route('/api/criteria/<int:criterion_id>', methods=['GET', 'PUT', 'DELETE'])
@role_required(['Administrator'])
def api_criteria(criterion_id=None):
    db = get_db()
    cursor = db.cursor()

    if request.method == 'GET':
        if criterion_id: # Einzelnes Kriterium abrufen
            criterion = cursor.execute("SELECT id, name, max_score, description FROM criteria WHERE id = ?", (criterion_id,)).fetchone()
            if criterion:
                return jsonify({'success': True, 'criterion': dict(criterion)})
            return jsonify({'success': False, 'message': 'Kriterium nicht gefunden.'}), 404
        else: # Alle Kriterien abrufen
            criteria = cursor.execute("SELECT id, name, max_score, description FROM criteria ORDER BY ID").fetchall()
            return jsonify({'success': True, 'criteria': [dict(c) for c in criteria]})

    data = {}
    if request.method in ['POST', 'PUT']:
        if not request.is_json:
            return jsonify({'success': False, 'message': 'Anfrage muss JSON sein.'}), 400
        data = request.get_json()

    if request.method == 'POST': # Neues Kriterium hinzufügen
        name = data.get('name', '').strip()
        max_score = data.get('max_score')
        description = data.get('description', '') # HTML-Inhalt, nicht strippen

        if not name or not isinstance(max_score, int):
            return jsonify({'success': False, 'message': "Name und eine gültige Ganzzahl für max_score sind erforderlich."}), 400
        try:
            cursor.execute("INSERT INTO criteria (name, max_score, description) VALUES (?, ?, ?)",
                           (name, max_score, description))
            db.commit()
            return jsonify({'success': True, 'message': f"Kriterium '{name}' erfolgreich hinzugefügt!", 'criterion_id': cursor.lastrowid}), 201
        except sqlite3.IntegrityError:
            return jsonify({'success': False, 'message': f"Fehler: Kriterium '{name}' existiert bereits."}), 409
        except sqlite3.Error as e:
            db.rollback()
            return jsonify({'success': False, 'message': f"Ein Fehler ist aufgetreten: {e}"}), 500

    elif request.method == 'PUT': # Kriterium aktualisieren
        if not criterion_id:
            return jsonify({'success': False, 'message': "Kriterium-ID ist für die Aktualisierung erforderlich."}), 400
        name = data.get('name', '').strip()
        max_score = data.get('max_score')
        description = data.get('description', '') # HTML-Inhalt, nicht strippen

        if not name or not isinstance(max_score, int):
            return jsonify({'success': False, 'message': "Name und eine gültige Ganzzahl für max_score sind erforderlich."}), 400
        try:
            cursor.execute("UPDATE criteria SET name = ?, max_score = ?, description = ? WHERE id = ?",
                           (name, max_score, description, criterion_id))
            db.commit()
            if cursor.rowcount == 0:
                return jsonify({'success': False, 'message': "Kriterium nicht gefunden."}), 404
            return jsonify({'success': True, 'message': f"Kriterium '{name}' erfolgreich aktualisiert!"})
        except sqlite3.IntegrityError:
            return jsonify({'success': False, 'message': f"Fehler: Kriterium '{name}' existiert bereits."}), 409
        except sqlite3.Error as e:
            db.rollback()
            return jsonify({'success': False, 'message': f"Ein Fehler ist aufgetreten: {e}"}), 500

    elif request.method == 'DELETE': # Kriterium löschen
        if not criterion_id:
            return jsonify({'success': False, 'message': "Kriterium-ID ist für die Löschung erforderlich."}), 400
        try:
            cursor.execute("DELETE FROM criteria WHERE id = ?", (criterion_id,))
            db.commit()
            if cursor.rowcount == 0:
                return jsonify({'success': False, 'message': "Kriterium nicht gefunden."}), 404
            return jsonify({'success': True, 'message': "Kriterium erfolgreich gelöscht!"})
        except sqlite3.Error as e:
            db.rollback()
            return jsonify({'success': False, 'message': f"Ein Fehler ist aufgetreten: {e}"}), 500
