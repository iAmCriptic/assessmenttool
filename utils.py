import datetime
from flask import g, current_app, request, url_for
import sqlite3


def is_api_request(req):
    """Erkennt API-Aufrufe robust, auch hinter Reverse-Proxy-Unterpfaden."""
    path = (req.path or '').rstrip('/')
    if path.startswith('/api') or path.startswith('/warnings/api'):
        return True

    script_root = (req.script_root or current_app.config.get('APPLICATION_ROOT', '') or '').rstrip('/')
    if script_root:
        if path.startswith(f'{script_root}/api') or path.startswith(f'{script_root}/warnings/api'):
            return True

    forwarded_prefix = (req.headers.get('X-Forwarded-Prefix', '') or '').rstrip('/')
    if forwarded_prefix:
        if path.startswith(f'{forwarded_prefix}/api') or path.startswith(f'{forwarded_prefix}/warnings/api'):
            return True

    return False


def prefixed_url_for(endpoint, **values):
    """Erzeugt URL mit APPLICATION_ROOT, falls der Proxy keinen script_root liefert."""
    generated = url_for(endpoint, **values)
    app_root = (request.script_root or current_app.config.get('APPLICATION_ROOT', '') or '').rstrip('/')
    if app_root and generated.startswith('/') and not generated.startswith(app_root + '/'):
        return app_root + generated
    return generated

def format_datetime(value):
    """Formatiert einen ISO-Datums-/Zeitstring in 'TT.MM. - HH:MM'."""
    if value:
        try:
            dt_object = datetime.datetime.fromisoformat(value)
            return dt_object.strftime('%d.%m. - %H:%M')
        except ValueError:
            return value # Fallback, falls Format ungültig ist
    return 'N/A'

def allowed_file(filename):
    """Überprüft, ob die Dateierweiterung zulässig ist."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

def check_admin_setup_required():
    """Überprüft, ob die Admin-Einrichtung erforderlich ist."""
    db = get_db()
    cursor = db.cursor()
    admin_user = cursor.execute("SELECT id, password FROM users WHERE username = 'admin' AND is_admin = 1").fetchone()
    # Admin-Benutzer muss existieren und das Standardpasswort haben
    if admin_user and admin_user['password'] == current_app.config['DEFAULT_ADMIN_PASSWORD']:
        return True
    return False

def get_db():
    """Stellt eine Datenbankverbindung her oder gibt die aktuelle zurück."""
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row # Ermöglicht den Zugriff auf Spalten als Wörterbuch
    return g.db
