import sqlite3
from flask import Blueprint, render_template, session, jsonify, redirect, url_for, request, current_app, send_from_directory
from decorators import role_required
from db import get_db
import os

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
