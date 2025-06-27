import sqlite3
from flask import Blueprint, render_template, session, jsonify, redirect, url_for, request, current_app, send_from_directory
from decorators import role_required
from db import get_db
import os
# Importiere die zentrale Versionskonfiguration
from config_version import FRONTEND_VERSION, BACKEND_VERSION


general_bp = Blueprint('general', __name__)

@general_bp.route('/home')
@role_required(['Administrator', 'Bewerter', 'Betrachter', 'Inspektor', 'Verwarner'])
def home():
    """Zeigt die Startseite an."""
    return render_template('home.html', dark_mode_enabled=session.get('dark_mode_enabled'))

@general_bp.route('/api/session_data')
@role_required(['Administrator', 'Bewerter', 'Betrachter', 'Inspektor', 'Verwarner'])
def api_session_data():
    """Gibt die aktuellen Sitzungsdaten des Benutzers als JSON zurück."""
    return jsonify({
        'success': True,
        'logged_in': session.get('logged_in', False),
        'username': session.get('username'),
        'display_name': session.get('display_name'),
        'user_id': session.get('user_id'),
        'is_admin': session.get('is_admin', False),
        'user_roles': session.get('user_roles', []),
        'dark_mode_enabled': session.get('dark_mode_enabled', False)
    })

@general_bp.route('/toggle_dark_mode', methods=['POST'])
@role_required(['Administrator', 'Bewerter', 'Betrachter', 'Inspektor', 'Verwarner'])
def toggle_dark_mode():
    """Schaltet den Dark Mode um."""
    session['dark_mode_enabled'] = not session.get('dark_mode_enabled', False)
    return jsonify(success=True, dark_mode_enabled=session['dark_mode_enabled'])

@general_bp.route('/static_files/<path:filename>')
def static_files(filename):
    """Dient statischen Dateien aus dem Unterordner 'static'."""
    return send_from_directory(current_app.static_folder, filename)

@general_bp.route('/service-worker.js')
def serve_service_worker():
    """Dient dem Service Worker aus dem Root-Verzeichnis."""
    # Dies wird verwendet, um Dateien außerhalb des 'static'-Ordners zu senden
    return send_from_directory(current_app.root_path, 'service-worker.js', mimetype='application/javascript')

# NEW ROUTE for the example Excel file for stands (moved from app.py)
@general_bp.route('/static/beispiel_staende.xlsx')
def download_beispiel_staende_excel():
    """Stellt die beispiel_staende.xlsx-Datei aus dem statischen Ordner zum Download bereit."""
    # Korrektur: Verwende send_from_directory mit as_attachment=True
    return send_from_directory(current_app.static_folder, 'beispiel_staende.xlsx', as_attachment=True)

# NEW ROUTE for the example Excel file for users (moved from app.py)
@general_bp.route('/static/beispiel_benutzer.xlsx')
def download_beispiel_benutzer_excel():
    """Stellt die beispiel_benutzer.xlsx-Datei aus dem statischen Ordner zum Download bereit."""
    # Korrektur: Verwende send_from_directory mit as_attachment=True
    return send_from_directory(current_app.static_folder, 'beispiel_benutzer.xlsx', as_attachment=True)

# NEW ROUTE for the example Excel file for criteria (moved from app.py)
@general_bp.route('/static/beispiel_kriterien.xlsx')
def download_beispiel_kriterien_excel():
    """Stellt die beispiel_kriterien.xlsx-Datei aus dem statischen Ordner zum Download bereit."""
    # Korrektur: Verwende send_from_directory mit as_attachment=True
    return send_from_directory(current_app.static_folder, 'beispiel_kriterien.xlsx', as_attachment=True)

# NEW ROUTE for view_plan.html
@general_bp.route('/view_plan')
@role_required(['Administrator', 'Bewerter', 'Betrachter', 'Inspektor', 'Verwarner'])
def view_plan():
    """Zeigt die Seite zur Ansicht des Lageplans an."""
    return render_template('view_plan.html', dark_mode_enabled=session.get('dark_mode_enabled'))

@general_bp.route('/manage_list', methods=['GET'])
@role_required(['Administrator'])
def manage_list_page():
    """Verwaltet das Zurücksetzen von Rangliste und Rauminspektionen."""
    # Korrektur: Verwende render_template, da manage_list.html Jinja2-Variablen enthalten wird.
    dark_mode_enabled = session.get('dark_mode_enabled', False)
    return render_template('manage_list.html', dark_mode_enabled=dark_mode_enabled)

# NEUE API-ROUTE FÜR ZURÜCKSETZEN VON DATEN
@general_bp.route('/api/reset_data', methods=['POST'])
@role_required(['Administrator'])
def api_reset_data():
    """
    Sets various data in the database back, based on the 'action'.
    Requires Administrator role.
    """
    db = get_db()
    cursor = db.cursor()
    data = request.get_json()
    action = data.get('action')

    if not action:
        return jsonify({'success': False, 'message': 'Action not specified.'}), 400

    try:
        if action == 'reset_ranking':
            # Delete all entries from evaluation_scores and evaluations
            cursor.execute("DELETE FROM evaluation_scores")
            cursor.execute("DELETE FROM evaluations")
            db.commit()
            return jsonify({'success': True, 'message': 'Ranking and all evaluations successfully reset!'})
        elif action == 'reset_room_inspections':
            # Delete all entries from room_inspections
            cursor.execute("DELETE FROM room_inspections")
            db.commit()
            return jsonify({'success': True, 'message': 'All room inspections successfully reset!'})
        elif action == 'reset_warnings':
            # Delete all entries from warnings
            cursor.execute("DELETE FROM warnings")
            db.commit()
            return jsonify({'success': True, 'message': 'All warnings successfully reset!'})
        else:
            return jsonify({'success': False, 'message': 'Invalid action.'}), 400
    except sqlite3.Error as e:
        db.rollback()
        print(f"Database error during reset action {action}: {e}")
        return jsonify({'success': False, 'message': f'Error resetting data: {e}'}), 500
    except Exception as e:
        db.rollback()
        print(f"An unexpected error occurred during reset action {action}: {e}")
        return jsonify({'success': False, 'message': f'An unexpected error occurred: {e}'}), 500


@general_bp.route('/api/versions', methods=['GET'])
def api_versions():
    """
    Returns frontend and backend version information as JSON.
    """
    return jsonify({
        'success': True,
        'frontend_version': FRONTEND_VERSION,
        'backend_version': BACKEND_VERSION
    })

