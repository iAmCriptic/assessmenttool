import sqlite3
import requests
import zipfile
import os
import shutil
import platform # NEU: Für die Erkennung des Betriebssystems
import subprocess # NEU: Zum Ausführen externer Skripte
from flask import Blueprint, request, jsonify, current_app, session
from decorators import role_required
from db import get_db
from config_version import GITHUB_REPO_OWNER, GITHUB_REPO_NAME, CURRENT_APP_VERSION # , GITHUB_TOKEN
# Importiere die Skriptpfade aus der Hauptkonfigurationsdatei
from config import Config


update_bp = Blueprint('update', __name__)

# Temporärer Ordner für Downloads und Entpacken
TEMP_UPDATE_DIR = os.path.join(os.getcwd(), 'temp_update')


@update_bp.route('/admin/check_for_updates', methods=['GET'])
@role_required(['Administrator'])
def check_for_updates():
    """
    Überprüft, ob eine neue Version der Anwendung auf GitHub verfügbar ist.
    Benötigt Administrator-Rolle.
    """
    if not GITHUB_REPO_OWNER or not GITHUB_REPO_NAME:
        return jsonify({'success': False, 'message': 'GitHub-Repository-Konfiguration fehlt. Bitte GITHUB_REPO_OWNER und GITHUB_REPO_NAME einstellen.'}), 500

    api_url = f"https://api.github.com/repos/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/releases/latest"
    
    headers = {}
    # if GITHUB_TOKEN:
    #     headers['Authorization'] = f'token {GITHUB_TOKEN}'

    try:
        response = requests.get(api_url, headers=headers)
        response.raise_for_status() # Löst HTTPError für schlechte Antworten (4xx oder 5xx) aus
        latest_release = response.json()

        latest_tag_name = latest_release.get('tag_name')
        
        # Annahme: Deine aktuelle Version ist fest oder wird aus einer Datei gelesen.
        # Für diese Demo nehmen wir an, die aktuelle Version ist "v1.0.0".
        # In einer echten Anwendung würdest du dies dynamisch aus einer Konfigurationsdatei lesen.
        current_version = CURRENT_APP_VERSION # Verwende die Version aus config_version.py

        # Überprüfe, ob die neueste Version neuer ist als die aktuelle
        # Eine einfache String- oder numerische Vergleichslogik kann hier implementiert werden.
        # Für einfache Versionen wie "v1.0.0" können wir Vergleiche basierend auf dem Tag-Namen durchführen.
        if latest_tag_name and latest_tag_name != current_version:
            # Hier könnten wir auch eine komplexere Versionsvergleichslogik einfügen,
            # um sicherzustellen, dass es sich um eine neuere Version handelt (z.B. semver).
            message = f"Neue Version ({latest_tag_name}) verfügbar! Aktuelle Version: {current_version}."
            return jsonify({
                'success': True,
                'new_version_available': True,
                'latest_version': latest_tag_name,
                'current_version': current_version,
                'download_url': latest_release['zipball_url'], # URL zum Download des gesamten Quellcodes als ZIP
                'message': message
            })
        else:
            message = f"Du verwendest bereits die neueste Version ({current_version})."
            return jsonify({
                'success': True,
                'new_version_available': False,
                'latest_version': latest_tag_name,
                'current_version': current_version,
                'message': message
            })

    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"Fehler beim Überprüfen von GitHub-Updates: {e}")
        return jsonify({'success': False, 'message': f'Fehler beim Zugriff auf GitHub: {e}'}), 500
    except Exception as e:
        current_app.logger.error(f"Unerwarteter Fehler beim Überprüfen von Updates: {e}")
        return jsonify({'success': False, 'message': f'Ein unerwarteter Fehler ist aufgetreten: {e}'}), 500


@update_bp.route('/admin/perform_update', methods=['POST'])
@role_required(['Administrator'])
def perform_update():
    """
    Führt das Herunterladen und Entpacken einer neuen Anwendungsversion durch.
    Anschließend wird ein externes Skript für den Dateiaustausch und den Neustart ausgelöst.
    Benötigt Administrator-Rolle.
    """
    data = request.get_json()
    download_url = data.get('download_url')
    latest_version = data.get('latest_version')

    if not download_url or not latest_version:
        return jsonify({'success': False, 'message': 'Download-URL oder Versionsinformationen fehlen.'}), 400

    # Sicherstellen, dass der temporäre Update-Ordner existiert und sauber ist
    if os.path.exists(TEMP_UPDATE_DIR):
        shutil.rmtree(TEMP_UPDATE_DIR) # Entfernt den Ordner und seinen Inhalt
    os.makedirs(TEMP_UPDATE_DIR)

    zip_filepath = os.path.join(TEMP_UPDATE_DIR, f'release_{latest_version}.zip')
    
    headers = {}
    # if GITHUB_TOKEN:
    #     headers['Authorization'] = f'token {GITHUB_TOKEN}'

    try:
        # 1. ZIP-Datei herunterladen
        current_app.logger.info(f"Lade Update von {download_url} herunter...")
        with requests.get(download_url, stream=True, headers=headers) as r:
            r.raise_for_status()
            with open(zip_filepath, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        current_app.logger.info(f"Update-Datei erfolgreich heruntergeladen nach {zip_filepath}")

        # 2. ZIP-Datei entpacken
        current_app.logger.info(f"Entpacke Update-Datei...")
        with zipfile.ZipFile(zip_filepath, 'r') as zip_ref:
            # GitHub-Zip-Dateien enthalten normalerweise einen Stammordner (z.B. repo-name-commit_hash)
            # Wir wollen den Inhalt DIESES Stammordners extrahieren.
            # Den ersten Eintrag im ZIP verwenden, um den Stammordnernamen zu finden.
            first_dir = next((m for m in zip_ref.namelist() if m.endswith('/')), None)
            if first_dir:
                zip_ref.extractall(TEMP_UPDATE_DIR)
                extracted_content_path = os.path.join(TEMP_UPDATE_DIR, first_dir)
                current_app.logger.info(f"Inhalt entpackt nach: {extracted_content_path}")
            else:
                raise Exception("Konnte den Stammordner in der ZIP-Datei nicht finden.")

        # Bestimme das Betriebssystem und rufe das entsprechende Skript auf
        current_os = platform.system()
        app_root_dir = os.getcwd() # Der Stammordner deiner Flask-Anwendung

        # Parameter, die an das Skript übergeben werden
        # extracted_content_path: Der Pfad zum entpackten Quellcode
        # app_root_dir: Der Pfad zum aktuellen Anwendungsstammverzeichnis
        script_args = [extracted_content_path, app_root_dir]

        if current_os == 'Linux':
            script_path = current_app.config['LINUX_UPDATE_SCRIPT']
            # Stelle sicher, dass das Skript ausführbar ist
            if not os.access(script_path, os.X_OK):
                os.chmod(script_path, 0o755) # Füge Ausführungsrechte hinzu
            
            current_app.logger.info(f"Starte Linux Update-Skript: {script_path} {script_args[0]} {script_args[1]}")
            # Ausführen des Skripts im Hintergrund (ohne auf Beendigung zu warten)
            # ACHTUNG: 'nohup' und '&' sind LINUX-spezifisch.
            # Für eine robustere Lösung in der Produktion wird ein Systemdienst (systemd, Supervisor) empfohlen.
            subprocess.Popen(['nohup', 'bash', script_path] + script_args, 
                             stdout=subprocess.DEVNULL, 
                             stderr=subprocess.DEVNULL, 
                             preexec_fn=os.setpgrp)
            
            message = f"Update ({latest_version}) erfolgreich heruntergeladen und entpackt. Das Linux-Update-Skript wird im Hintergrund ausgeführt, um die Anwendung neu zu starten."
            return jsonify({'success': True, 'message': message, 'restart_triggered': True})

        elif current_os == 'Windows':
            script_path = current_app.config['WINDOWS_UPDATE_SCRIPT']
            current_app.logger.info(f"Starte Windows Update-Skript: {script_path} {script_args[0]} {script_args[1]}")
            # Ausführen des Skripts im Hintergrund für Windows
            # 'start ""' ist wichtig, um ein neues Konsolenfenster zu öffnen und das Python-Programm nicht zu blockieren.
            subprocess.Popen(['start', '', 'cmd', '/c', script_path] + script_args, 
                             shell=True, 
                             stdout=subprocess.DEVNULL, 
                             stderr=subprocess.DEVNULL)
            
            message = f"Update ({latest_version}) erfolgreich heruntergeladen und entpackt. Das Windows-Update-Skript wird im Hintergrund ausgeführt, um die Anwendung neu zu starten."
            return jsonify({'success': True, 'message': message, 'restart_triggered': True})

        else:
            message = f"Update ({latest_version}) erfolgreich heruntergeladen und entpackt nach '{extracted_content_path}'.\n" \
                      f"Automatische Aktualisierung für Betriebssystem '{current_os}' nicht unterstützt. Bitte ersetzen Sie die alten Anwendungsdateien manuell und starten Sie die Anwendung neu."
            return jsonify({'success': True, 'message': message, 'extracted_path': extracted_content_path, 'restart_triggered': False})

    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"Fehler beim Herunterladen des Updates: {e}")
        return jsonify({'success': False, 'message': f'Fehler beim Herunterladen der Update-Datei: {e}'}), 500
    except zipfile.BadZipFile as e:
        current_app.logger.error(f"Ungültige ZIP-Datei: {e}")
        return jsonify({'success': False, 'message': f'Die heruntergeladene Datei ist keine gültige ZIP-Datei: {e}'}), 500
    except Exception as e:
        db.rollback() # Sicherstellen, dass Transaktionen zurückgerollt werden, falls ein Fehler auftritt
        current_app.logger.error(f"Unerwarteter Fehler während des Update-Vorgangs: {e}")
        return jsonify({'success': False, 'message': f'Ein unerwarteter Fehler ist aufgetreten: {e}'}), 500
    finally:
        # Cleanup: ZIP-Datei nach dem Entpacken entfernen (Skript sollte sie nicht mehr benötigen)
        if os.path.exists(zip_filepath):
            os.remove(zip_filepath)

