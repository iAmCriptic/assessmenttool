import sqlite3
import os
from flask import Blueprint, render_template, request, jsonify, send_from_directory, current_app, session, flash, url_for
from werkzeug.utils import secure_filename
from decorators import role_required
from db import get_db

map_bp = Blueprint('map', __name__)

# Konfiguration für Uploads
# Stellen Sie sicher, dass dieser Ordner existiert oder erstellen Sie ihn.
UPLOAD_FOLDER = 'static/uploaded_floor_plans'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    """Überprüft, ob die Dateiendung erlaubt ist."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Route zum Verwalten des Lageplans
@map_bp.route('/manage_plan')
@role_required(['Administrator'])
def manage_plan_page():
    """Zeigt die Seite zur Verwaltung des Lageplans an."""
    dark_mode_enabled = session.get('dark_mode_enabled', False)
    return render_template('manage_plan.html', dark_mode_enabled=dark_mode_enabled)

# API-Route zum Hochladen eines Lageplans
@map_bp.route('/api/upload_floor_plan', methods=['POST'])
@role_required(['Administrator'])
def upload_floor_plan():
    """
    Empfängt den Upload eines Lageplans, speichert ihn und legt einen Eintrag in der Datenbank an.
    Setzt den hochgeladenen Plan automatisch als aktiv.
    """
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'Keine Datei im Request.'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'Keine Datei ausgewählt.'}), 400
    if file and allowed_file(file.filename):
        try:
            # Erstelle den Upload-Ordner, falls er nicht existiert
            upload_path = os.path.join(current_app.root_path, UPLOAD_FOLDER)
            os.makedirs(upload_path, exist_ok=True)

            filename = secure_filename(file.filename)
            file_path = os.path.join(upload_path, filename)
            
            # Speichere die Datei
            file.save(file_path)

            db = get_db()
            cursor = db.cursor()

            # Überprüfen, ob ein Plan mit diesem Namen bereits existiert
            existing_plan = cursor.execute("SELECT id FROM floor_plans WHERE name = ?", (filename,)).fetchone()

            # Deaktiviere alle anderen Pläne
            cursor.execute("UPDATE floor_plans SET is_active = 0")

            image_db_path = os.path.join(UPLOAD_FOLDER, filename).replace('\\', '/') # Korrigiere Pfad für DB

            if existing_plan:
                # Aktualisiere den vorhandenen Plan und setze ihn als aktiv
                cursor.execute("""
                    UPDATE floor_plans SET image_path = ?, is_active = 1,
                    width_px = NULL, height_px = NULL,
                    scale_point1_x = NULL, scale_point1_y = NULL,
                    scale_point2_x = NULL, scale_point2_y = NULL,
                    scale_distance_meters = NULL
                    WHERE id = ?
                """, (image_db_path, existing_plan['id']))
                new_plan_id = existing_plan['id']
                message = 'Lageplan erfolgreich aktualisiert und als aktiv gesetzt.'
                # Lösche bestehende Objekte dieses Plans, da der Plan neu hochgeladen wurde
                cursor.execute("DELETE FROM floor_plan_objects WHERE plan_id = ?", (new_plan_id,))
            else:
                # Füge neuen Plan hinzu und setze ihn als aktiv
                cursor.execute("""
                    INSERT INTO floor_plans (name, image_path, is_active)
                    VALUES (?, ?, 1)
                """, (filename, image_db_path))
                new_plan_id = cursor.lastrowid
                message = 'Lageplan erfolgreich hochgeladen und als aktiv gesetzt.'
            
            db.commit()

            return jsonify({
                'success': True,
                'message': message,
                'plan': {
                    'id': new_plan_id,
                    'name': filename,
                    'image_path': image_db_path, # Sende den DB-Pfad, url_for wird im Frontend verwendet
                    'image_url': url_for('map.serve_uploaded_plans', filename=filename), # Füge die tatsächliche URL hinzu
                    'is_active': 1
                }
            }), 200
        except sqlite3.Error as e:
            db.rollback()
            return jsonify({'success': False, 'message': f'Datenbankfehler: {e}'}), 500
        except Exception as e:
            return jsonify({'success': False, 'message': f'Fehler beim Speichern der Datei: {e}'}), 500
    else:
        return jsonify({'success': False, 'message': 'Dateityp nicht erlaubt.'}), 400

# API-Route zum Setzen eines Plans als aktiv
@map_bp.route('/api/set_active_plan', methods=['POST'])
@role_required(['Administrator'])
def set_active_plan():
    """Setzt einen vorhandenen Lageplan als aktiv."""
    data = request.get_json()
    plan_id = data.get('plan_id')

    if not plan_id:
        return jsonify({'success': False, 'message': 'Plan-ID fehlt.'}), 400

    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("UPDATE floor_plans SET is_active = 0") # Alle anderen deaktivieren
        cursor.execute("UPDATE floor_plans SET is_active = 1 WHERE id = ?", (plan_id,))
        db.commit()
        if cursor.rowcount > 0:
            return jsonify({'success': True, 'message': 'Lageplan erfolgreich als aktiv gesetzt.'}), 200
        else:
            return jsonify({'success': False, 'message': 'Lageplan nicht gefunden.'}), 404
    except sqlite3.Error as e:
        db.rollback()
        return jsonify({'success': False, 'message': f'Datenbankfehler: {e}'}), 500

# API-Route zum Abrufen des aktiven Lageplans und seiner Objekte
@map_bp.route('/api/get_active_plan', methods=['GET'])
@role_required(['Administrator', 'Bewerter', 'Betrachter', 'Inspektor', 'Verwarner'])
def get_active_plan():
    """Gibt Details des aktiven Lageplans und seine Objekte zurück."""
    db = get_db()
    cursor = db.cursor()
    try:
        plan = cursor.execute("SELECT * FROM floor_plans WHERE is_active = 1").fetchone()
        if plan:
            plan_data = dict(plan)
            # Konvertiere image_path zu einer URL, die der Browser aufrufen kann
            plan_data['image_url'] = url_for('map.serve_uploaded_plans', filename=os.path.basename(plan_data['image_path']))

            # Hole alle Objekte für diesen Plan, einschließlich stand_name und custom_stand_name
            objects_raw = cursor.execute("""
                SELECT fpo.*, s.name as stand_name FROM floor_plan_objects fpo
                LEFT JOIN stands s ON fpo.stand_id = s.id
                WHERE fpo.plan_id = ?
            """, (plan_data['id'],)).fetchall()
            
            plan_objects = [dict(obj) for obj in objects_raw]
            
            # Hole alle Stände für die Stand-Auswahl in der Toolbox
            stands = cursor.execute("SELECT id, name FROM stands").fetchall()
            stands_data = [dict(stand) for stand in stands]

            return jsonify({
                'success': True,
                'plan': plan_data,
                'objects': plan_objects,
                'available_stands': stands_data
            }), 200
        else:
            return jsonify({'success': False, 'message': 'Kein aktiver Lageplan gefunden.'}), 404
    except sqlite3.Error as e:
        return jsonify({'success': False, 'message': f'Datenbankfehler: {e}'}), 500

# API-Route zum Speichern/Aktualisieren eines Lageplanobjekts
@map_bp.route('/api/save_floor_plan_object', methods=['POST'])
@role_required(['Administrator'])
def save_floor_plan_object():
    """Speichert oder aktualisiert ein Lageplanobjekt."""
    data = request.get_json()
    object_id = data.get('id')
    plan_id = data.get('plan_id')
    obj_type = data.get('type')
    x = data.get('x')
    y = data.get('y')
    width = data.get('width')
    height = data.get('height')
    color = data.get('color')
    trash_can_color = data.get('trash_can_color')
    power_outlet_label = data.get('power_outlet_label')
    stand_id = data.get('stand_id')
    custom_stand_name = data.get('custom_stand_name') # NEU: Benutzerdefinierten Namen erhalten

    if not all([plan_id, obj_type, x, y]):
        return jsonify({'success': False, 'message': 'Fehlende Daten für das Objekt.'}), 400

    db = get_db()
    cursor = db.cursor()
    try:
        if object_id:
            # Bestehendes Objekt aktualisieren
            cursor.execute("""
                UPDATE floor_plan_objects
                SET plan_id = ?, type = ?, x = ?, y = ?, width = ?, height = ?,
                    color = ?, trash_can_color = ?, power_outlet_label = ?, stand_id = ?,
                    custom_stand_name = ? -- NEU: custom_stand_name aktualisieren
                WHERE id = ?
            """, (plan_id, obj_type, x, y, width, height, color, trash_can_color, power_outlet_label, stand_id,
                  custom_stand_name, object_id)) # custom_stand_name hier hinzufügen
            message = 'Objekt erfolgreich aktualisiert.'
        else:
            # Neues Objekt einfügen
            cursor.execute("""
                INSERT INTO floor_plan_objects (plan_id, type, x, y, width, height, color, trash_can_color, power_outlet_label, stand_id, custom_stand_name)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (plan_id, obj_type, x, y, width, height, color, trash_can_color, power_outlet_label, stand_id, custom_stand_name)) # custom_stand_name hier hinzufügen
            object_id = cursor.lastrowid
            message = 'Objekt erfolgreich hinzugefügt.'
        db.commit()
        return jsonify({'success': True, 'message': message, 'object_id': object_id}), 200
    except sqlite3.Error as e:
        db.rollback()
        return jsonify({'success': False, 'message': f'Datenbankfehler: {e}'}), 500

# API-Route zum Löschen eines Lageplanobjekts
@map_bp.route('/api/delete_floor_plan_object/<int:object_id>', methods=['DELETE'])
@role_required(['Administrator'])
def delete_floor_plan_object(object_id):
    """Löscht ein Lageplanobjekt."""
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("DELETE FROM floor_plan_objects WHERE id = ?", (object_id,))
        db.commit()
        if cursor.rowcount > 0:
            return jsonify({'success': True, 'message': 'Objekt erfolgreich gelöscht.'}), 200
        else:
            return jsonify({'success': False, 'message': 'Objekt nicht gefunden.'}), 404
    except sqlite3.Error as e:
        db.rollback()
        return jsonify({'success': False, 'message': f'Datenbankfehler: {e}'}), 500

# API-Route zum Aktualisieren der Skalierungspunkte eines Plans
@map_bp.route('/api/update_plan_scale', methods=['POST'])
@role_required(['Administrator'])
def update_plan_scale():
    """Aktualisiert die Skalierungspunkte und die gemessene Distanz für den aktiven Plan."""
    data = request.get_json()
    plan_id = data.get('plan_id')
    scale_point1_x = data.get('scale_point1_x')
    scale_point1_y = data.get('scale_point1_y')
    scale_point2_x = data.get('scale_point2_x')
    scale_point2_y = data.get('scale_point2_y')
    scale_distance_meters = data.get('scale_distance_meters')
    width_px = data.get('width_px')
    height_px = data.get('height_px')

    if not all([plan_id, scale_point1_x, scale_point1_y, scale_point2_x, scale_point2_y, scale_distance_meters, width_px, height_px]):
        return jsonify({'success': False, 'message': 'Fehlende Skalierungsdaten.'}), 400

    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("""
            UPDATE floor_plans
            SET scale_point1_x = ?, scale_point1_y = ?, scale_point2_x = ?, scale_point2_y = ?,
                scale_distance_meters = ?, width_px = ?, height_px = ?
            WHERE id = ?
        """, (scale_point1_x, scale_point1_y, scale_point2_x, scale_point2_y,
              scale_distance_meters, width_px, height_px, plan_id))
        db.commit()
        if cursor.rowcount > 0:
            return jsonify({'success': True, 'message': 'Skalierungsdaten erfolgreich aktualisiert.'}), 200
        else:
            return jsonify({'success': False, 'message': 'Plan nicht gefunden.'}), 404
    except sqlite3.Error as e:
        db.rollback()
        return jsonify({'success': False, 'message': f'Datenbankfehler: {e}'}), 500

# Route zum Bereitstellen der hochgeladenen Lagepläne
@map_bp.route(f'/{UPLOAD_FOLDER}/<filename>')
def serve_uploaded_plans(filename):
    """Stellt die hochgeladenen Lageplanbilder bereit."""
    return send_from_directory(os.path.join(current_app.root_path, UPLOAD_FOLDER), filename)
