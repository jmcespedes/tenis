from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import logging
import os
import psycopg2
from psycopg2.extras import RealDictCursor
import re
from datetime import datetime

# Configuración básica de la app
app = Flask(__name__)

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuración de la base de datos
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'dpg-d00re5c9c44c73ckj38g-a.oregon-postgres.render.com'),
    'user': os.getenv('DB_USER', 'reservas_0m08_user'),
    'password': os.getenv('DB_PASS', 'gJ6CvycTBwpsWe7j166vb7nA5RqQPx9k'),
    'dbname': os.getenv('DB_NAME', 'reservas_0m08'),
    'port': os.getenv('DB_PORT', '5432')
}

# Emojis para mejorar la experiencia
EMOJIS = {
    'tennis': '🎾',
    'hand': '👋',
    'ball': '🎯',
    'clock': '⏰',
    'calendar': '📅',
    'check': '✅',
    'cross': '❌',
    'warning': '⚠️',
    'info': 'ℹ️',
    'happy': '😊',
    'court': '🏟️'
}

@app.route('/')
def home():
    return 'Aplicación en funcionamiento!'

def get_db_connection():
    """Obtiene conexión a la base de datos"""
    return psycopg2.connect(cursor_factory=RealDictCursor, **DB_CONFIG)

def buscar_socio_por_celular(celular):
    """Busca socio por número de celular en formato +569XXXXXXXX"""
    try:
        cleaned_number = ''.join([c for c in celular if c.isdigit() or c == '+'])
        
        if not cleaned_number.startswith('+569') and len(cleaned_number) >= 9:
            if cleaned_number.startswith('569'):
                cleaned_number = '+' + cleaned_number
            elif cleaned_number.startswith('9'):
                cleaned_number = '+56' + cleaned_number
        
        logger.info(f"Buscando número: {cleaned_number}")
        
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM socios WHERE celular = %s",
                (cleaned_number,)
            )
            return cursor.fetchone()
    except Exception as e:
        logger.error(f"Error en DB: {e}")
        return None
    finally:
        if 'conn' in locals():
            conn.close()

def verificar_fecha_disponible(fecha_str):
    """Verifica si la fecha tiene formato correcto y es futura"""
    try:
        fecha = datetime.strptime(fecha_str, '%d-%m').date()
        fecha = fecha.replace(year=datetime.now().year)
        
        if fecha < datetime.now().date():
            fecha = fecha.replace(year=datetime.now().year + 1)
            
        return True, fecha.strftime('%Y-%m-%d')
    except ValueError:
        return False, "Formato de fecha inválido. Usa DD-MM (ej: 20-04)"

def obtener_horas_disponibles(fecha):
    """Obtiene horas disponibles para una fecha específica"""
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT hora, STRING_AGG(cancha::text, ', ') as canchas
                FROM reservas 
                WHERE fecha = %s AND reservada = 0
                GROUP BY hora
                ORDER BY hora
            """, (fecha,))
            return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error al obtener horas: {e}")
        return None
    finally:
        if 'conn' in locals():
            conn.close()

def obtener_canchas_disponibles(fecha, hora):
    """Obtiene canchas disponibles para fecha y hora específica"""
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT cancha 
                FROM reservas 
                WHERE fecha = %s AND hora = %s AND reservada = 0
                ORDER BY cancha
            """, (fecha, hora))
            return [row['cancha'] for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Error al obtener canchas: {e}")
        return None
    finally:
        if 'conn' in locals():
            conn.close()

def realizar_reserva(fecha, hora, cancha, socio):
    """Realiza una reserva en la base de datos"""
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE reservas 
                SET reservada = 1, 
                    rut_socio = %s,
                    nombre_socio = %s,
                    celular_socio = %s
                WHERE fecha = %s AND hora = %s AND cancha = %s
                RETURNING *
            """, (socio['rut'], socio['nombre'], socio['celular'], fecha, hora, cancha))
            conn.commit()
            return cursor.fetchone()
    except Exception as e:
        logger.error(f"Error al realizar reserva: {e}")
        conn.rollback()
        return None
    finally:
        if 'conn' in locals():
            conn.close()

@app.route("/whatsapp", methods=['POST'])
def whatsapp_reply():
    """Endpoint para respuestas de WhatsApp"""
    try:
        user_message = request.form.get('Body', '').strip()
        whatsapp_number = request.form.get('From', '')
        user_number = whatsapp_number.replace('whatsapp:', '')
        
        logger.info(f"Mensaje de {user_number}: {user_message}")
        
        # Obtener contexto de conversación
        session = {'step': None, 'fecha': None, 'hora': None, 'cancha': None}
        
        # Verificar si es una fecha (DD-MM)
        if re.match(r'^\d{1,2}-\d{1,2}$', user_message):
            valido, fecha = verificar_fecha_disponible(user_message)
            if not valido:
                response = MessagingResponse()
                response.message(f"{EMOJIS['cross']} {fecha}")
                return str(response), 200, {'Content-Type': 'text/xml'}
            
            session['fecha'] = fecha
            horas = obtener_horas_disponibles(fecha)
            
            if not horas:
                response = MessagingResponse()
                response.message(f"{EMOJIS['cross']} No hay horarios disponibles para el {user_message}")
                return str(response), 200, {'Content-Type': 'text/xml'}
            
            opciones = "\n".join([f"{EMOJIS['clock']} {hora['hora']} (Canchas: {hora['canchas']})" 
                       for hora in horas])
            
            response = MessagingResponse()
            response.message(
                f"{EMOJIS['calendar']} Horarios disponibles para el {user_message}:\n\n"
                f"{opciones}\n\n"
                f"Por favor, escribe la hora que deseas (ej: 08:00)"
            )
            return str(response), 200, {'Content-Type': 'text/xml'}
        
        # Verificar si es una hora (HH:MM)
        elif re.match(r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$', user_message) and session.get('fecha'):
            canchas = obtener_canchas_disponibles(session['fecha'], user_message)
            
            if not canchas:
                response = MessagingResponse()
                response.message(f"{EMOJIS['cross']} No hay canchas disponibles a las {user_message}")
                return str(response), 200, {'Content-Type': 'text/xml'}
            
            response = MessagingResponse()
            response.message(
                f"{EMOJIS['court']} Canchas disponibles a las {user_message}:\n\n"
                f"{', '.join([f'Cancha {c}' for c in canchas])}\n\n"
                f"Por favor, escribe el número de cancha que deseas (ej: 1)"
            )
            return str(response), 200, {'Content-Type': 'text/xml'}
        
        # Verificar si es número de cancha (1-4)
        elif user_message.isdigit() and 1 <= int(user_message) <= 4 and session.get('fecha') and session.get('hora'):
            # Aquí iría la lógica para confirmar la reserva
            pass
        
        # Buscar socio si no es un paso de reserva
        socio = buscar_socio_por_celular(user_number)
        
        if socio:
            if 'si' in user_message.lower() or 'sí' in user_message.lower():
                response_text = (
                    f"{EMOJIS['hand']} ¡Hola {socio['nombre']}! {EMOJIS['happy']}\n\n"
                    f"{EMOJIS['calendar']} Por favor, escribe el día que deseas reservar (DD-MM)\n"
                    f"Ejemplo: 20-04 para el 20 de Abril"
                )
            else:
                response_text = (
                    f"{EMOJIS['hand']} ¡Hola! {EMOJIS['happy']}\n\n"
                    f"{EMOJIS['ball']} *Bienvenido a Club de Tenis Chocalán* {EMOJIS['ball']}\n\n"
                    f"{EMOJIS['calendar']} ¿Deseas reservar una cancha? Responde 'SI' {EMOJIS['calendar']}"
                )
        else:
            response_text = (
                f"{EMOJIS['cross']} No encontramos tu número en la base de datos.\n"
                f"Si es un error, contáctanos para verificar tus datos. {EMOJIS['info']}"
            )
            
        response = MessagingResponse()
        response.message(response_text)
        return str(response), 200, {'Content-Type': 'text/xml'}
        
    except Exception as e:
        logger.error(f"Error: {e}")
        response = MessagingResponse()
        response.message(f"{EMOJIS['warning']} Error interno. Intenta más tarde. {EMOJIS['warning']}")
        return str(response), 200, {'Content-Type': 'text/xml'}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)