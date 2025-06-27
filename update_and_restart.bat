@echo off
REM update_and_restart.bat
REM Skript für Windows, um die Flask-Anwendung zu aktualisieren und neu zu starten.

REM Übergabeparameter:
REM %1: Pfad zum entpackten neuen Quellcode (z.B. C:\path\to\app\temp_update\repo-name-commit)
REM %2: Pfad zum aktuellen Anwendungsstammverzeichnis (z.B. C:\path\to\app)

SET NEW_APP_PATH=%1
SET CURRENT_APP_ROOT=%2
SET LOG_FILE=%CURRENT_APP_ROOT%\update_log.txt

REM Leere das Logfile für diesen Lauf
ECHO. > "%LOG_FILE%"
ECHO --- Update-Skript gestartet: %DATE% %TIME% --- >> "%LOG_FILE%"
ECHO Neuer App-Pfad: %NEW_APP_PATH% >> "%LOG_FILE%"
ECHO Aktueller App-Root: %CURRENT_APP_ROOT% >> "%LOG_FILE%"

REM Warte kurz, um sicherzustellen, dass die Flask-Antwort gesendet werden kann
ECHO Warte 5 Sekunden, bevor der Update-Prozess beginnt... >> "%LOG_FILE%"
ping -n 6 127.0.0.1 >nul

IF "%NEW_APP_PATH%"=="" (
    ECHO Fehler: Erster Parameter (NEW_APP_PATH) fehlt. >> "%LOG_FILE%"
    EXIT /b 1
)
IF "%CURRENT_APP_ROOT%"=="" (
    ECHO Fehler: Zweiter Parameter (CURRENT_APP_ROOT) fehlt. >> "%LOG_FILE%"
    EXIT /b 1
)

REM Bestimme den Pfad zum Python-Interpreter und Pip
SET PYTHON_EXE="%CURRENT_APP_ROOT%\venv\Scripts\python.exe"
SET PIP_EXE="%CURRENT_APP_ROOT%\venv\Scripts\pip.exe"

IF NOT EXIST %PYTHON_EXE% (
    SET PYTHON_EXE=python.exe
    ECHO Info: venv Python nicht gefunden, verwende System-Python. >> "%LOG_FILE%"
)
IF NOT EXIST %PIP_EXE% (
    SET PIP_EXE=pip.exe
    ECHO Info: venv Pip nicht gefunden, verwende System-Pip. >> "%LOG_FILE%"
)


REM Optional: Flask-Dienst stoppen (ANPASSEN, falls du z.B. NSSM oder Task Scheduler verwendest)
ECHO Versuche Flask-Prozesse zu beenden... >> "%LOG_FILE%"
REM Versuche, alle Python-Prozesse zu beenden
taskkill /F /IM python.exe >> "%LOG_FILE%" 2>&1
IF %ERRORLEVEL% NEQ 0 (
    ECHO Warnung: Es gab Probleme beim Beenden der Python-Prozesse oder es wurden keine gefunden. >> "%LOG_FILE%"
)

REM Wenn du deine Flask-App z.B. mit 'flask run' startest oder Gunicorn/uWSGI:
REM taskkill /F /IM flask.exe >> "%LOG_FILE%" 2>&1
REM taskkill /F /IM gunicorn.exe >> "%LOG_FILE%" 2>&1
REM Oder wenn du einen Windows-Dienst eingerichtet hast (empfohlen für Produktion):
REM sc stop YourFlaskService >> "%LOG_FILE%" 2>&1

ECHO Warte 5 Sekunden, um sicherzustellen, dass die Prozesse beendet sind... >> "%LOG_FILE%"
TIMEOUT /T 5 /NOBREAK

REM PAUSE REM FÜR DEBUGGING: Entferne dies, wenn das Skript funktioniert
ECHO. >> "%LOG_FILE%"
ECHO Schritt: Alte Dateien sichern >> "%LOG_FILE%"
REM Alte Dateien sichern (optional, aber SEHR EMPFOHLEN)
FOR /f "tokens=2-4 delims=/ " %%a in ('date /t') do (set mydate=%%c%%a%%b)
FOR /f "tokens=1-2 delims=:" %%a in ('time /t') do (set mytime=%%a%%b)
SET BACKUP_DIR=%CURRENT_APP_ROOT%\_backup_%mydate%%mytime%
ECHO Erstelle Backup-Verzeichnis: "%BACKUP_DIR%" >> "%LOG_FILE%"
mkdir "%BACKUP_DIR%" >> "%LOG_FILE%" 2>&1
IF %ERRORLEVEL% NEQ 0 (ECHO Fehler beim Erstellen des Backup-Verzeichnisses. >> "%LOG_FILE%")

REM Verschiebe alle Dateien und Ordner außer dem Backup-Ordner selbst
ECHO Verschiebe alte Dateien und Ordner nach Backup-Verzeichnis... >> "%LOG_FILE%"
FOR /D %%D IN ("%CURRENT_APP_ROOT%\*") DO (
    IF NOT "%%D"=="%BACKUP_DIR%" (
        ECHO Verschiebe Ordner: "%%D" >> "%LOG_FILE%"
        MOVE /Y "%%D" "%BACKUP_DIR%\" >> "%LOG_FILE%" 2>&1
    )
)
FOR %%F IN ("%CURRENT_APP_ROOT%\*.*") DO (
    IF NOT "%%F"=="%BACKUP_DIR%" (
        ECHO Verschiebe Datei: "%%F" >> "%LOG_FILE%"
        MOVE /Y "%%F" "%BACKUP_DIR%\" >> "%LOG_FILE%" 2>&1
    )
)
ECHO Alte Dateien verschoben. >> "%LOG_FILE%"
IF %ERRORLEVEL% NEQ 0 (ECHO Fehler beim Verschieben alter Dateien. >> "%LOG_FILE%")

REM PAUSE REM FÜR DEBUGGING: Entferne dies, wenn das Skript funktioniert
ECHO. >> "%LOG_FILE%"
ECHO Schritt: Neue Dateien kopieren >> "%LOG_FILE%"
REM Neue Dateien kopieren
ECHO Kopiere neue Dateien von "%NEW_APP_PATH%" nach "%CURRENT_APP_ROOT%" >> "%LOG_FILE%"
xcopy "%NEW_APP_PATH%"\* "%CURRENT_APP_ROOT%\" /E /I /Y >> "%LOG_FILE%" 2>&1
IF %ERRORLEVEL% NEQ 0 (
    ECHO Fehler beim Kopieren der neuen Dateien. >> "%LOG_FILE%"
    EXIT /b 1
)
ECHO Neue Dateien kopiert. >> "%LOG_FILE%"

REM PAUSE REM FÜR DEBUGGING: Entferne dies, wenn das Skript funktioniert
ECHO. >> "%LOG_FILE%"
ECHO Schritt: Abhaengigkeiten installieren >> "%LOG_FILE%"
REM Abhängigkeiten installieren (falls sich requirements.txt geändert hat)
ECHO Installiere/aktualisiere Python-Abhängigkeiten mit Pip... >> "%LOG_FILE%"
%PIP_EXE% install -r "%CURRENT_APP_ROOT%\requirements.txt" >> "%LOG_FILE%" 2>&1
IF %ERRORLEVEL% NEQ 0 (
    ECHO Fehler beim Installieren der Python-Abhaengigkeiten. >> "%LOG_FILE%"
    REM Optional: Rollback durchführen oder den Benutzer benachrichtigen
)
ECHO Python-Abhaengigkeiten installiert. >> "%LOG_FILE%"

REM Datenbank-Migrationen werden beim Start der App (durch init_db() in app.py) automatisch durchgeführt.
ECHO Datenbank-Migrationen werden beim naechsten Start der Anwendung ausgefuehrt. >> "%LOG_FILE%"

REM PAUSE REM FÜR DEBUGGING: Entferne dies, wenn das Skript funktioniert
ECHO. >> "%LOG_FILE%"
ECHO Schritt: Temporaeren Update-Ordner aufraeumen >> "%LOG_FILE%"
REM Temporären Update-Ordner aufräumen
ECHO Entferne temporaeren Update-Ordner: "%NEW_APP_PATH%" >> "%LOG_FILE%"
rmdir /s /q "%NEW_APP_PATH%" >> "%LOG_FILE%" 2>&1
ECHO Temporaeren Update-Ordner entfernt. >> "%LOG_FILE%"

REM PAUSE REM FÜR DEBUGGING: Entferne dies, wenn das Skript funktioniert
ECHO. >> "%LOG_FILE%"
ECHO Schritt: Flask-Dienst starten >> "%LOG_FILE%"
REM Flask-Dienst starten (ANPASSEN, falls du deine App als Dienst oder direkt ausführst)
ECHO Starte Flask-Anwendung... >> "%LOG_FILE%"
REM Dies startet die App und öffnet ein neues Konsolenfenster.
REM Wir verwenden hier %PYTHON_EXE% um sicherzustellen, dass das richtige Python verwendet wird.
start "" %PYTHON_EXE% "%CURRENT_APP_ROOT%\app.py" >> "%LOG_FILE%" 2>&1
IF %ERRORLEVEL% NEQ 0 (
    ECHO Fehler beim Starten der Flask-Anwendung. >> "%LOG_FILE%"
)

ECHO --- Update-Skript beendet: %DATE% %TIME% --- >> "%LOG_FILE%"

REM PAUSE REM FÜR DEBUGGING: Entferne dies, wenn das Skript funktioniert
EXIT /b 0
