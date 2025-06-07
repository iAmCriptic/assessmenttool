import sqlite3
from flask import Blueprint, request, jsonify, url_for, current_app, session, render_template # render_template hinzugefügt
from db import get_db
from decorators import role_required
import os
from werkzeug.utils import secure_filename

admin_settings_bp = Blueprint('admin_settings', __name__)

@admin_settings_bp.route('/admin_settings')
@role_required(['Administrator'])
def admin_settings_page():
    """Rendert die Admin-Einstellungen-Seite."""
    return render_template('admin_settings.html', dark_mode_enabled=session.get('dark_mode_enabled'))


@admin_settings_bp.route('/api/admin_settings', methods=['GET'])
# KEIN @role_required hier, da diese API auch für die Login-Seite benötigt wird, um Einstellungen zu laden
def api_get_admin_settings():
    """Gibt die aktuellen Anwendungseinstellungen als JSON zurück."""
    db = get_db()
    cursor = db.cursor()
    settings = cursor.execute("SELECT setting_key, setting_value FROM app_settings").fetchall()
    settings_dict = {s['setting_key']: s['setting_value'] for s in settings}
    
    # Vollständige URL für logo_path hier konstruieren, innerhalb eines Request-Kontextes
    if 'logo_path' in settings_dict and settings_dict['logo_path']:
        # KORREKTUR: Verwenden Sie 'general.static_files' für den Blueprint-Zugriff
        settings_dict['logo_url'] = url_for('general.static_files', filename=settings_dict['logo_path'])
    else:
        # Fallback-Logo-URL, falls kein Logo-Pfad in den Einstellungen vorhanden ist
        settings_dict['logo_url'] = url_for('general.static_files', filename='img/logo_V2.png')


    return jsonify({'success': True, 'settings': settings_dict})

@admin_settings_bp.route('/api/admin_settings', methods=['POST'])
@role_required(['Administrator']) # Dies bleibt auf Admin beschränkt, um Einstellungen zu speichern
def api_save_admin_settings():
    """Speichert Anwendungseinstellungen."""
    db = get_db()
    cursor = db.cursor()
    data = request.get_json()

    try:
        # Einstellungen aktualisieren oder einfügen
        for key, value in data.items():
            cursor.execute("INSERT OR REPLACE INTO app_settings (setting_key, setting_value) VALUES (?, ?)", (key, value))
        db.commit()
        return jsonify({'success': True, 'message': 'Einstellungen erfolgreich gespeichert!'})
    except sqlite3.Error as e:
        db.rollback()
        return jsonify({'success': False, 'message': f'Fehler beim Speichern der Einstellungen: {e}'}), 500

@admin_settings_bp.route('/api/upload_logo', methods=['POST'])
@role_required(['Administrator'])
def api_upload_logo():
    """Verarbeitet den Logo-Dateiupload und aktualisiert die logo_path-Einstellung."""
    if 'logo_file' not in request.files:
        return jsonify({'success': False, 'message': 'Keine Datei gefunden.'}), 400
    file = request.files['logo_file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'Keine Datei ausgewählt.'}), 400
    
    # Überprüfen, ob die Dateierweiterung für Bilder zulässig ist
    allowed_image_extensions = {'png', 'jpg', 'jpeg', 'gif', 'svg'}
    if '.' in file.filename and file.filename.rsplit('.', 1)[1].lower() in allowed_image_extensions:
        filename = secure_filename(file.filename)
        # Logo in einem spezifischen 'img'-Unterordner innerhalb von 'static' speichern
        logo_dir = os.path.join(current_app.root_path, 'static', 'img')
        if not os.path.exists(logo_dir):
            os.makedirs(logo_dir)
        filepath = os.path.join(logo_dir, filename)
        file.save(filepath)

        # logo_path in app_settings aktualisieren. Relativen Pfad speichern.
        db = get_db()
        cursor = db.cursor()
        try:
            # Relativen Pfad in der Datenbank speichern
            relative_logo_path = f'img/{filename}'
            cursor.execute("INSERT OR REPLACE INTO app_settings (setting_key, setting_value) VALUES (?, ?)", ('logo_path', relative_logo_path))
            db.commit()
            # Die vollständige URL für die sofortige Verwendung im Frontend zurückgeben
            # KORREKTUR: Verwenden Sie 'general.static_files' für den Blueprint-Zugriff
            full_logo_url = url_for('general.static_files', filename=relative_logo_path)
            return jsonify({'success': True, 'message': 'Logo erfolgreich hochgeladen und aktualisiert!', 'logo_url': full_logo_url})
        except sqlite3.Error as e:
            db.rollback()
            return jsonify({'success': False, 'message': f'Fehler beim Speichern des Logos: {e}'}), 500
    else:
        return jsonify({'success': False, 'message': 'Ungültiger Dateityp. Nur PNG, JPG, JPEG, GIF, SVG erlaubt.'}), 400
