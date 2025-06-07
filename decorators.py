from functools import wraps
from flask import session, redirect, url_for, flash, request, jsonify
from db import get_db, get_role_id # Importiere get_db und get_role_id

def role_required(allowed_roles):
    """
    Decorator, der sicherstellt, dass der Benutzer angemeldet ist und eine der
    erforderlichen Rollen hat.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not session.get('logged_in'):
                # Für API-Endpunkte, gib JSON-Fehler zurück
                if request.path.startswith('/api/'):
                    return jsonify({'success': False, 'message': 'Authentication required'}), 401
                flash('Sie müssen sich anmelden, um diese Seite aufzurufen.', 'error')
                return redirect(url_for('auth.login_page')) # Verwende Blueprint-Namen

            user_roles = session.get('user_roles', []) # Liste der Rollennamen des Benutzers
            
            # Administratoren haben immer Zugriff, es sei denn, sie müssen ihr Passwort ändern
            # Diese Logik wird jetzt VORHER im before_request-Hook behandelt.
            if 'Administrator' in user_roles:
                return f(*args, **kwargs)

            has_required_role = any(role in user_roles for role in allowed_roles)
            
            if not has_required_role:
                # Für API-Endpunkte, gib JSON-Fehler zurück
                if request.path.startswith('/api/'):
                    return jsonify({'success': False, 'message': 'Access denied: You do not have the required permissions.'}), 403
                flash("Zugriff verweigert: Sie haben nicht die erforderlichen Berechtigungen für diese Seite.", "error")
                return redirect(url_for('home')) # 'home' ist eine allgemeine Route, die noch definiert werden muss
            return f(*args, **kwargs)
        return decorated_function
    return decorator
