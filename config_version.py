# config_version.py
# Zentrale Konfigurationsdatei für Versionsinformationen und Update-Details

# GitHub Repository Details für automatische Updates
# ÄNDERE DIESE WERTE, um sie an dein tatsächliches GitHub-Repository anzupassen.
GITHUB_REPO_OWNER = 'iAmCriptic' 
GITHUB_REPO_NAME = 'assessmenttool'      

# Optional: GitHub Personal Access Token für private Repositories oder höhere Ratenbegrenzungen.
# Lade diesen NICHT direkt im Code hoch. Verwende Umgebungsvariablen für die Produktion.
# Für die Entwicklung kannst du ihn hier temporär setzen oder als Umgebungsvariable beim Start der App.
# GITHUB_TOKEN = None 
# import os
# GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')

# Aktuelle Version deiner Anwendung
# Diese sollte dem 'tag_name' deines aktuellen GitHub-Release entsprechen (z.B. 'v1.0.0')
CURRENT_APP_VERSION = "V3" # <<< WICHTIG: Passe dies an deine aktuelle Version an!

# Versionen für Frontend und Backend (können gleich der APP_VERSION sein oder spezifischer)
FRONTEND_VERSION = "3.0.1 - Stable"
BACKEND_VERSION = "2.5.3 - Stable"

