import sqlite3
from flask import Blueprint, request, jsonify, current_app
from db import get_db, get_role_id
from decorators import role_required
import pandas as pd
import os
from werkzeug.utils import secure_filename

excel_uploads_bp = Blueprint('excel_uploads', __name__)

def allowed_file(filename):
    """Überprüft, ob die Dateierweiterung zulässig ist."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

@excel_uploads_bp.route('/upload_stands_excel', methods=['POST'])
@role_required(['Administrator'])
def upload_stands_excel():
    """Lädt eine Excel-Datei für Stände hoch und verarbeitet sie."""
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'Keine Datei gefunden.'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'Keine Datei ausgewählt.'}), 400
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        upload_folder = current_app.config['UPLOAD_FOLDER']
        
        # Sicherstellen, dass der Upload-Ordner existiert
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder) # Erstellt den Ordner, falls er nicht existiert
        
        filepath = os.path.join(upload_folder, filename)
        file.save(filepath)

        db = get_db()
        cursor = db.cursor()
        try:
            df = pd.read_excel(filepath)
            required_columns = ['Standname', 'Beschreibung', 'Raum'] 
            if not all(col in df.columns for col in required_columns):
                return jsonify({'success': False, 'message': f"Excel-Datei muss die Spalten enthalten: {', '.join(required_columns)}."}), 400

            stands_added = 0
            stands_updated = 0
            errors = []
            rooms_created = 0

            for index, row in df.iterrows():
                stand_name = str(row['Standname']).strip()
                stand_description = str(row['Beschreibung']).strip() if pd.notna(row['Beschreibung']) else ''
                room_name = str(row['Raum']).strip() if pd.notna(row['Raum']) else None

                room_id = None
                if room_name:
                    cursor.execute("SELECT id FROM rooms WHERE name = ?", (room_name,))
                    room = cursor.fetchone()
                    if room:
                        room_id = room['id']
                    else:
                        try:
                            cursor.execute("INSERT INTO rooms (name) VALUES (?)", (room_name,))
                            room_id = cursor.lastrowid
                            rooms_created += 1
                        except sqlite3.IntegrityError:
                            cursor.execute("SELECT id FROM rooms WHERE name = ?", (room_name,))
                            room = cursor.fetchone()
                            if room:
                                room_id = room['id']
                            else:
                                errors.append(f"Zeile {index+2}: Raum '{room_name}' für Stand '{stand_name}' konnte nicht erstellt oder gefunden werden.")
                                continue
                        except Exception as e:
                            errors.append(f"Zeile {index+2}: Fehler beim Erstellen von Raum '{room_name}' für Stand '{stand_name}': {e}.")
                            continue

                cursor.execute("SELECT id FROM stands WHERE name = ?", (stand_name,))
                existing_stand = cursor.fetchone()

                if existing_stand:
                    cursor.execute("UPDATE stands SET description = ?, room_id = ? WHERE id = ?",
                                   (stand_description, room_id, existing_stand['id']))
                    stands_updated += 1
                else:
                    cursor.execute("INSERT INTO stands (name, description, room_id) VALUES (?, ?, ?)",
                                   (stand_name, stand_description, room_id))
                    stands_added += 1
            db.commit()
            message = f"Stände erfolgreich importiert: {stands_added} hinzugefügt, {stands_updated} aktualisiert."
            if rooms_created > 0:
                message += f" {rooms_created} Räume wurden automatisch erstellt."
            if errors:
                message += " Fehler: " + "; ".join(errors)
                return jsonify({'success': False, 'message': message}), 400
            return jsonify({'success': True, 'message': message})

        except Exception as e:
            db.rollback()
            return jsonify({'success': False, 'message': f"Fehler beim Verarbeiten der Excel-Datei: {e}"}), 500
        finally:
            os.remove(filepath)
    return jsonify({'success': False, 'message': 'Ungültiger Dateityp.'}), 400

@excel_uploads_bp.route('/upload_users_excel', methods=['POST'])
@role_required(['Administrator'])
def upload_users_excel():
    """Lädt eine Excel-Datei für Benutzer hoch und verarbeitet sie."""
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'Keine Datei gefunden.'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'Keine Datei ausgewählt.'}), 400
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        upload_folder = current_app.config['UPLOAD_FOLDER']
        
        # Sicherstellen, dass der Upload-Ordner existiert
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
        
        filepath = os.path.join(upload_folder, filename)
        file.save(filepath)

        db = get_db()
        cursor = db.cursor()
        try:
            df = pd.read_excel(filepath)
            required_columns = ['Benutzername', 'Password', 'Anzeigename', 'Rollen']
            if not all(col in df.columns for col in required_columns):
                return jsonify({'success': False, 'message': f"Excel-Datei muss die Spalten enthalten: {', '.join(required_columns)}."}), 400

            users_added = 0
            users_updated = 0
            errors = []

            for index, row in df.iterrows():
                username = str(row['Benutzername']).strip()
                password = str(row['Password']).strip()
                display_name = str(row['Anzeigename']).strip() if pd.notna(row['Anzeigename']) else username
                roles_str = str(row['Rollen']).strip() if pd.notna(row['Rollen']) else ''
                
                if not username or not password or not roles_str:
                    errors.append(f"Zeile {index+2}: Benutzername, Passwort und Rollen sind für Benutzer '{username}' erforderlich. Benutzer nicht hinzugefügt/aktualisiert.")
                    continue

                role_names = [r.strip() for r in roles_str.split(',') if r.strip()]
                role_ids = []
                for role_name in role_names:
                    role_id = get_role_id(role_name)
                    if role_id:
                        role_ids.append(role_id)
                    else:
                        errors.append(f"Zeile {index+2}: Rolle '{role_name}' für Benutzer '{username}' nicht gefunden.")
                
                if not role_ids:
                    errors.append(f"Zeile {index+2}: Keine gültigen Rollen für Benutzer '{username}' gefunden. Benutzer nicht hinzugefügt/aktualisiert.")
                    continue

                cursor.execute("SELECT id, username FROM users WHERE username = ?", (username,))
                existing_user = cursor.fetchone()

                is_admin_flag = 0
                admin_role_id = get_role_id('Administrator')
                if admin_role_id in role_ids:
                    is_admin_flag = 1

                if existing_user:
                    if existing_user['username'] == 'admin':
                        if is_admin_flag == 0:
                            cursor.execute("SELECT COUNT(*) FROM user_roles ur JOIN roles r ON ur.role_id = r.id WHERE r.name = 'Administrator'")
                            num_admins = cursor.fetchone()[0]
                            if num_admins <= 1:
                                errors.append(f"Zeile {index+2}: 'admin' kann nicht aus der Administratorrolle entfernt werden, wenn es der einzige Administrator ist.")
                                continue
                        is_admin_flag = 1 
                        
                    cursor.execute("UPDATE users SET password = ?, display_name = ?, is_admin = ? WHERE id = ?",
                                   (password, display_name, is_admin_flag, existing_user['id']))
                    cursor.execute("DELETE FROM user_roles WHERE user_id = ?", (existing_user['id'],))
                    for role_id in role_ids:
                        cursor.execute("INSERT INTO user_roles (user_id, role_id) VALUES (?, ?)", (existing_user['id'], role_id))
                    users_updated += 1
                else:
                    cursor.execute("INSERT INTO users (username, password, display_name, is_admin) VALUES (?, ?, ?, ?)",
                                   (username, password, display_name, is_admin_flag))
                    new_user_id = cursor.lastrowid
                    for role_id in role_ids:
                        cursor.execute("INSERT INTO user_roles (user_id, role_id) VALUES (?, ?)", (new_user_id, role_id))
                    users_added += 1
            db.commit()
            message = f"Benutzer erfolgreich importiert: {users_added} hinzugefügt, {users_updated} aktualisiert."
            if errors:
                message += " Fehler: " + "; ".join(errors)
                return jsonify({'success': False, 'message': message}), 400
            return jsonify({'success': True, 'message': message})

        except Exception as e:
            db.rollback()
            return jsonify({'success': False, 'message': f"Fehler beim Verarbeiten der Excel-Datei: {e}"}), 500
        finally:
            os.remove(filepath)
    return jsonify({'success': False, 'message': 'Ungültiger Dateityp.'}), 400

@excel_uploads_bp.route('/upload_criteria_excel', methods=['POST'])
@role_required(['Administrator'])
def upload_criteria_excel():
    """Lädt eine Excel-Datei für Bewertungskriterien hoch und verarbeitet sie."""
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'Keine Datei gefunden.'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'Keine Datei ausgewählt.'}), 400
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        upload_folder = current_app.config['UPLOAD_FOLDER']
        
        # Sicherstellen, dass der Upload-Ordner existiert
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
        
        filepath = os.path.join(upload_folder, filename)
        file.save(filepath)

        db = get_db()
        cursor = db.cursor()
        try:
            df = pd.read_excel(filepath)
            required_columns = ['Name', 'Maximale Punktzahl', 'Beschreibung']
            if not all(col in df.columns for col in required_columns):
                return jsonify({'success': False, 'message': f"Excel-Datei muss die Spalten enthalten: {', '.join(required_columns)}."}), 400

            criteria_added = 0
            criteria_updated = 0
            errors = []

            for index, row in df.iterrows():
                criterion_name = str(row['Name']).strip()
                max_score = row['Maximale Punktzahl']
                criterion_description = str(row['Beschreibung']).strip() if pd.notna(row['Beschreibung']) else ''

                if not criterion_name or not pd.notna(max_score) or not isinstance(max_score, (int, float)):
                    errors.append(f"Zeile {index+2}: Name und eine gültige numerische Maximalpunktzahl sind für Kriterium '{criterion_name}' erforderlich. Kriterium nicht hinzugefügt/aktualisiert.")
                    continue
                
                max_score = int(max_score)

                cursor.execute("SELECT id FROM criteria WHERE name = ?", (criterion_name,))
                existing_criterion = cursor.fetchone()

                if existing_criterion:
                    cursor.execute("UPDATE criteria SET max_score = ?, description = ? WHERE id = ?",
                                   (max_score, criterion_description, existing_criterion['id']))
                    criteria_updated += 1
                else:
                    cursor.execute("INSERT INTO criteria (name, max_score, description) VALUES (?, ?, ?)",
                                   (criterion_name, max_score, criterion_description))
                    criteria_added += 1
            db.commit()
            message = f"Kriterien erfolgreich importiert: {criteria_added} hinzugefügt, {criteria_updated} aktualisiert."
            if errors:
                message += " Fehler: " + "; ".join(errors)
                return jsonify({'success': False, 'message': message}), 400
            return jsonify({'success': True, 'message': message})

        except Exception as e:
            db.rollback()
            return jsonify({'success': False, 'message': f"Fehler beim Verarbeiten der Excel-Datei: {e}"}), 500
        finally:
            os.remove(filepath)
    return jsonify({'success': False, 'message': 'Ungültiger Dateityp.'}), 400

