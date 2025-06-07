# routes/errors.py
from flask import Blueprint, render_template, session, g

errors_bp = Blueprint('errors', __name__)

@errors_bp.app_errorhandler(400)
def bad_request_error(error):
    """Handle 400 Bad Request errors."""
    dark_mode_enabled = session.get('dark_mode_enabled', False)
    return render_template('error.html', error_code=400, error_message="Bad Request: Die Anfrage konnte vom Server nicht verarbeitet werden, da die Syntax ungültig ist.", dark_mode_enabled=dark_mode_enabled), 400

@errors_bp.app_errorhandler(401)
def unauthorized_error(error):
    """Handle 401 Unauthorized errors."""
    dark_mode_enabled = session.get('dark_mode_enabled', False)
    # Beachten Sie, dass der Fehlerobjekt hier oft die Beschreibung des Fehlers enthält
    message = getattr(error, 'description', "Unauthorized: Sie sind nicht angemeldet oder Ihre Sitzung ist abgelaufen. Bitte melden Sie sich an.")
    return render_template('error.html', error_code=401, error_message=message, dark_mode_enabled=dark_mode_enabled), 401

@errors_bp.app_errorhandler(403)
def forbidden_error(error):
    """Handle 403 Forbidden errors."""
    dark_mode_enabled = session.get('dark_mode_enabled', False)
    message = getattr(error, 'description', "Forbidden: Sie haben keine Berechtigung, auf diese Ressource zuzugreifen.")
    return render_template('error.html', error_code=403, error_message=message, dark_mode_enabled=dark_mode_enabled), 403

@errors_bp.app_errorhandler(404)
def not_found_error(error):
    """Handle 404 Not Found errors."""
    dark_mode_enabled = session.get('dark_mode_enabled', False)
    return render_template('error.html', error_code=404, error_message="Not Found: Die angeforderte Seite oder Ressource konnte nicht gefunden werden.", dark_mode_enabled=dark_mode_enabled), 404

@errors_bp.app_errorhandler(500)
def internal_error(error):
    """Handle 500 Internal Server Error errors."""
    dark_mode_enabled = session.get('dark_mode_enabled', False)
    # Sicherstellen, dass die Datenbank-Transaktion im Fehlerfall zurückgesetzt wird
    db = getattr(g, 'db', None)
    if db is not None:
        db.rollback()
    return render_template('error.html', error_code=500, error_message="Internal Server Error: Ein unerwarteter Fehler ist auf dem Server aufgetreten. Bitte versuchen Sie es später erneut.", dark_mode_enabled=dark_mode_enabled), 500

