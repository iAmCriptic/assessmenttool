import sqlite3
from flask import Blueprint, request, jsonify, session, current_app, render_template, url_for
from db import get_db
from decorators import role_required
import datetime
from datetime import timezone # Importiere timezone

evaluations_bp = Blueprint('evaluations', __name__)

@evaluations_bp.route('/evaluate', methods=['GET', 'POST'])
@role_required(['Administrator', 'Bewerter'])
def evaluate_page():
    """Rendert das Bewertungsformular und verarbeitet Bewertungen."""
    if request.method == 'GET':
        dark_mode_enabled = session.get('dark_mode_enabled', False)
        return render_template('evaluation.html', dark_mode_enabled=dark_mode_enabled)
    
    if request.method == 'POST':
        db = get_db()
        cursor = db.cursor()
        data = request.get_json() 
        
        # DEBUG: Log raw received data
        print(f"DEBUG (Flask): Received data for /evaluate POST: {data}")

        selected_stand_id = data.get('stand_id')
        scores_data = data.get('scores')
        
        user_id = session['user_id']

        if not selected_stand_id or not scores_data:
            print(f"DEBUG (Flask): Missing stand_id or scores_data. Stand ID: {selected_stand_id}, Scores: {scores_data}")
            return jsonify({'success': False, 'message': 'Stand-ID und Bewertungen sind erforderlich.'}), 400

        try:
            cursor.execute("SELECT id FROM evaluations WHERE user_id = ? AND stand_id = ?", (user_id, selected_stand_id))
            existing_evaluation = cursor.fetchone()

            if existing_evaluation:
                evaluation_id = existing_evaluation['id']
                cursor.execute("UPDATE evaluations SET timestamp = CURRENT_TIMESTAMP WHERE id = ?", (evaluation_id,))
                # Vorhandene Punktzahlen für diese Bewertung löschen, um Duplikate oder alte Punktzahlen zu vermeiden
                cursor.execute("DELETE FROM evaluation_scores WHERE evaluation_id = ?", (evaluation_id,))
                message = "Deine Bewertung wurde erfolgreich aktualisiert!"
                print(f"DEBUG (Flask): Updated existing evaluation {evaluation_id} for user {user_id}, stand {selected_stand_id}")
            else:
                cursor.execute(
                    "INSERT INTO evaluations (stand_id, user_id) VALUES (?, ?)",
                    (selected_stand_id, user_id)
                )
                evaluation_id = cursor.lastrowid
                message = "Deine Bewertung wurde erfolgreich gespeichert!"
                print(f"DEBUG (Flask): Created new evaluation {evaluation_id} for user {user_id}, stand {selected_stand_id}")
            
            # Kriterien-Maximalpunktzahlen abrufen
            criteria_max_scores = {c['id']: c['max_score'] for c in cursor.execute("SELECT id, max_score FROM criteria").fetchall()}
            print(f"DEBUG (Flask): Criteria max scores: {criteria_max_scores}")

            # Neue Punktzahlen einfügen
            for criterion_id_str, score_value in scores_data.items():
                criterion_id = int(criterion_id_str)
                max_score = criteria_max_scores.get(criterion_id)

                if max_score is None:
                    print(f"DEBUG (Flask): Criterion {criterion_id} not found in max scores, skipping.")
                    # Kriterium nicht gefunden, überspringen
                    continue 
                
                try:
                    score_value = int(score_value)
                except (ValueError, TypeError):
                    print(f"DEBUG (Flask): Invalid score value '{score_value}' for criterion {criterion_id}, deleting any existing entry.")
                    # Wenn der Wert keine gültige Zahl ist, lösche einen vorhandenen Eintrag für dieses Kriterium
                    cursor.execute("DELETE FROM evaluation_scores WHERE evaluation_id = ? AND criterion_id = ?",
                                   (evaluation_id, criterion_id))
                    continue

                if 0 <= score_value <= max_score:
                    # Füge die Punktzahl ein (kein Update nötig, da wir vorher gelöscht haben)
                    cursor.execute("INSERT INTO evaluation_scores (evaluation_id, criterion_id, score) VALUES (?, ?, ?)",
                                   (evaluation_id, criterion_id, score_value))
                    print(f"DEBUG (Flask): Inserted score {score_value} for criterion {criterion_id} in evaluation {evaluation_id}")
                else:
                    # Wenn die Punktzahl außerhalb des gültigen Bereichs liegt, lösche sie
                    cursor.execute("DELETE FROM evaluation_scores WHERE evaluation_id = ? AND criterion_id = ?",
                                   (evaluation_id, criterion_id))
                    print(f"DEBUG (Flask): Score {score_value} for criterion {criterion_id} out of range, deleting any existing entry.")

            db.commit()
            return jsonify({'success': True, 'message': message})

        except sqlite3.Error as e:
            db.rollback()
            print(f"Database error in evaluate_page (POST): {e}")
            return jsonify({'success': False, 'message': f"Fehler beim Speichern/Aktualisieren der Bewertung: {e}"}), 500
        except Exception as e:
            db.rollback()
            print(f"An unexpected error occurred in evaluate_page (POST): {e}")
            return jsonify({'success': False, 'message': f"Ein unerwarteter Fehler ist aufgetreten: {e}"}), 500
    

@evaluations_bp.route('/api/evaluate_initial_data', methods=['GET'])
@role_required(['Administrator', 'Bewerter'])
def api_evaluate_initial_data():
    """Gibt Initialdaten (Stände und Kriterien) für den Bewertungsbogen zurück."""
    db = get_db()
    cursor = db.cursor()

    try:
        # Hinzufügen von s.description zum SELECT-Statement für Stände
        stands = cursor.execute('''
            SELECT s.id, s.name, s.description, r.name AS room_name
            FROM stands s
            LEFT JOIN rooms r ON s.room_id = r.id
            ORDER BY s.name
        ''').fetchall()
        
        criteria = cursor.execute("SELECT id, name, description, max_score FROM criteria ORDER BY ID").fetchall()

        print(f"DEBUG (Flask): Initial data Stands: {[dict(s) for s in stands]}")
        print(f"DEBUG (Flask): Initial data Criteria: {[dict(c) for c in criteria]}")

        return jsonify({
            'success': True,
            'stands': [dict(s) for s in stands],
            'criteria': [dict(c) for c in criteria]
        })
    except sqlite3.Error as e:
        print(f"Database error in api_evaluate_initial_data: {e}")
        return jsonify({'success': False, 'message': f'Fehler beim Abrufen der Initialdaten: {e}'}), 500
    except Exception as e:
        print(f"An unexpected error occurred in api_evaluate_initial_data: {e}")
        return jsonify({'success': False, 'message': f'Ein unerwarteter Fehler ist aufgetreten: {e}'}), 500

@evaluations_bp.route('/view_my_evaluations')
@role_required(['Administrator', 'Bewerter'])
def view_my_evaluations_page():
    """Rendert die Seite 'Meine Bewertungen'."""
    dark_mode_enabled = session.get('dark_mode_enabled', False)
    # Korrektur: Verwende render_template für HTML-Dateien im templates-Ordner
    return render_template('view_my_evaluations.html', dark_mode_enabled=dark_mode_enabled)

@evaluations_bp.route('/api/my_evaluations')
@role_required(['Administrator', 'Bewerter'])
def api_my_evaluations():
    """Gibt alle Bewertungen des aktuell angemeldeten Benutzers als JSON zurück."""
    user_id = session['user_id']
    db = get_db()
    cursor = db.cursor()

    evaluations = cursor.execute('''
        SELECT
            e.id AS evaluation_id,
            s.name AS stand_name,
            e.timestamp
        FROM evaluations e
        JOIN stands s ON e.stand_id = s.id
        WHERE e.user_id = ?
        ORDER BY e.timestamp DESC
    ''', (user_id,)).fetchall()

    eval_with_scores = []
    for eval_entry in evaluations:
        eval_dict = dict(eval_entry)
        total_score_row = cursor.execute('''
            SELECT SUM(es.score) AS total_score
            FROM evaluation_scores es
            WHERE es.evaluation_id = ?
        ''', (eval_dict['evaluation_id'],)).fetchone()
        
        eval_dict['total_achieved_score'] = total_score_row['total_score'] if total_score_row and total_score_row['total_score'] is not None else 0
        # Format timestamp to ISO 8601 for consistent parsing in frontend
        if eval_dict['timestamp']:
            # Assume timestamp from DB is UTC and make it timezone-aware
            dt_object = datetime.datetime.fromisoformat(eval_dict['timestamp'])
            # If the database stores naive datetimes, and we know it's UTC, attach UTC timezone info
            if dt_object.tzinfo is None:
                dt_object = dt_object.replace(tzinfo=timezone.utc)
            eval_dict['timestamp'] = dt_object.isoformat()
        eval_with_scores.append(eval_dict)

    return jsonify({'success': True, 'evaluations': eval_with_scores})

@evaluations_bp.route('/api/evaluations/user_scores/<int:stand_id>', methods=['GET'])
@role_required(['Administrator', 'Bewerter', 'Betrachter', 'Inspektor', 'Verwarner'])
def api_user_evaluation_scores(stand_id):
    """Gibt die Bewertungspunkte des aktuellen Benutzers für einen bestimmten Stand zurück."""
    db = get_db()
    cursor = db.cursor()
    user_id = session.get('user_id')

    print(f"DEBUG (Flask): Requesting user scores for stand_id={stand_id}, user_id={user_id}")

    if not user_id:
        print("DEBUG (Flask): User not logged in for api_user_evaluation_scores.")
        return jsonify({'success': False, 'message': 'Benutzer nicht angemeldet.'}), 401

    try:
        cursor.execute("SELECT id, timestamp FROM evaluations WHERE user_id = ? AND stand_id = ?", (user_id, stand_id))
        existing_evaluation = cursor.fetchone()

        if existing_evaluation:
            evaluation_id = existing_evaluation['id']
            timestamp = existing_evaluation['timestamp']

            scores = {}
            score_rows = cursor.execute("SELECT criterion_id, score FROM evaluation_scores WHERE evaluation_id = ?", (evaluation_id,)).fetchall()
            for row in score_rows:
                scores[row['criterion_id']] = row['score']
            
            # Zeitstempel im ISO-Format zurückgeben
            # fromisoformat wandelt den String in ein datetime-Objekt um
            # .isoformat() wandelt es in einen ISO 8601-String um, der von JS Date() gut verarbeitet wird
            iso_timestamp = None
            if timestamp:
                dt_object = datetime.datetime.fromisoformat(timestamp)
                # Wenn die Datenbank naive Datetimes speichert und wir wissen, dass es UTC ist,
                # fügen wir die Zeitzoneninformation hinzu.
                if dt_object.tzinfo is None:
                    dt_object = dt_object.replace(tzinfo=timezone.utc)
                iso_timestamp = dt_object.isoformat()

            print(f"DEBUG (Flask): Found existing evaluation {evaluation_id} for stand {stand_id}, scores: {scores}, timestamp: {iso_timestamp}")
            return jsonify({'success': True, 'exists': True, 'scores': scores, 'timestamp': iso_timestamp})
        else:
            print(f"DEBUG (Flask): No existing evaluation found for stand {stand_id} and user {user_id}.")
            return jsonify({'success': True, 'exists': False, 'scores': {}})
    except sqlite3.Error as e:
        print(f"Database error in api_user_evaluation_scores: {e}")
        return jsonify({'success': False, 'message': f'Fehler beim Abrufen der Bewertung: {e}'}), 500
    except Exception as e:
        print(f"An unexpected error occurred in api_user_evaluation_scores: {e}")
        return jsonify({'success': False, 'message': f'Ein unerwarteter Fehler ist aufgetreten: {e}'}), 500

@evaluations_bp.route('/get_stand_description/<int:stand_id>')
@role_required(['Administrator', 'Bewerter', 'Betrachter', 'Inspektor', 'Verwarner'])
def get_stand_description(stand_id):
    """Gibt die Beschreibung eines Standes als JSON zurück."""
    db = get_db()
    cursor = db.cursor()
    stand = cursor.execute("SELECT description FROM stands WHERE id = ?", (stand_id,)).fetchone()
    
    if stand:
        return jsonify({'success': True, 'description': stand['description'] or 'No description available.'})
    else:
        return jsonify({'success': False, 'description': 'Keine Beschreibung verfügbar.', 'message': 'Stand nicht gefunden.'}), 404


@evaluations_bp.route('/print_evaluation/<int:evaluation_id>')
@role_required(['Administrator', 'Bewerter', 'Betrachter', 'Inspektor', 'Verwarner'])
def print_evaluation(evaluation_id):
    """Rendert die Druckansicht einer spezifischen Bewertung (ausgefüllt)."""
    dark_mode_enabled = session.get('dark_mode_enabled', False)
    db = get_db()
    cursor = db.cursor()
    settings = cursor.execute("SELECT setting_key, setting_value FROM app_settings WHERE setting_key = 'logo_path'").fetchone()
    logo_url = url_for('general.static_files', filename='img/logo_V2.png') # Standard-Logo
    if settings and settings['setting_value']:
        logo_url = url_for('general.static_files', filename=settings['setting_value'])

    return render_template('print_evaluation.html', dark_mode_enabled=dark_mode_enabled, logo_url=logo_url)

@evaluations_bp.route('/view_blank_printevaluations')
@role_required(['Administrator', 'Bewerter', 'Inspektor', 'Verwarner'])
def view_blank_printevaluations_page():
    """Zeigt eine Übersicht aller Stände zum Drucken leerer Bewertungsformulare an."""
    dark_mode_enabled = session.get('dark_mode_enabled', False) # Lade den Dark Mode Status
    return render_template('view_blank_printevaluations.html', dark_mode_enabled=dark_mode_enabled) # Übergebe ihn an das Template

# NEUE ROUTE für die HTML-Ansicht der leeren Bewertungsbogen-Vorlage
@evaluations_bp.route('/print_evaluation_template/<int:stand_id>')
@role_required(['Administrator', 'Bewerter', 'Betrachter', 'Inspektor', 'Verwarner'])
def render_print_evaluation_template(stand_id):
    """Rendert die HTML-Seite für ein leeres Bewertungsformular für einen bestimmten Stand."""
    db = get_db()
    cursor = db.cursor()

    # Logo-Pfad aus den Einstellungen abrufen
    settings = cursor.execute("SELECT setting_key, setting_value FROM app_settings WHERE setting_key = 'logo_path'").fetchone()
    logo_url = url_for('general.static_files', filename='img/logo_V2.png') # Standard-Logo
    if settings and settings['setting_value']:
        logo_url = url_for('general.static_files', filename=settings['setting_value'])

    stand = cursor.execute("SELECT s.id, s.name, s.description, r.name AS room_name FROM stands s LEFT JOIN rooms r ON s.room_id = r.id WHERE s.id = ?", (stand_id,)).fetchone()
    if not stand:
        from flask import abort
        abort(404, description="Stand nicht gefunden.")

    criteria_data = [dict(row) for row in cursor.execute("SELECT id, name, max_score, description FROM criteria ORDER BY id").fetchall()]
    total_max_possible_score = sum(c['max_score'] for c in criteria_data)

    template_data = {
        'stand': dict(stand),
        'criteria': criteria_data,
        'total_max_possible_score': total_max_possible_score,
        'logo_url': logo_url,  # logo_url an das Template übergeben
    }
    dark_mode_enabled = session.get('dark_mode_enabled', False)
    return render_template('print_evaluation_template.html', **template_data, dark_mode_enabled=dark_mode_enabled)

# Bestehende API-Route für die Daten der leeren Bewertungsbogen-Vorlage
@evaluations_bp.route('/api/blank_evaluations', methods=['GET'])
@role_required(['Administrator', 'Bewerter', 'Inspektor', 'Verwarner'])
def api_blank_evaluations():
    """Gibt Daten für leere Bewertungsformulare als JSON zurück."""
    db = get_db()
    cursor = db.cursor()
    stands = cursor.execute("SELECT s.id, s.name, s.description, r.name AS room_name FROM stands s LEFT JOIN rooms r ON s.room_id = r.id ORDER BY s.name").fetchall()
    
    criteria = [dict(row) for row in cursor.execute("SELECT id, name, max_score, description FROM criteria ORDER BY id").fetchall()]
    total_max_possible_score = sum(c['max_score'] for c in criteria)

    return jsonify({
        'success': True,
        'stands': [dict(s) for s in stands],
        'criteria': criteria,
        'total_max_possible_score': total_max_possible_score
    })

@evaluations_bp.route('/api/evaluation_details/<int:evaluation_id>', methods=['GET'])
@role_required(['Administrator', 'Bewerter', 'Betrachter', 'Inspektor', 'Verwarner'])
def api_evaluation_details(evaluation_id):
    """Gibt die Details einer spezifischen Bewertung zurück, einschließlich Kriterien und erzielten Punkten."""
    db = get_db()
    cursor = db.cursor()

    try:
        # Basis-Bewertungsinformationen
        evaluation = cursor.execute('''
            SELECT
                e.id AS evaluation_id,
                s.name AS stand_name,
                s.description AS stand_description,
                u.display_name AS evaluator_display_name,
                e.timestamp
            FROM evaluations e
            JOIN stands s ON e.stand_id = s.id
            JOIN users u ON e.user_id = u.id
            WHERE e.id = ?
        ''', (evaluation_id,)).fetchone()

        if not evaluation:
            return jsonify({'success': False, 'message': 'Bewertung nicht gefunden.'}), 404

        # Kriterien mit erzielten Punkten
        criteria_with_scores = cursor.execute('''
            SELECT
                c.id AS criterion_id,
                c.name AS name,
                c.description AS description,
                c.max_score AS max_score,
                es.score AS achieved_score
            FROM evaluation_scores es
            JOIN criteria c ON es.criterion_id = c.id
            WHERE es.evaluation_id = ?
            ORDER BY c.id
        ''', (evaluation_id,)).fetchall()

        # Gesamtpunktzahl und maximale mögliche Punktzahl berechnen
        total_achieved_score = sum(row['achieved_score'] for row in criteria_with_scores)
        
        # Holen Sie sich die maximale Punktzahl für alle Kriterien (unabhängig von dieser Bewertung)
        all_criteria_max_scores = cursor.execute("SELECT SUM(max_score) FROM criteria").fetchone()[0]
        total_max_possible_score = all_criteria_max_scores if all_criteria_max_scores is not None else 0

        # Format timestamp to ISO 8601 for consistent parsing in frontend
        evaluation_dict = dict(evaluation) # ensure it's a dict
        if evaluation_dict['timestamp']:
            dt_object = datetime.datetime.fromisoformat(evaluation_dict['timestamp'])
            # If the database stores naive datetimes, and we know it's UTC, attach UTC timezone info
            if dt_object.tzinfo is None:
                dt_object = dt_object.replace(tzinfo=timezone.utc)
            evaluation_dict['timestamp'] = dt_object.isoformat()
        else:
            evaluation_dict['timestamp'] = None


        return jsonify({
            'success': True,
            'data': {
                'evaluation': evaluation_dict,
                'criteria_with_scores': [dict(c) for c in criteria_with_scores],
                'total_achieved_score': total_achieved_score,
                'total_max_possible_score': total_max_possible_score
            }
        })
    except sqlite3.Error as e:
        print(f"Database error in api_evaluation_details: {e}")
        return jsonify({'success': False, 'message': f'Fehler beim Abrufen der Bewertungsdetails: {e}'}), 500
    except Exception as e:
        print(f"An unexpected error occurred in api_evaluation_details: {e}")
        return jsonify({'success': False, 'message': f'Ein unerwarteter Fehler ist aufgetreten: {e}'}), 500
