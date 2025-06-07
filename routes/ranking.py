import sqlite3
from flask import Blueprint, request, jsonify, current_app, render_template, session # Importiere render_template und session
from db import get_db
from decorators import role_required

ranking_bp = Blueprint('ranking', __name__)

@ranking_bp.route('/view_ranking')
@role_required(['Administrator', 'Bewerter', 'Betrachter', 'Inspektor', 'Verwarner'])
def view_ranking_page():
    """Rendert die Ranglistenseite."""
    dark_mode_enabled = session.get('dark_mode_enabled', False) # Hole den Dark Mode Status
    return render_template('view_ranking.html', dark_mode_enabled=dark_mode_enabled) # Übergebe ihn an das Template

@ranking_bp.route('/api/ranking_data', methods=['GET'])
@role_required(['Administrator', 'Bewerter', 'Betrachter', 'Inspektor', 'Verwarner'])
def api_ranking_data():
    """Gibt die Rangliste der Stände als JSON zurück."""
    db = get_db()
    cursor = db.cursor()

    try:
        rankings = cursor.execute('''
            SELECT
                s.id AS stand_id,
                s.name AS stand_name,
                r.name AS room_name,
                SUM(es.score) AS total_achieved_score,
                COUNT(DISTINCT e.user_id) AS num_evaluators
            FROM stands s
            LEFT JOIN rooms r ON s.room_id = r.id
            JOIN evaluations e ON s.id = e.stand_id
            JOIN evaluation_scores es ON e.id = es.evaluation_id
            JOIN criteria c ON es.criterion_id = c.id
            GROUP BY s.id, s.name, r.name
            ORDER BY total_achieved_score DESC
        ''').fetchall()

        ranked_data = []
        current_rank = 1
        previous_score = -1

        for i, row in enumerate(rankings):
            rank_entry = dict(row)
            # Logik für die Rangfolge (gleiche Punktzahl = gleicher Rang)
            if rank_entry['total_achieved_score'] != previous_score:
                current_rank = i + 1
            rank_entry['rank'] = current_rank
            previous_score = rank_entry['total_achieved_score']
            ranked_data.append(rank_entry)

        return jsonify({'success': True, 'rankings': ranked_data})

    except sqlite3.Error as e:
        print(f"Database error in api_ranking_data: {e}")
        return jsonify({'success': False, 'message': f'Fehler beim Abrufen der Rangliste: {e}'}), 500
    except Exception as e:
        print(f"An unexpected error occurred in api_ranking_data: {e}")
        return jsonify({'success': False, 'message': f'Ein unerwarteter Fehler ist aufgetreten: {e}'}), 500

@ranking_bp.route('/print_ranking')
@role_required(['Administrator', 'Bewerter', 'Betrachter', 'Inspektor', 'Verwarner'])
def print_ranking_page():
    """Rendert die Druckansicht der Rangliste."""
    dark_mode_enabled = session.get('dark_mode_enabled', False) # Hole den Dark Mode Status
    return render_template('print_ranking.html', dark_mode_enabled=dark_mode_enabled) # Übergebe ihn an das Template
