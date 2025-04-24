from flask import Flask, jsonify, request
import mysql.connector
import json
from functools import wraps

app = Flask(__name__)

# Configuración de la base de datos Moodle con tus credenciales
DB_CONFIG = {
    'host': '204.48.25.122',
    'user': 'indeseg_select',
    'password': 'MySQL#2024',
    'database': 'moodle'  # Asegúrate que este es el nombre correcto de la BD
}

# Token de autenticación
API_TOKEN = "61b2a4b0b12dd9d85993029e2de42c3e"

# Decorador para verificar el token
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')

        if not token or token != f"Bearer {API_TOKEN}":
            return jsonify({'message': 'Token is missing or invalid'}), 401

        return f(*args, **kwargs)
    return decorated

@app.route('/api/grades', methods=['GET'])
@token_required
def get_grades():
    try:
        # Obtener parámetros
        course_id = request.args.get('course_id', type=int)
        user_id = request.args.get('user_id', type=int)

        if not course_id or not user_id:
            return jsonify({'error': 'Missing course_id or user_id parameters'}), 400

        # Conexión a la base de datos
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # CONSULTA SQL ACTUALIZADA
        query = """
        SELECT 
            c.id AS course_id,
            u.id AS user_id,
            u.idnumber AS identification,
            CONCAT(u.firstname, ' ', u.lastname) AS name,
            (
                SELECT JSON_ARRAYAGG(
                    JSON_OBJECT(
                        'competence', COALESCE(co.shortname, 'No asociada a competencia'),
                        'body', gi.itemname,
                        'note', ROUND(gg.finalgrade, 1),
                        'year', CAST(FROM_UNIXTIME(c.startdate, '%Y') AS UNSIGNED)
                    )
                )
                FROM mdl_grade_items gi
                LEFT JOIN mdl_grade_grades gg ON gg.itemid = gi.id AND gg.userid = u.id
                LEFT JOIN mdl_course_modules cm ON cm.course = c.id 
                    AND cm.instance = gi.iteminstance 
                    AND cm.module = (
                        SELECT id FROM mdl_modules WHERE name = gi.itemmodule
                    )
                LEFT JOIN mdl_competency_modulecomp cmc ON cm.id = cmc.cmid
                LEFT JOIN mdl_competency co ON cmc.competencyid = co.id
                WHERE gi.courseid = c.id
                AND gi.itemtype = 'mod'
            ) AS contents
        FROM 
            mdl_course c
        JOIN 
            mdl_context ctx ON c.id = ctx.instanceid AND ctx.contextlevel IN (50, 70)
        JOIN 
            mdl_role_assignments ra ON ctx.id = ra.contextid
        JOIN 
            mdl_user u ON ra.userid = u.id
        WHERE 
            c.id = %s AND u.id = %s
        """

        cursor.execute(query, (course_id, user_id))
        result = cursor.fetchone()

        if not result:
            return jsonify({'message': 'No data found for the given parameters'}), 404

        # Procesar los resultados
        if result['contents']:
            contents = json.loads(result['contents'])
            # Asegurar el orden en cada elemento de contents
            ordered_contents = []
            for item in contents:
                ordered_item = {
                    'competence': item['competence'],
                    'body': item['body'],
                    'note': item['note'],
                    'year': item['year']
                }
                ordered_contents.append(ordered_item)
            result['contents'] = ordered_contents
        else:
            result['contents'] = []

        cursor.close()
        conn.close()

        # Configurar el orden principal
        app.config['JSON_SORT_KEYS'] = False
        response_data = {
            'course_id': result['course_id'],
            'user_id': result['user_id'],
            'identification': result['identification'],
            'name': result['name'],
            'contents': result['contents']
        }

        return jsonify(response_data)
        
    except mysql.connector.Error as err:
        return jsonify({'error': f'Database error: {err}'}), 500
    except Exception as e:
        return jsonify({'error': f'Unexpected error: {e}'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
