import os

class Config:
    """Basis-Konfigurationsklasse für die Flask-Anwendung."""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your_secret_key_here' # Ersetzen Sie dies durch einen sicheren, zufälligen Schlüssel
    DATABASE = 'database.db'
    UPLOAD_FOLDER = 'uploads'
    ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'png', 'jpg', 'jpeg', 'gif', 'svg'}
    DEFAULT_ADMIN_PASSWORD = 'password' # Standard-Admin-Passwort, das geändert werden muss

    # Stelle sicher, dass der Upload-Ordner existiert
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)

    # NEU: Pfade zu den Update-Skripten
    # Diese Pfade sollten absolut sein oder relativ zum Ausführungsverzeichnis der App
    LINUX_UPDATE_SCRIPT = os.path.join(os.getcwd(), 'update_and_restart.sh')
    WINDOWS_UPDATE_SCRIPT = os.path.join(os.getcwd(), 'update_and_restart.bat')

