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

IF "%NEW_APP_PATH%"=="" (
    ECHO Fehler: Beide Pfade (NEW_APP_PATH und CURRENT_APP_ROOT) müssen angegeben werden. >> "%LOG_FILE%"
    EXIT /b 1
)
IF "%CURRENT_APP_ROOT%"=="" (
    ECHO Fehler: Beide Pfade (NEW_APP_PATH und CURRENT_APP_ROOT) müssen angegeben werden. >> "%LOG_FILE%"
    EXIT /b 1
)

REM Optional: Flask-Dienst stoppen (ANPASSEN, falls du z.B. NSSM oder Task Scheduler verwendest)
REM Beispiel: taskkill /F /IM python.exe (oder den Namen deines Dienstprozesses)
REM Hier ist es schwieriger, den *richtigen* Flask-Prozess zu finden und zu beenden,
REM ohne andere Python-Programme zu beeinflussen.
REM Idealerweise beendest du den Dienst, der deine Flask-App hostet.
ECHO Versuche Flask-Prozesse zu beenden... >> "%LOG_FILE%"
REM Dies ist eine aggressive Methode und könnte andere Python-Programme beenden!
REM Besser ist es, den spezifischen Prozessnamen oder Dienstnamen zu kennen.
taskkill /F /IM python.exe /FI "WINDOWTITLE eq your_flask_app_title" >> "%LOG_FILE%" 2>&1
REM oder, wenn du einen Dienst hast: sc stop YourFlaskService
TIMEOUT /T 5 /NOBREAK

REM Alte Dateien sichern (optional, aber SEHR EMPFOHLEN)
FOR /f "tokens=2-4 delims=/ " %%a in ('date /t') do (set mydate=%%c%%a%%b)
FOR /f "tokens=1-2 delims=:" %%a in ('time /t') do (set mytime=%%a%%b)
SET BACKUP_DIR=%CURRENT_APP_ROOT%\_backup_%mydate%%mytime%
ECHO Erstelle Backup der aktuellen Anwendung in %BACKUP_DIR% >> "%LOG_FILE%"
mkdir "%BACKUP_DIR%" >> "%LOG_FILE%" 2>&1
REM Verschiebe alle Dateien und Ordner außer dem Backup-Ordner selbst
FOR /D %%D IN ("%CURRENT_APP_ROOT%\*") DO IF NOT "%%D"=="%BACKUP_DIR%" (MOVE "%%D" "%BACKUP_DIR%\" >> "%LOG_FILE%" 2>&1)
FOR %%F IN ("%CURRENT_APP_ROOT%\*.*") DO IF NOT "%%F"=="%BACKUP_DIR%" (MOVE "%%F" "%BACKUP_DIR%\" >> "%LOG_FILE%" 2>&1)


REM Neue Dateien kopieren
ECHO Kopiere neue Dateien von %NEW_APP_PATH% nach %CURRENT_APP_ROOT% >> "%LOG_FILE%"
xcopy "%NEW_APP_PATH%"\* "%CURRENT_APP_ROOT%\" /E /I /Y >> "%LOG_FILE%" 2>&1

REM Abhängigkeiten installieren (falls sich requirements.txt geändert hat)
ECHO Installiere/aktualisiere Python-Abhängigkeiten... >> "%LOG_FILE%"
pip install -r "%CURRENT_APP_ROOT%\requirements.txt" >> "%LOG_FILE%" 2>&1

REM Datenbank-Migrationen werden beim Start der App (durch init_db() in app.py) automatisch durchgeführt.
ECHO Datenbank-Migrationen werden beim nächsten Start der Anwendung ausgefuehrt. >> "%LOG_FILE%"

REM Temporären Update-Ordner aufräumen
ECHO Entferne temporären Update-Ordner: %NEW_APP_PATH% >> "%LOG_FILE%"
rmdir /s /q "%NEW_APP_PATH%" >> "%LOG_FILE%" 2>&1

REM Flask-Dienst starten (ANPASSEN, falls du deine App als Dienst oder direkt ausführst)
REM Beispiel: starte deine Flask-App mit einem Batch-Skript oder als Windows-Dienst
ECHO Starte Flask-Anwendung... >> "%LOG_FILE%"
REM Wenn du deine Flask-App direkt mit `python app.py` startest:
REM ACHTUNG: Dies ist für die Produktion NICHT empfohlen! Besser als Windows-Dienst.
start "" python "%CURRENT_APP_ROOT%\app.py" >> "%LOG_FILE%" 2>&1

ECHO --- Update-Skript beendet: %DATE% %TIME% --- >> "%LOG_FILE%"

EXIT /b 0
