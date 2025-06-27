#!/bin/bash
# update_and_restart.sh
# Skript für Linux (Ubuntu), um die Flask-Anwendung zu aktualisieren und neu zu starten.

# Übergabeparameter:
# $1: Pfad zum entpackten neuen Quellcode (z.B. /path/to/app/temp_update/repo-name-commit)
# $2: Pfad zum aktuellen Anwendungsstammverzeichnis (z.B. /path/to/app)

NEW_APP_PATH="$1"
CURRENT_APP_ROOT="$2"
LOG_FILE="${CURRENT_APP_ROOT}/update_log.txt"

# Leere das Logfile für diesen Lauf
> "$LOG_FILE"
echo "--- Update-Skript gestartet: $(date) ---" >> "$LOG_FILE"
echo "Neuer App-Pfad: $NEW_APP_PATH" >> "$LOG_FILE"
echo "Aktueller App-Root: $CURRENT_APP_ROOT" >> "$LOG_FILE"

# Überprüfen, ob die Pfade übergeben wurden
if [ -z "$NEW_APP_PATH" ] || [ -z "$CURRENT_APP_ROOT" ]; then
    echo "Fehler: Beide Pfade (NEW_APP_PATH und CURRENT_APP_ROOT) müssen angegeben werden." >> "$LOG_FILE"
    exit 1
fi

# Optional: Flask-Dienst stoppen (ANPASSEN, falls du systemd, Gunicorn etc. verwendest)
# Beispiel für systemd:
echo "Versuche Flask-Dienst zu stoppen (falls systemd verwendet wird)..." >> "$LOG_FILE"
# Ersetze 'your_flask_app_service.service' durch den tatsächlichen Namen deines Systemd-Dienstes
sudo systemctl stop your_flask_app_service.service >> "$LOG_FILE" 2>&1 
# Wenn du Gunicorn direkt ausführst, müsstest du den Gunicorn-Prozess beenden.
# Beispiel: pkill gunicorn

# Warte kurz, um sicherzustellen, dass der Dienst beendet ist
sleep 5

# Alte Dateien sichern (optional, aber SEHR EMPFOHLEN)
BACKUP_DIR="${CURRENT_APP_ROOT}/_backup_$(date +%Y%m%d%H%M%S)"
echo "Erstelle Backup der aktuellen Anwendung in $BACKUP_DIR" >> "$LOG_FILE"
mkdir -p "$BACKUP_DIR" >> "$LOG_FILE" 2>&1
mv "${CURRENT_APP_ROOT}"/* "$BACKUP_DIR/" >> "$LOG_FILE" 2>&1 # Verschiebe alle Dateien außer dem Backup-Ordner selbst

# Neue Dateien kopieren
echo "Kopiere neue Dateien von $NEW_APP_PATH nach $CURRENT_APP_ROOT" >> "$LOG_FILE"
# Kopiert den Inhalt des entpackten Ordners
cp -R "${NEW_APP_PATH}"/* "$CURRENT_APP_ROOT/" >> "$LOG_FILE" 2>&1
cp -R "${NEW_APP_PATH}"/.[!.]* "$CURRENT_APP_ROOT/" >> "$LOG_FILE" 2>&1 # Kopiert versteckte Dateien

# Abhängigkeiten installieren (falls sich requirements.txt geändert hat)
echo "Installiere/aktualisiere Python-Abhängigkeiten..." >> "$LOG_FILE"
pip install -r "${CURRENT_APP_ROOT}/requirements.txt" >> "$LOG_FILE" 2>&1

# Datenbank-Migrationen werden beim Start der App (durch init_db() in app.py) automatisch durchgeführt.
echo "Datenbank-Migrationen werden beim nächsten Start der Anwendung ausgeführt." >> "$LOG_FILE"

# Temporären Update-Ordner aufräumen
echo "Entferne temporären Update-Ordner: $NEW_APP_PATH" >> "$LOG_FILE"
rm -rf "$NEW_APP_PATH" >> "$LOG_FILE" 2>&1

# Flask-Dienst starten (ANPASSEN, falls du systemd, Gunicorn etc. verwendest)
# Beispiel für systemd:
echo "Starte Flask-Dienst (falls systemd verwendet wird)..." >> "$LOG_FILE"
# Ersetze 'your_flask_app_service.service' durch den tatsächlichen Namen deines Systemd-Dienstes
sudo systemctl start your_flask_app_service.service >> "$LOG_FILE" 2>&1

# Wenn du deine Flask-App direkt mit `python app.py` startest:
# ACHTUNG: Dies ist für die Produktion NICHT empfohlen! Besser systemd/Gunicorn.
# echo "Starte Flask-Anwendung direkt mit python app.py..." >> "$LOG_FILE"
# nohup python "${CURRENT_APP_ROOT}/app.py" & >> "$LOG_FILE" 2>&1

echo "--- Update-Skript beendet: $(date) ---" >> "$LOG_FILE"

exit 0
