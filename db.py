import sqlite3
from flask import g, current_app 
import datetime

# Importiere Konfiguration
from config import Config

def get_db():
    """Establishes a database connection or returns the current one."""
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row # Allows access to columns as a dictionary
    return g.db

def close_connection(exception):
    """Closes the database connection at the end of the request."""
    db = g.pop('db', None)
    if db is not None:
        db.close()

def get_role_id(role_name):
    """Helper function to retrieve the role ID by name."""
    db = get_db()
    cursor = db.cursor()
    role = cursor.execute("SELECT id FROM roles WHERE name = ?", (role_name,)).fetchone()
    return role['id'] if role else None

# --- DATABASE MIGRATION SYSTEM ---

def _get_current_schema_version(cursor):
    """Retrieves the current schema version from the database."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schema_versions (
            version TEXT PRIMARY KEY,
            applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("SELECT version FROM schema_versions ORDER BY applied_at DESC LIMIT 1")
    result = cursor.fetchone()
    return result['version'] if result else "0.0.0" # Start version if no entry

def _record_schema_version(cursor, version):
    """Records an applied schema version."""
    # NEU: INSERT OR IGNORE, um UNIQUE constraint failed zu verhindern, wenn Version bereits existiert
    cursor.execute("INSERT OR IGNORE INTO schema_versions (version) VALUES (?)", (version,))

def migrate_to_1_0_1(cursor):
    """
    Migration to version 1.0.1: Add 'is_active' column to 'users' table if it doesn't exist.
    """
    try:
        # Check if the column already exists to prevent errors on re-run
        cursor.execute("PRAGMA table_info(users)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'is_active' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN is_active INTEGER DEFAULT 1")
            print("Migration 1.0.1: Added 'is_active' column to users table.")
            return True # Rückgabe True nur, wenn die Änderung tatsächlich vorgenommen wurde
        else:
            print("Migration 1.0.1: 'is_active' column already exists in users table.")
            return True # Rückgabe True, da der gewünschte Zustand erreicht ist
    except sqlite3.Error as e:
        print(f"Error during migration 1.0.1: {e}")
        return False

def migrate_to_1_0_2(cursor):
    """
    Migration to version 1.0.2: Add 'contact_email' column to 'stands' table if it doesn't exist.
    """
    try:
        cursor.execute("PRAGMA table_info(stands)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'contact_email' not in columns:
            cursor.execute("ALTER TABLE stands ADD COLUMN contact_email TEXT")
            print("Migration 1.0.2: Added 'contact_email' column to stands table.")
            return True # Rückgabe True nur, wenn die Änderung tatsächlich vorgenommen wurde
        else:
            print("Migration 1.0.2: 'contact_email' column already exists in stands table.")
            return True # Rückgabe True, da der gewünschte Zustand erreicht ist
    except sqlite3.Error as e:
        print(f"Error during migration 1.0.2: {e}")
        return False

# Define migration functions in order
MIGRATIONS = {
    "1.0.1": migrate_to_1_0_1,
    "1.0.2": migrate_to_1_0_2,
    # Add new migrations here in chronological order
    # "2.0.0": migrate_to_2_0_0,
}

def apply_migrations(db):
    """Applies all pending schema migrations."""
    cursor = db.cursor()
    current_version_str = _get_current_schema_version(cursor)
    
    # Convert version string to a comparable tuple of integers
    def parse_version(version_str):
        return tuple(map(int, version_str.split('.')))

    current_version = parse_version(current_version_str)
    
    print(f"Current database schema version: {current_version_str}")
    
    # Sort versions using the same parsing logic
    sorted_versions = sorted(MIGRATIONS.keys(), key=parse_version)
    
    for version_str in sorted_versions:
        migration_version = parse_version(version_str)
        if migration_version > current_version:
            print(f"Applying migration {version_str}...")
            if MIGRATIONS[version_str](cursor):
                _record_schema_version(cursor, version_str)
                db.commit()
                print(f"Migration {version_str} applied successfully.")
            else:
                db.rollback()
                print(f"Migration {version_str} failed. Rolling back changes.")
                return False # Stop if a migration fails
    print("All migrations applied or no new migrations found.")
    return True

# --- END DATABASE MIGRATION SYSTEM ---


def init_db():
    """Initializes the database and creates tables if they do not exist."""
    db = get_db()
    cursor = db.cursor()

    # Tables are only created if they do not exist.
    # NO DROP TABLE IF EXISTS STATEMENTS HERE ANYMORE!

    # Create Roles table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
    """)

    # Updated Users table (with display_name)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            display_name TEXT,
            is_admin INTEGER DEFAULT 0
        )
    """)

    # Link table for Many-to-Many relationship between users and roles
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_roles (
            user_id INTEGER NOT NULL,
            role_id INTEGER NOT NULL,
            PRIMARY KEY (user_id, role_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE
        )
    """)

    # Table for rooms
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
    """)

    # Updated Stands table (with room_id and description, as expected by stands.py)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            room_id INTEGER,
            FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE SET NULL
        )
    ''')

    # Table for evaluation criteria (with description)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS criteria (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            max_score INTEGER NOT NULL,
            description TEXT
        )
    ''')

    # evaluations table
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

    # evaluation_scores table
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

    # Table for room inspections
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

    # warnings table
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

    # NEW TABLE FOR APP SETTINGS
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS app_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            setting_key TEXT NOT NULL UNIQUE,
            setting_value TEXT
        )
    """)

    # NEW TABLE FOR FLOOR PLANS
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
            is_active INTEGER DEFAULT 0 -- Only one plan can be active
        )
    """)

    # NEW TABLE FOR FLOOR PLAN OBJECTS (stands, trash cans, power outlets)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS floor_plan_objects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_id INTEGER NOT NULL,
            type TEXT NOT NULL, -- 'stand', 'trash_can', 'power_outlet'
            x REAL NOT NULL,
            y REAL NOT NULL,
            width REAL,
            height REAL,
            color TEXT, -- For stands (hex code)
            trash_can_color TEXT, -- For trash cans ('yellow', 'blue', 'black')
            wc_label TEXT, -- For WC (e.g. 'WC')      
            power_outlet_label TEXT, -- For power outlets (the number, e.g. '1')
            stand_id INTEGER, -- Link to stands table, if type 'stand'
            custom_stand_name TEXT, -- NEW: Column for custom name
            FOREIGN KEY (plan_id) REFERENCES floor_plans(id) ON DELETE CASCADE,
            FOREIGN KEY (stand_id) REFERENCES stands(id) ON DELETE SET NULL
        )
    """)

    db.commit() # Commit initial table creations

    # After tables are created/checked, apply pending migrations
    apply_migrations(db)

def add_initial_data():
    """Adds initial data (users and roles) if not already present."""
    db = get_db()
    cursor = db.cursor()

    # Add default roles if not already present
    cursor.execute("INSERT OR IGNORE INTO roles (id, name) VALUES (1, 'Administrator')")
    cursor.execute("INSERT OR IGNORE INTO roles (id, name) VALUES (2, 'Bewerter')")
    cursor.execute("INSERT OR IGNORE INTO roles (id, name) VALUES (3, 'Betrachter')")
    cursor.execute("INSERT OR IGNORE INTO roles (id, name) VALUES (4, 'Inspektor')")
    cursor.execute("INSERT OR IGNORE INTO roles (id, name) VALUES (5, 'Verwarner')")
    db.commit() # Commit after roles so they are available for users

    admin_role_id = get_role_id('Administrator')
    
    # Add 'admin' user or update it
    cursor.execute("SELECT id, password FROM users WHERE username = ?", ('admin',))
    admin_user_data = cursor.fetchone()

    if not admin_user_data:
        # Admin user does not exist, add with default password
        cursor.execute("INSERT INTO users (username, password, display_name, is_admin, is_active) VALUES (?, ?, ?, ?, ?)", # is_active hinzugefügt
                       ('admin', current_app.config['DEFAULT_ADMIN_PASSWORD'], 'Administrator', 1, 1))
        admin_user_id = cursor.lastrowid
        if admin_role_id:
            cursor.execute("INSERT OR IGNORE INTO user_roles (user_id, role_id) VALUES (?, ?)", (admin_user_id, admin_role_id))
        print("Initial 'admin' user added with temporary password. Please change it on first login.")
    else:
        # Admin user exists. Check if password is still the default.
        # If it's the default password, ensure is_admin flag is set
        # and Administrator role is assigned, if not already.
        admin_user_id = admin_user_data['id']
        if admin_user_data['password'] == current_app.config['DEFAULT_ADMIN_PASSWORD']:
            cursor.execute("UPDATE users SET is_admin = 1, display_name = ?, is_active = ? WHERE id = ? ", # is_active hinzugefügt
                           ('Administrator', 1, admin_user_id))
            if admin_role_id:
                cursor.execute("INSERT OR IGNORE INTO user_roles (user_id, role_id) VALUES (?, ?)", (admin_user_id, admin_role_id))
            print("User 'admin' still exists with temporary password. Please ensure role is correct.")
        else:
            # If password has already been changed, just ensure admin flags are correct.
            cursor.execute("UPDATE users SET is_admin = 1 WHERE id = ? ", (admin_user_id,))
            if admin_role_id:
                cursor.execute("INSERT OR IGNORE INTO user_roles (user_id, role_id) VALUES (?, ?)", (admin_user_id, admin_role_id))
            print("User 'admin' exists and password has already been changed.")
    
    # Add default app settings if not present
    default_settings = {
        'index_title_text': 'Welcome',
        'index_title_color': '#1f2937', # Tailwind text-gray-800
        'bg_gradient_color1': '#ffb3c1',
        'bg_gradient_color2': '#a7d9f7',
        'dark_bg_gradient_color1': '#8B0000', # NEW: Default dark mode gradient color 1
        'dark_bg_gradient_color2': '#00008B', # NEW: Default dark mode gradient color 2
        'logo_url': '/static/img/logo_V2.png', # Direct relative path
        'favicon_url': '/static/img/logo_V2.png' # Direct relative path
    }

    for key, default_value in default_settings.items():
        # Check if key already exists
        setting = cursor.execute("SELECT setting_value FROM app_settings WHERE setting_key = ?", (key,)).fetchone()
        if setting is None:
            # Add setting only if it doesn't exist yet
            cursor.execute("INSERT INTO app_settings (setting_key, setting_value) VALUES (?, ?)", (key, default_value))
    db.commit()

    # Sections for adding sample stands, rooms, and criteria have been removed.

