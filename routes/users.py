import sqlite3
from flask import Blueprint, request, jsonify, session, current_app, render_template # render_template wurde hinzugefügt
from db import get_db
from decorators import role_required

users_bp = Blueprint('users', __name__)

@users_bp.route('/manage_users', methods=['GET'])
@role_required(['Administrator'])
def manage_users_page():
    """Rendert die Benutzerverwaltungsseite."""
    # Statt send_static_file verwenden wir render_template,
    # da manage_users.html Jinja2-Variablen enthält.
    dark_mode_enabled = session.get('dark_mode_enabled', False)
    return render_template('manage_users.html', dark_mode_enabled=dark_mode_enabled)

@users_bp.route('/api/users', methods=['GET', 'POST', 'PUT', 'DELETE'])
@role_required(['Administrator'])
def api_users():
    """API-Endpunkt zur Verwaltung von Benutzern."""
    db = get_db()
    cursor = db.cursor()

    if request.method == 'GET':
        # Angepasste SQL-Abfrage: 'u.is_active' wurde entfernt, da die Spalte nicht existiert.
        users = cursor.execute('''
            SELECT u.id, u.username, u.display_name,
                   GROUP_CONCAT(r.name) AS role_names, GROUP_CONCAT(r.id) AS role_ids
            FROM users u
            JOIN user_roles ur ON u.id = ur.user_id
            JOIN roles r ON ur.role_id = r.id
            GROUP BY u.id, u.username, u.display_name
            ORDER BY u.username
        ''').fetchall()

        # Für die Anzeige im Frontend die Rollennamen als Liste pro Benutzer zusammenfassen
        users_data = []
        for user in users:
            user_dict = dict(user)
            # GROUP_CONCAT gibt einen String zurück, der in eine Liste umgewandelt werden muss
            user_dict['role_names'] = user_dict['role_names'].split(',') if user_dict['role_names'] else []
            user_dict['role_ids'] = [int(id) for id in user_dict['role_ids'].split(',')] if user_dict['role_ids'] else []
            users_data.append(user_dict)

        return jsonify({'success': True, 'users': users_data})

    elif request.method == 'POST':
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        display_name = data.get('display_name')
        role_ids = data.get('role_ids') # Erwarte eine Liste von Rollen-IDs

        if not all([username, password, display_name, role_ids]):
            return jsonify({'success': False, 'message': 'Benutzername, Passwort, Anzeigename und Rollen sind erforderlich.'}), 400

        if not isinstance(role_ids, list) or not all(isinstance(r, int) for r in role_ids):
            return jsonify({'success': False, 'message': 'Rollen-IDs müssen eine Liste von Ganzzahlen sein.'}), 400

        try:
            # Passwort wird hier NICHT gehasht, wie vom Benutzer gewünscht.
            cursor.execute("INSERT INTO users (username, password, display_name) VALUES (?, ?, ?)",
                           (username, password, display_name))
            user_id = cursor.lastrowid

            # Rollen für den Benutzer zuweisen
            for role_id in role_ids:
                cursor.execute("INSERT INTO user_roles (user_id, role_id) VALUES (?, ?)", (user_id, role_id))

            db.commit()
            return jsonify({'success': True, 'message': 'Benutzer erfolgreich hinzugefügt!'})
        except sqlite3.IntegrityError:
            db.rollback()
            return jsonify({'success': False, 'message': 'Benutzername existiert bereits.'}), 409
        except sqlite3.Error as e:
            db.rollback()
            return jsonify({'success': False, 'message': f'Fehler beim Hinzufügen des Benutzers: {e}'}), 500

    elif request.method == 'PUT':
        data = request.get_json()
        user_id = data.get('id')
        display_name = data.get('display_name')
        password = data.get('password') # Optionales Passwort-Update
        role_ids = data.get('role_ids')
        # 'is_active' wurde hier entfernt, da die Spalte nicht existiert.
        # Wenn Sie die 'is_active'-Funktion benötigen, müssen Sie die Datenbanktabelle anpassen.

        if not all([user_id, display_name, role_ids]): # 'is_active' aus der Prüfung entfernt
            return jsonify({'success': False, 'message': 'Benutzer-ID, Anzeigename und Rollen sind erforderlich.'}), 400

        if not isinstance(role_ids, list) or not all(isinstance(r, int) for r in role_ids):
            return jsonify({'success': False, 'message': 'Rollen-IDs müssen eine Liste von Ganzzahlen sein.'}), 400

        try:
            # Update des Benutzers
            update_fields = ['display_name = ?'] # 'is_active' aus den Update-Feldern entfernt
            update_values = [display_name]

            if password: # Wenn ein neues Passwort angegeben wurde
                update_fields.append('password = ?')
                update_values.append(password)

            update_query = f"UPDATE users SET {', '.join(update_fields)} WHERE id = ?"
            update_values.append(user_id) # user_id ist das letzte Element für die WHERE-Klausel
            cursor.execute(update_query, tuple(update_values))

            # Bestehende Rollen des Benutzers löschen
            cursor.execute("DELETE FROM user_roles WHERE user_id = ?", (user_id,))

            # Neue Rollen zuweisen
            for role_id in role_ids:
                cursor.execute("INSERT INTO user_roles (user_id, role_id) VALUES (?, ?)", (user_id, role_id))

            db.commit()
            return jsonify({'success': True, 'message': 'Benutzer erfolgreich aktualisiert!'})
        except sqlite3.IntegrityError:
            db.rollback()
            return jsonify({'success': False, 'message': 'Benutzername existiert bereits.'}), 409
        except sqlite3.Error as e:
            db.rollback()
            return jsonify({'success': False, 'message': f'Fehler beim Aktualisieren des Benutzers: {e}'}), 500

    elif request.method == 'DELETE':
        user_id = request.args.get('id')
        if not user_id:
            return jsonify({'success': False, 'message': 'Benutzer-ID ist erforderlich.'}), 400
        try:
            # Zuerst Rollenbeziehungen löschen
            cursor.execute("DELETE FROM user_roles WHERE user_id = ?", (user_id,))
            # Dann den Benutzer löschen
            cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
            db.commit()
            return jsonify({'success': True, 'message': 'Benutzer erfolgreich gelöscht!'})
        except sqlite3.Error as e:
            db.rollback()
            return jsonify({'success': False, 'message': f'Fehler beim Löschen des Benutzers: {e}'}), 500

@users_bp.route('/api/roles', methods=['GET'])
@role_required(['Administrator'])
def api_roles():
    """Gibt alle verfügbaren Rollen als JSON zurück."""
    db = get_db()
    cursor = db.cursor()
    roles = cursor.execute("SELECT id, name FROM roles ORDER BY name").fetchall()
    return jsonify({'success': True, 'roles': [dict(role) for role in roles]})

@users_bp.route('/api/users/<int:user_id>', methods=['GET'])
@role_required(['Administrator'])
def api_get_user(user_id):
    """Gibt die Daten eines einzelnen Benutzers zurück."""
    db = get_db()
    cursor = db.cursor()

    # Angepasste SQL-Abfrage: 'u.is_active' wurde entfernt
    user = cursor.execute('''
        SELECT u.id, u.username, u.display_name
        FROM users u
        WHERE u.id = ?
    ''', (user_id,)).fetchone()

    if user:
        user_dict = dict(user)
        # Rollen des Benutzers abrufen
        user_roles = cursor.execute('''
            SELECT role_id FROM user_roles WHERE user_id = ?
        ''', (user_id,)).fetchall()
        user_dict['role_ids'] = [r['role_id'] for r in user_roles]
        return jsonify({'success': True, 'user': user_dict})
    else:
        return jsonify({'success': False, 'message': 'Benutzer nicht gefunden.'}), 404
