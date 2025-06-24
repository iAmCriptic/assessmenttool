import sqlite3
from flask import g, current_app 
import datetime

# Importiere Konfiguration
from config import Config

def get_db():
    """Stellt eine Datenbankverbindung her oder gibt die aktuelle zurück."""
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row # Ermöglicht den Zugriff auf Spalten als Wörterbuch
    return g.db

def close_connection(exception):
    """Schließt die Datenbankverbindung am Ende der Anfrage."""
    db = g.pop('db', None)
    if db is not None:
        db.close()

def get_role_id(role_name):
    """Hilfsfunktion zum Abrufen der Rollen-ID anhand des Namens."""
    db = get_db()
    cursor = db.cursor()
    role = cursor.execute("SELECT id FROM roles WHERE name = ?", (role_name,)).fetchone()
    return role['id'] if role else None

def init_db():
    """Initialisiert die Datenbank und erstellt Tabellen, falls sie nicht existieren."""
    db = get_db()
    cursor = db.cursor()

    # Tabellen werden nur erstellt, wenn sie nicht existieren.
    # KEINE DROP TABLE IF EXISTS ANWEISUNGEN HIER MEHR!

    # Erstelle Rollen-Tabelle
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
    """)

    # Aktualisierte Benutzer-Tabelle (mit display_name)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            display_name TEXT,
            is_admin INTEGER DEFAULT 0
        )
    """)

    # Verknüpfungstabelle für Many-to-Many-Beziehung zwischen Benutzern und Rollen
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_roles (
            user_id INTEGER NOT NULL,
            role_id INTEGER NOT NULL,
            PRIMARY KEY (user_id, role_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE
        )
    """)

    # Tabelle für Räume
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
    """)

    # Aktualisierte Tabelle für Stände (mit room_id und description, wie von stands.py erwartet)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            room_id INTEGER,
            FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE SET NULL
        )
    ''')

    # Tabelle für Bewertungskriterien (mit Beschreibung)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS criteria (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            max_score INTEGER NOT NULL,
            description TEXT
        )
    ''')

    # evaluations-Tabelle
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS evaluations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            stand_id INTEGER NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (stand_id) REFERENCES stands(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(user_id, stand_id)
        )
    ''')

    # evaluation_scores-Tabelle
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS evaluation_scores (
            evaluation_id INTEGER NOT NULL,
            criterion_id INTEGER NOT NULL,
            score INTEGER NOT NULL,
            PRIMARY KEY (evaluation_id, criterion_id),
            FOREIGN KEY (evaluation_id) REFERENCES evaluations(id) ON DELETE CASCADE,
            FOREIGN KEY (criterion_id) REFERENCES criteria(id) ON DELETE CASCADE
        )
    ''')

    # Tabelle für Rauminspektionen
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS room_inspections (
            room_id INTEGER PRIMARY KEY,
            inspector_user_id INTEGER NOT NULL,
            inspection_timestamp TEXT NOT NULL,
            is_clean BOOLEAN NOT NULL DEFAULT 0,
            comment TEXT,
            FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE,
            FOREIGN KEY (inspector_user_id) REFERENCES users(id) ON DELETE RESTRICT
        )
    """)

    # warnings-Tabelle
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS warnings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stand_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            comment TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_invalidated INTEGER DEFAULT 0,
            invalidated_by_user_id INTEGER,
            invalidation_comment TEXT,
            invalidation_timestamp DATETIME,
            FOREIGN KEY (stand_id) REFERENCES stands(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (invalidated_by_user_id) REFERENCES users(id) ON DELETE SET NULL
        )
    """)

    # NEUE TABELLE FÜR APP-EINSTELLUNGEN
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS app_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            setting_key TEXT NOT NULL UNIQUE,
            setting_value TEXT
        )
    """)

    # NEUE TABELLE FÜR LAGEPLÄNE
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS floor_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            image_path TEXT NOT NULL,
            width_px REAL,
            height_px REAL,
            scale_point1_x REAL,
            scale_point1_y REAL,
            scale_point2_x REAL,
            scale_point2_y REAL,
            scale_distance_meters REAL,
            is_active INTEGER DEFAULT 0 -- Nur ein Plan kann aktiv sein
        )
    """)

    # NEUE TABELLE FÜR LAGEPLAN-OBJEKTE (Stände, Mülleimer, Steckdosen)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS floor_plan_objects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_id INTEGER NOT NULL,
            type TEXT NOT NULL, -- 'stand', 'trash_can', 'power_outlet'
            x REAL NOT NULL,
            y REAL NOT NULL,
            width REAL,
            height REAL,
            color TEXT, -- Für Stände (Hex-Code)
            trash_can_color TEXT, -- Für Mülleimer ('yellow', 'blue', 'black')
            power_outlet_label TEXT, -- Für Steckdosen (die Zahl, z.B. '1')
            stand_id INTEGER, -- Verknüpfung zum stands-Tabelle, wenn Typ 'stand'
            custom_stand_name TEXT, -- NEU: Spalte für benutzerdefinierten Namen
            FOREIGN KEY (plan_id) REFERENCES floor_plans(id) ON DELETE CASCADE,
            FOREIGN KEY (stand_id) REFERENCES stands(id) ON DELETE SET NULL
        )
    """)

    db.commit()

def add_initial_data():
    """Fügt Initialdaten (Benutzer und Rollen) hinzu, falls noch nicht vorhanden."""
    db = get_db()
    cursor = db.cursor()

    # Füge Standardrollen hinzu, falls noch nicht vorhanden
    cursor.execute("INSERT OR IGNORE INTO roles (id, name) VALUES (1, 'Administrator')")
    cursor.execute("INSERT OR IGNORE INTO roles (id, name) VALUES (2, 'Bewerter')")
    cursor.execute("INSERT OR IGNORE INTO roles (id, name) VALUES (3, 'Betrachter')")
    cursor.execute("INSERT OR IGNORE INTO roles (id, name) VALUES (4, 'Inspektor')")
    cursor.execute("INSERT OR IGNORE INTO roles (id, name) VALUES (5, 'Verwarner')")
    db.commit() # Commit nach Rollen, damit sie für Benutzer verfügbar sind

    admin_role_id = get_role_id('Administrator')
    
    # Füge Administrator-Benutzer 'admin' hinzu oder aktualisiere ihn
    cursor.execute("SELECT id, password FROM users WHERE username = ?", ('admin',))
    admin_user_data = cursor.fetchone()

    if not admin_user_data:
        # Admin-Benutzer existiert nicht, füge ihn mit dem Standardpasswort hinzu
        cursor.execute("INSERT INTO users (username, password, display_name, is_admin) VALUES (?, ?, ?, ?)",
                       ('admin', current_app.config['DEFAULT_ADMIN_PASSWORD'], 'Administrator', 1))
        admin_user_id = cursor.lastrowid
        if admin_role_id:
            cursor.execute("INSERT OR IGNORE INTO user_roles (user_id, role_id) VALUES (?, ?)", (admin_user_id, admin_role_id))
        print("Initialer Benutzer 'admin' mit temporärem Passwort hinzugefügt. Bitte ändern Sie es beim ersten Login.")
    else:
        # Admin-Benutzer existiert. Überprüfe, ob das Passwort noch das Standardpasswort ist.
        # Wenn es das Standardpasswort ist, stelle sicher, dass das is_admin-Flag gesetzt ist
        # und die Administrator-Rolle zugewiesen ist, falls noch nicht geschehen.
        admin_user_id = admin_user_data['id']
        if admin_user_data['password'] == current_app.config['DEFAULT_ADMIN_PASSWORD']:
            cursor.execute("UPDATE users SET is_admin = 1, display_name = ? WHERE id = ? ",
                           ('Administrator', admin_user_id))
            if admin_role_id:
                cursor.execute("INSERT OR IGNORE INTO user_roles (user_id, role_id) VALUES (?, ?)", (admin_user_id, admin_role_id))
            print("Benutzer 'admin' existiert immer noch mit temporärem Passwort. Stellen Sie sicher, dass die Rolle korrekt ist.")
        else:
            # Wenn das Passwort bereits geändert wurde, stelle einfach sicher, dass die Admin-Flags korrekt sind.
            cursor.execute("UPDATE users SET is_admin = 1 WHERE id = ? ", (admin_user_id,))
            if admin_role_id:
                cursor.execute("INSERT OR IGNORE INTO user_roles (user_id, role_id) VALUES (?, ?)", (admin_user_id, admin_role_id))
            print("Benutzer 'admin' existiert und das Passwort wurde bereits geändert.")
    
    # Füge Standard-App-Einstellungen hinzu, falls nicht vorhanden
    default_settings = {
        'index_title_text': 'Willkommen',
        'index_title_color': '#1f2937', # Tailwind text-gray-800
        'bg_gradient_color1': '#ffb3c1',
        'bg_gradient_color2': '#a7d9f7',
        'dark_bg_gradient_color1': '#8B0000', # NEU: Standard-Dark-Mode-Verlaufsfarbe 1
        'dark_bg_gradient_color2': '#00008B', # NEU: Standard-Dark-Mode-Verlaufsfarbe 2
        'logo_url': '/static/img/logo_V2.png', # Direkter relativer Pfad
        'favicon_url': '/static/img/logo_V2.png' # Direkter relativer Pfad
    }

    for key, default_value in default_settings.items():
        # Überprüfen, ob der Schlüssel bereits existiert
        setting = cursor.execute("SELECT setting_value FROM app_settings WHERE setting_key = ?", (key,)).fetchone()
        if setting is None:
            # Füge die Einstellung nur hinzu, wenn sie noch nicht existiert
            cursor.execute("INSERT INTO app_settings (setting_key, setting_value) VALUES (?, ?)", (key, default_value))
    db.commit()

    # Die Abschnitte zum Hinzufügen von Beispiel-Ständen, -Räumen und -Kriterien wurden entfernt.
