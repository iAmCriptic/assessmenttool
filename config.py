import os

class Config:
    """Basis-Konfigurationsklasse für die Flask-Anwendung."""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your_secret_key_here' # Ersetzen Sie dies durch einen sicheren, zufälligen Schlüssel
    DATABASE = 'database.db'
    UPLOAD_FOLDER = 'uploads'
    ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'png', 'jpg', 'jpeg', 'gif', 'svg'}
    DEFAULT_ADMIN_PASSWORD = 'password' # Standard-Admin-Passwort, das geändert werden muss
    # Optionaler URL-Unterpfad hinter Reverse-Proxy, z. B. "/unterpfad"
    APPLICATION_ROOT = os.environ.get('APPLICATION_ROOT', '').rstrip('/')
    # Cookie immer für die gesamte Domain gültig machen (nicht nur Subpfad),
    # damit Sessions bei Redirects mit/ohne Prefix nicht verloren gehen.
    SESSION_COOKIE_PATH = '/'

    # Stelle sicher, dass der Upload-Ordner existiert
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
