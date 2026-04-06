import sqlite3
from flask import Blueprint, request, jsonify, render_template, session
from db import get_db
from decorators import role_required

ranking_bp = Blueprint('ranking', __name__)

VALID_SORT_MODES = {'total', 'average'}
VALID_RANKING_MODES = {'standard', 'visitor', 'combined'}


def _read_ranking_settings(cursor):
    settings = cursor.execute(
        "SELECT setting_key, setting_value FROM app_settings WHERE setting_key IN ('ranking_sort_mode', 'ranking_active_mode')"
    ).fetchall()
    settings_dict = {row['setting_key']: row['setting_value'] for row in settings}
    sort_mode = settings_dict.get('ranking_sort_mode', 'total')
    active_mode = settings_dict.get('ranking_active_mode', 'standard')
    if sort_mode not in VALID_SORT_MODES:
        sort_mode = 'total'
    if active_mode not in VALID_RANKING_MODES:
        active_mode = 'standard'
    return sort_mode, active_mode


def _build_ranking_payload(cursor, requested_mode=None, requested_sort_mode=None):
    sort_mode, active_mode = _read_ranking_settings(cursor)
    ranking_mode = requested_mode if requested_mode in VALID_RANKING_MODES else active_mode
    resolved_sort_mode = requested_sort_mode if requested_sort_mode in VALID_SORT_MODES else sort_mode

    criteria_max_total = cursor.execute("SELECT COALESCE(SUM(max_score), 0) AS total FROM criteria").fetchone()['total']
    criteria_max_total = float(criteria_max_total or 0)

    standard_rows = cursor.execute('''
        SELECT
            s.id AS stand_id,
            COALESCE(SUM(es.score), 0) AS total_score,
            COUNT(DISTINCT e.user_id) AS evaluator_count
        FROM stands s
        LEFT JOIN evaluations e ON e.stand_id = s.id
        LEFT JOIN evaluation_scores es ON es.evaluation_id = e.id
        GROUP BY s.id
    ''').fetchall()
    standard_map = {
        row['stand_id']: {
            'total': float(row['total_score'] or 0),
            'count': int(row['evaluator_count'] or 0)
        }
        for row in standard_rows
    }

    visitor_rows = cursor.execute('''
        SELECT
            s.id AS stand_id,
            COALESCE(SUM(ves.score), 0) AS total_score,
            COUNT(DISTINCT ve.visitor_token_hash) AS evaluator_count
        FROM stands s
        LEFT JOIN visitor_evaluations ve ON ve.stand_id = s.id
        LEFT JOIN visitor_evaluation_scores ves ON ves.visitor_evaluation_id = ve.id
        GROUP BY s.id
    ''').fetchall()
    visitor_map = {
        row['stand_id']: {
            'total': float(row['total_score'] or 0),
            'count': int(row['evaluator_count'] or 0)
        }
        for row in visitor_rows
    }

    stands = cursor.execute('''
        SELECT s.id AS stand_id, s.name AS stand_name, r.name AS room_name
        FROM stands s
        LEFT JOIN rooms r ON r.id = s.room_id
        ORDER BY s.name
    ''').fetchall()

    ranked_data = []
    for stand in stands:
        stand_id = stand['stand_id']
        standard = standard_map.get(stand_id, {'total': 0.0, 'count': 0})
        visitor = visitor_map.get(stand_id, {'total': 0.0, 'count': 0})

        standard_avg = (standard['total'] / standard['count']) if standard['count'] > 0 else 0.0
        visitor_avg = (visitor['total'] / visitor['count']) if visitor['count'] > 0 else 0.0

        standard_pct = (standard_avg / criteria_max_total) if criteria_max_total > 0 else 0.0
        visitor_pct = (visitor_avg / criteria_max_total) if criteria_max_total > 0 else 0.0
        combined_normalized = (0.5 * standard_pct) + (0.5 * visitor_pct)
        combined_avg = combined_normalized * criteria_max_total

        combined_total = standard['total'] + visitor['total']
        combined_count = standard['count'] + visitor['count']

        if ranking_mode == 'standard':
            mode_total = standard['total']
            mode_avg = standard_avg
            mode_count = standard['count']
        elif ranking_mode == 'visitor':
            mode_total = visitor['total']
            mode_avg = visitor_avg
            mode_count = visitor['count']
        else:
            mode_total = combined_total
            mode_avg = combined_avg
            mode_count = combined_count

        ranked_data.append({
            'stand_id': stand_id,
            'stand_name': stand['stand_name'],
            'room_name': stand['room_name'],
            'total_achieved_score': round(mode_total, 2),
            'average_score': round(mode_avg, 2),
            'num_evaluators': mode_count,
            'standard_total_score': round(standard['total'], 2),
            'standard_average_score': round(standard_avg, 2),
            'standard_num_evaluators': standard['count'],
            'visitor_total_score': round(visitor['total'], 2),
            'visitor_average_score': round(visitor_avg, 2),
            'visitor_num_evaluators': visitor['count'],
            'combined_total_score': round(combined_total, 2),
            'combined_average_score': round(combined_avg, 2),
            'combined_num_evaluators': combined_count
        })

    key_name = 'total_achieved_score' if resolved_sort_mode == 'total' else 'average_score'
    ranked_data.sort(key=lambda item: item[key_name], reverse=True)

    current_rank = 0
    previous_value = None
    for index, row in enumerate(ranked_data, start=1):
        current_value = row[key_name]
        if previous_value is None or current_value != previous_value:
            current_rank = index
        row['rank'] = current_rank
        previous_value = current_value

    return {
        'rankings': ranked_data,
        'ranking_mode': ranking_mode,
        'sort_mode': resolved_sort_mode,
        'active_mode': active_mode,
        'configured_sort_mode': sort_mode
    }


@ranking_bp.route('/view_ranking')
@role_required(['Administrator', 'Bewerter', 'Betrachter', 'Inspektor', 'Verwarner'])
def view_ranking_page():
    dark_mode_enabled = session.get('dark_mode_enabled', False)
    return render_template('view_ranking.html', dark_mode_enabled=dark_mode_enabled)


@ranking_bp.route('/api/ranking_data', methods=['GET'])
@role_required(['Administrator', 'Bewerter', 'Betrachter', 'Inspektor', 'Verwarner'])
def api_ranking_data():
    db = get_db()
    cursor = db.cursor()

    try:
        requested_mode = request.args.get('mode')
        requested_sort_mode = request.args.get('sort_mode')
        payload = _build_ranking_payload(cursor, requested_mode=requested_mode, requested_sort_mode=requested_sort_mode)
        return jsonify({'success': True, **payload})
    except sqlite3.Error as e:
        return jsonify({'success': False, 'message': f'Fehler beim Abrufen der Rangliste: {e}'}), 500
    except Exception as e:
        return jsonify({'success': False, 'message': f'Ein unerwarteter Fehler ist aufgetreten: {e}'}), 500


@ranking_bp.route('/api/public_ranking_data', methods=['GET'])
def api_public_ranking_data():
    db = get_db()
    cursor = db.cursor()
    try:
        requested_mode = request.args.get('mode')
        requested_sort_mode = request.args.get('sort_mode')
        payload = _build_ranking_payload(cursor, requested_mode=requested_mode, requested_sort_mode=requested_sort_mode)
        return jsonify({'success': True, **payload})
    except sqlite3.Error as e:
        return jsonify({'success': False, 'message': f'Fehler beim Abrufen der öffentlichen Rangliste: {e}'}), 500
    except Exception as e:
        return jsonify({'success': False, 'message': f'Ein unerwarteter Fehler ist aufgetreten: {e}'}), 500


@ranking_bp.route('/print_ranking')
@role_required(['Administrator', 'Bewerter', 'Betrachter', 'Inspektor', 'Verwarner'])
def print_ranking_page():
    dark_mode_enabled = session.get('dark_mode_enabled', False)
    return render_template('print_ranking.html', dark_mode_enabled=dark_mode_enabled)
