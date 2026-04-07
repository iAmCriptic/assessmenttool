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
from werkzeug.middleware.proxy_fix import ProxyFix


class PrefixPathMiddleware:
    """Entfernt optionalen URL-Präfix aus PATH_INFO (z. B. /sommerfest)."""

    def __init__(self, app, prefix):
        self.app = app
        self.prefix = (prefix or '').rstrip('/')

    def __call__(self, environ, start_response):
        if self.prefix:
            path_info = environ.get('PATH_INFO', '') or ''
            if path_info == self.prefix:
                environ['PATH_INFO'] = '/'
            elif path_info.startswith(self.prefix + '/'):
                environ['PATH_INFO'] = path_info[len(self.prefix):] or '/'
        return self.app(environ, start_response)


app = Flask(__name__)
app.config.from_object(Config)

# Unterstützt Betrieb hinter Reverse-Proxy (z. B. Nginx mit X-Forwarded-Prefix)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1, x_prefix=1)
app.wsgi_app = PrefixPathMiddleware(app.wsgi_app, app.config.get('APPLICATION_ROOT', ''))

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


@app.after_request
def inject_app_root_script(response):
    """
    Injiziert für HTML-Seiten ein kleines Script, das:
    - den App-Unterpfad als window.APP_ROOT verfügbar macht
    - fetch('/...') automatisch auf <APP_ROOT>/... umbiegt
    """
    content_type = response.headers.get('Content-Type', '')
    if 'text/html' not in content_type:
        return response

    body = response.get_data(as_text=True)
    if '</head>' not in body or 'window.APP_ROOT' in body:
        return response

    app_root = request.script_root or app.config.get('APPLICATION_ROOT', '') or ''
    app_root = app_root.rstrip('/')
    injected = f"""
<script>
window.APP_ROOT = {app_root!r};
(function() {{
  const root = window.APP_ROOT || '';
  const originalFetch = window.fetch ? window.fetch.bind(window) : null;
  if (!originalFetch) return;
  window.fetch = function(input, init) {{
    if (typeof input === 'string' && input.startsWith('/') && !input.startsWith('//') && root) {{
      input = root + input;
    }}
    return originalFetch(input, init);
  }};

  // Sorgt dafür, dass Service-Worker-Registrierung auch hinter Unterpfaden funktioniert.
  if (navigator.serviceWorker && navigator.serviceWorker.register) {{
    const originalRegister = navigator.serviceWorker.register.bind(navigator.serviceWorker);
    navigator.serviceWorker.register = function(scriptURL, options) {{
      if (typeof scriptURL === 'string' && scriptURL.startsWith('/') && !scriptURL.startsWith('//') && root) {{
        scriptURL = root + scriptURL;
      }}
      return originalRegister(scriptURL, options);
    }};
  }}
}})();
</script>
"""
    response.set_data(body.replace('</head>', injected + '\n</head>'))
    return response


# Vor jeder Anfrage ausführen
@app.before_request
def before_request_checks():
    # Liste der Endpunkte, die ohne Login erreichbar sein müssen
    allowed_endpoints = [
        'auth.login_page',
        'auth.login',
        'auth.admin_setup',
        'general.static_files', # Wichtig für CSS, JS, Bilder
        'general.serve_service_worker', # Service Worker muss ohne Login erreichbar sein
        'admin_settings.api_get_settings', # Admin-Einstellungen API muss ohne Login erreichbar sein, um Logo/Hintergrund zu laden
        'admin_settings.api_upload_logo', # Logo-Upload sollte nur für Admins zugänglich sein, daher nicht hier
        'map.serve_uploaded_plans' # Erlaube Zugriff auf hochgeladene Planbilder
    ]
    # Erlaube alle API-Aufrufe, die nicht explizit durch @role_required geschützt sind
    # (dies wird von den Blueprints selbst gehandhabt)
    app_root = (request.script_root or app.config.get('APPLICATION_ROOT', '') or '').rstrip('/')
    prefixed_api_path = f'{app_root}/api/' if app_root else None

    if (
        request.endpoint in allowed_endpoints
        or request.path.startswith('/api/')
        or (prefixed_api_path and request.path.startswith(prefixed_api_path))
    ):
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
    host = os.environ.get('FLASK_HOST', '0.0.0.0')
    port = int(os.environ.get('FLASK_PORT', '5001'))
    debug = os.environ.get('FLASK_DEBUG', '0') == '1'
    app.run(debug=debug, host=host, port=port)
