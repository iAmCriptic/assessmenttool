import sqlite3
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, current_app
from db import get_db, get_role_id
from utils import check_admin_setup_required

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET'])
def login_page():
    """Rendert die Login-Seite."""
    db = get_db()
    cursor = db.cursor()
    # Logo-Pfad aus den Einstellungen abrufen
    settings_rows = cursor.execute("SELECT setting_key, setting_value FROM app_settings WHERE setting_key = 'logo_path'").fetchone()
    
    logo_url = url_for('general.static_files', filename='img/logo_V2.png') # Standard-Logo
    if settings_rows and settings_rows['setting_value']:
        logo_url = url_for('general.static_files', filename=settings_rows['setting_value'])

    return render_template('index.html', dark_mode_enabled=session.get('dark_mode_enabled'), logo_url=logo_url)

@auth_bp.route('/login', methods=['POST'])
def login():
    """Verarbeitet Login-Anfragen."""
    username = request.form['username']
    password = request.form['password']
    db = get_db()
    cursor = db.cursor()
    
    # Benutzerdaten abrufen
    cursor.execute("SELECT id, username, display_name, is_admin, password FROM users WHERE username = ? AND password = ?", (username, password))
    user = cursor.fetchone()

    if user:
        session['logged_in'] = True
        session['username'] = user['username']
        session['display_name'] = user['display_name'] if user['display_name'] else user['username']
        session['user_id'] = user['id']
        session['is_admin'] = bool(user['is_admin'])

        # Alle Rollen des Benutzers abrufen
        cursor.execute("""
            SELECT r.name
            FROM roles r
            JOIN user_roles ur ON r.id = ur.role_id
            WHERE ur.user_id = ?
        """, (user['id'],))
        user_roles = [row['name'] for row in cursor.fetchall()]
        session['user_roles'] = user_roles # Liste der Rollennamen in der Session speichern

        # Bestimme die primäre Rolle für die Rückgabe an den Client
        # Wenn der Benutzer mehrere Rollen hat, wird die erste in der Liste gesendet.
        # Wenn der Benutzer keine Rollen hat, ist user_role_to_send None, und Flutter verwendet seinen Standardwert.
        user_role_to_send = user_roles[0] if user_roles else None

        # Wenn Admin sich mit Standardpasswort anmeldet, ist Setup erforderlich
        if user['username'] == 'admin' and user['password'] == current_app.config['DEFAULT_ADMIN_PASSWORD']:
            return jsonify({
                'success': True,
                'message': 'Admin-Login erfolgreich, Setup erforderlich.',
                'redirect_to_setup': True,
                'user_role': user_role_to_send # Sende die Rolle auch bei Admin-Setup
            })

        return jsonify({
            'success': True,
            'message': 'Login erfolgreich.',
            'redirect_to_setup': False,
            'user_role': user_role_to_send # Sende die Rolle
        })
    else:
        return jsonify({'success': False, 'message': 'Ungültiger Benutzername oder Passwort'}), 401

@auth_bp.route('/logout')
def logout():
    """Meldet den Benutzer ab."""
    session.pop('logged_in', None)
    session.pop('username', None)
    session.pop('display_name', None)
    session.pop('user_id', None)
    session.pop('is_admin', None)
    session.pop('user_roles', None)
    session.pop('dark_mode_enabled', None) # Dark Mode-Präferenz beim Abmelden löschen
    return redirect(url_for('auth.login_page'))

@auth_bp.route('/api/logout') # API-Endpunkt zum Abmelden
def api_logout():
    """Meldet den Benutzer ab und gibt eine JSON-Antwort zurück."""
    session.pop('logged_in', None)
    session.pop('username', None)
    session.pop('display_name', None)
    session.pop('user_id', None)
    session.pop('is_admin', None)
    session.pop('user_roles', None)
    session.pop('dark_mode_enabled', None) # Dark Mode-Präferenz beim Abmelden löschen
    return jsonify({'success': True, 'message': 'Erfolgreich abgemeldet'})

@auth_bp.route('/admin_setup', methods=['GET', 'POST'])
def admin_setup():
    """
    Seite zur initialen Einrichtung des Administratorkontos.
    Nur zugänglich, wenn Admin mit dem Standardpasswort angemeldet ist.
    """
    db = get_db()
    cursor = db.cursor()
    
    # Überprüfen, ob der aktuell angemeldete Benutzer 'admin' ist und noch das Standardpasswort hat
    if not session.get('logged_in') or session.get('username') != 'admin':
        # Wenn nicht angemeldet oder kein Admin, leite zu Login-Seite für HTML-Anfragen weiter
        if not request.path.startswith('/api/'):
            return redirect(url_for('auth.login_page'))
        # Für API-Anfragen, gib "nicht autorisiert" zurück
        return jsonify({'success': False, 'message': 'Unauthorized access'}), 401

    cursor.execute("SELECT password FROM users WHERE username = 'admin'")
    admin_password_row = cursor.fetchone()
    
    if not admin_password_row or admin_password_row['password'] != current_app.config['DEFAULT_ADMIN_PASSWORD']:
        # Admin-Passwort wurde bereits geändert oder es ist kein Admin-Benutzer
        if not request.path.startswith('/api/'):
            return redirect(url_for('home')) # Leite zur Startseite weiter
        return jsonify({'success': False, 'message': 'Admin-Setup nicht erforderlich oder bereits abgeschlossen'}), 400

    if request.method == 'POST':
        # Erwarte JSON-Daten für API-Aufrufe
        data = request.get_json()
        new_password = data.get('new_password', '').strip()
        confirm_password = data.get('confirm_password', '').strip()
        display_name = data.get('display_name', '').strip()

        if not display_name:
            display_name = "Administrator" # Standard-Anzeigename, falls keiner angegeben

        if new_password == current_app.config['DEFAULT_ADMIN_PASSWORD']:
            return jsonify({'success': False, 'message': f"Das neue Passwort darf nicht das Standardpasswort '{current_app.config['DEFAULT_ADMIN_PASSWORD']}' sein."}), 400
        elif not new_password or not confirm_password:
            return jsonify({'success': False, 'message': "Bitte geben Sie ein neues Passwort und eine Bestätigung ein."}), 400
        elif new_password != confirm_password:
            return jsonify({'success': False, 'message': "Passwörter stimmen nicht überein."}), 400
        else:
            try:
                # Admin-Benutzer-ID abrufen
                cursor.execute("SELECT id FROM users WHERE username = 'admin'")
                admin_id = cursor.fetchone()['id']

                # Passwort und Anzeigename aktualisieren
                cursor.execute("UPDATE users SET password = ?, display_name = ? WHERE id = ?",
                               (new_password, display_name, admin_id))
                db.commit()
                
                # Session aktualisieren, da sich der Anzeigename geändert haben könnte
                if session.get('username') == 'admin': # Stelle sicher, dass nur der aktuelle Benutzer Admin ist
                    session['display_name'] = display_name
                
                return jsonify({'success': True, 'message': "Administratorkonto erfolgreich eingerichtet!"})

            except sqlite3.Error as e:
                db.rollback()
                return jsonify({'success': False, 'message': f"Fehler beim Einrichten des Administratorkontos: {e}"}), 500
    
    # Für GET-Anfrage, rendern Sie weiterhin die HTML-Vorlage
    return render_template('admin_setup.html', dark_mode_enabled=session.get('dark_mode_enabled'))
