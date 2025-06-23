import os
from flask import Flask, g, session, redirect, url_for, request, jsonify, send_from_directory, flash
import sqlite3
import datetime
import pandas as pd
from werkzeug.utils import secure_filename

# Importiere Konfiguration
from config import Config

# Importiere Datenbank-Utilities
from db import get_db, close_connection, init_db, add_initial_data, get_role_id

# Importiere Hilfsfunktionen und Dekoratoren
from utils import check_admin_setup_required, format_datetime
from decorators import role_required

# Importiere Blueprints
from routes.auth import auth_bp
from routes.admin_settings import admin_settings_bp
from routes.users import users_bp
from routes.stands import stands_bp
from routes.rooms import rooms_bp
from routes.criteria import criteria_bp
from routes.evaluations import evaluations_bp
from routes.warnings import warnings_bp
from routes.inspections import inspections_bp # <<< WICHTIG: Stelle sicher, dass dies importiert ist
from routes.ranking import ranking_bp
from routes.general import general_bp
from routes.excel_uploads import excel_uploads_bp
from routes.errors import errors_bp
from routes.map import map_bp # NEU: Importiere den Map Blueprint

app = Flask(__name__)
app.config.from_object(Config)

# Registriere Teardown-Funktion für die Datenbank
app.teardown_appcontext(close_connection)

# Registriere Jinja2-Filter
app.jinja_env.filters['format_datetime'] = format_datetime

# Registriere Blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(admin_settings_bp)
app.register_blueprint(users_bp)
app.register_blueprint(stands_bp)
app.register_blueprint(rooms_bp)
app.register_blueprint(criteria_bp)
app.register_blueprint(evaluations_bp)
app.register_blueprint(warnings_bp, url_prefix='/warnings')
app.register_blueprint(inspections_bp)
app.register_blueprint(ranking_bp)
app.register_blueprint(general_bp)
app.register_blueprint(excel_uploads_bp)
app.register_blueprint(errors_bp)
app.register_blueprint(map_bp) # NEU: Registriere den Map Blueprint


# Vor jeder Anfrage ausführen
@app.before_request
def before_request_checks():
    # Liste der Endpunkte, die ohne Login erreichbar sein müssen
    allowed_endpoints = [
        'auth.login_page',
        'auth.login',
        'auth.admin_setup',
        'general.static_files', # Wichtig für CSS, JS, Bilder
        'admin_settings.api_get_settings', # Admin-Einstellungen API muss ohne Login erreichbar sein, um Logo/Hintergrund zu laden
        'admin_settings.api_upload_logo', # Logo-Upload sollte nur für Admins zugänglich sein, daher nicht hier
        'map.serve_uploaded_plans' # Erlaube Zugriff auf hochgeladene Planbilder
    ]
    # Erlaube alle API-Aufrufe, die nicht explizit durch @role_required geschützt sind
    # (dies wird von den Blueprints selbst gehandhabt)
    if request.endpoint in allowed_endpoints or request.path.startswith('/api/'):
        return None

    # Überprüfe, ob Admin-Setup erforderlich ist
    if check_admin_setup_required():
        # Wenn Admin angemeldet ist und Setup erforderlich ist, leite zur Setup-Seite weiter
        if session.get('logged_in') and session.get('username') == 'admin':
            if request.endpoint != 'auth.admin_setup': # Verhindere Endlosschleife
                return redirect(url_for('auth.admin_setup'))
        # Wenn nicht angemeldet, aber Setup erforderlich ist, stelle sicher, dass sie zur Login-Seite gelangen
        elif not session.get('logged_in'):
            if request.endpoint not in ['auth.login_page', 'auth.login']: # Verhindere Endlosschleife
                return redirect(url_for('auth.login_page'))
    
    # Wenn Admin-Setup nicht erforderlich ist oder der Benutzer kein Admin ist, fahre normal fort
    return None

@app.route('/')
def index():
    """Leitet zur Login-Seite weiter."""
    return redirect(url_for('auth.login_page'))

# Route für statische Dateien im Hauptverzeichnis (z.B. manifest.json, service-worker.js)
@app.route('/<path:filename>')
def serve_static(filename):
    """Dient statischen Dateien aus dem Root-Verzeichnis."""
    root_dir = os.getcwd()
    return send_from_directory(os.path.join(root_dir, 'static'), filename)


if __name__ == '__main__':
    # Initialisiere die Datenbank und füge Startdaten hinzu
    with app.app_context():
        init_db()
        add_initial_data()
    app.run(debug=True, host='0.0.0.0', port='5000')  # Host auf
