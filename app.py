from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import logging
import os
import psycopg2
from psycopg2.extras import RealDictCursor
import re
from datetime import datetime

app = Flask(__name__)

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Config DB
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'dpg-d00re5c9c44c73ckj38g-a.oregon-postgres.render.com'),
    'user': os.getenv('DB_USER', 'reservas_0m08_user'),
    'password': os.getenv('DB_PASS', 'gJ6CvycTBwpsWe7j166vb7nA5RqQPx9k'),
    'dbname': os.getenv('DB_NAME', 'reservas_0m08'),
    'port': os.getenv('DB_PORT', '5432')
}

# Emojis
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
    return psycopg2.connect(cursor_factory=RealDictCursor, **DB_CONFIG)

# Sesiones
def cargar_sesion(celular):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM sesiones WHERE celular = %s", (celular,))
            return cursor.fetchone()
    except Exception as e:
        logger.error(f"Error al cargar sesión: {e}")
        return None
    finally:
        if 'conn' in locals():
            conn.close()

def guardar_sesion(celular, paso, fecha=None, hora=None, cancha=None):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO sesiones (celular, paso, fecha, hora, cancha)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (celular) DO UPDATE 
                SET paso = EXCLUDED.paso, fecha = EXCLUDED.fecha, hora = EXCLUDED.hora, cancha = EXCLUDED.cancha
            """, (celular, paso, fecha, hora, cancha))
            conn.commit()
    except Exception as e:
        logger.error(f"Error al guardar sesión: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

def limpiar_sesion(celular):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM sesiones WHERE celular = %s", (celular,))
            conn.commit()
    except Exception as e:
        logger.error(f"Error al limpiar sesión: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

# Lógica
def buscar_socio_por_celular(celular):
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
            cursor.execute("SELECT * FROM socios WHERE celular = %s", (cleaned_number,))
            return cursor.fetchone()
    except Exception as e:
        logger.error(f"Error en DB: {e}")
        return None
    finally:
        if 'conn' in locals():
            conn.close()

def verificar_fecha_disponible(fecha_str):
    try:
        fecha = datetime.strptime(fecha_str, '%d-%m').date()
        fecha = fecha.replace(year=datetime.now().year)
        if fecha < datetime.now().date():
            fecha = fecha.replace(year=datetime.now().year + 1)
        return True, fecha.strftime('%Y-%m-%d')
    except ValueError:
        return False, "Formato de fecha inválido. Usa DD-MM (ej: 20-04)"

def obtener_horas_disponibles(fecha):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT hora_inicial, hora_final, STRING_AGG(cancha::text, ', ') as canchas
                FROM reservas 
                WHERE fecha = %s AND reservada = 0
                GROUP BY hora_inicial, hora_final
                ORDER BY hora_inicial
            """, (fecha,))
            return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error al obtener horas: {e}")
        return None
    finally:
        if 'conn' in locals():
            conn.close()

def obtener_canchas_disponibles(fecha, hora_inicial):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT cancha 
                FROM reservas 
                WHERE fecha = %s AND hora_inicial = %s AND reservada = 0
                ORDER BY cancha
            """, (fecha, hora_inicial))
            return [row['cancha'] for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Error al obtener canchas: {e}")
        return None
    finally:
        if 'conn' in locals():
            conn.close()

def realizar_reserva(fecha, hora, cancha, socio):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE reservas 
                SET reservada = 1, 
                    rut = %s,
                    celular = %s                    
                WHERE fecha = %s AND hora_inicial = %s AND cancha = %s
                RETURNING *
            """, (socio['rut'], socio['celular'], fecha, hora, cancha))
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
    try:
        user_message = request.form.get('Body', '').strip()
        whatsapp_number = request.form.get('From', '')
        user_number = whatsapp_number.replace('whatsapp:', '')

        logger.info(f"Mensaje de {user_number}: {user_message}")

        sesion = cargar_sesion(user_number)
        paso = sesion['paso'] if sesion else None

        socio = buscar_socio_por_celular(user_number)
        response = MessagingResponse()

        if paso == 'esperando_hora':
            hora = user_message
            canchas = obtener_canchas_disponibles(sesion['fecha'], hora)
            if not canchas:
                response.message(f"{EMOJIS['cross']} No hay canchas disponibles a las {hora}")
            else:
                guardar_sesion(user_number, 'esperando_cancha', sesion['fecha'], hora)
                response.message(
                    f"{EMOJIS['court']} Canchas disponibles a las {hora}:\n\n"
                    f"{', '.join([f'Cancha {c}' for c in canchas])}\n\n"
                    f"Por favor, escribe el número de cancha que deseas (ej: 1)"
                )
            return str(response), 200, {'Content-Type': 'text/xml'}

        elif paso == 'esperando_cancha':
            cancha = user_message
            reserva = realizar_reserva(sesion['fecha'], sesion['hora'], cancha, socio)
            if reserva:
                response.message(
                    f"{EMOJIS['check']} ¡Reserva confirmada!\n\n"
                    f"{EMOJIS['calendar']} Día: {sesion['fecha']}\n"
                    f"{EMOJIS['clock']} Hora: {sesion['hora']}\n"
                    f"{EMOJIS['court']} Cancha: {cancha}"
                )
            else:
                response.message(f"{EMOJIS['cross']} No se pudo hacer la reserva. Intenta más tarde.")
            limpiar_sesion(user_number)
            return str(response), 200, {'Content-Type': 'text/xml'}

        if re.match(r'^\d{1,2}-\d{1,2}$', user_message):
            valido, fecha = verificar_fecha_disponible(user_message)
            if not valido:
                response.message(f"{EMOJIS['cross']} {fecha}")
                return str(response), 200, {'Content-Type': 'text/xml'}

            horas = obtener_horas_disponibles(fecha)
            if not horas:
                response.message(f"{EMOJIS['cross']} No hay horarios disponibles para el {user_message}")
                return str(response), 200, {'Content-Type': 'text/xml'}

            opciones = "\n".join([
                f"{EMOJIS['clock']} {hora['hora_inicial']} a {hora['hora_final']} (Canchas: {hora['canchas']})"
                for hora in horas
            ])
            guardar_sesion(user_number, 'esperando_hora', fecha)
            response.message(
                f"{EMOJIS['calendar']} Horarios disponibles para el {user_message}:\n\n"
                f"{opciones}\n\n"
                f"Por favor, escribe la hora de inicio que deseas (ej: 08:00)"
            )
            return str(response), 200, {'Content-Type': 'text/xml'}

        if socio:
            if 'si' in user_message.lower() or 'sí' in user_message.lower():
                response.message(
                    f"{EMOJIS['hand']} ¡Hola {socio['nombre']}! {EMOJIS['happy']}\n\n"
                    f"{EMOJIS['calendar']} Por favor, escribe el día que deseas reservar (DD-MM)\n"
                    f"Ejemplo: 10-03 para el 10 de Marzo"
                )
            else:
                response.message(
                    f"{EMOJIS['hand']} ¡Hola! {EMOJIS['happy']}\n\n"
                    f"{EMOJIS['tennis']} *Bienvenido a Club de Tenis Chocalán* {EMOJIS['tennis']}\n\n"
                    f"{EMOJIS['calendar']} ¿Deseas reservar una cancha? Responde 'SI'"
                )
        else:
            response.message(
                f"{EMOJIS['cross']} No encontramos tu número en la base de datos.\n"
                f"Si es un error, contáctanos para verificar tus datos. {EMOJIS['info']}"
            )

        return str(response), 200, {'Content-Type': 'text/xml'}

    except Exception as e:
        logger.error(f"Error: {e}")
        response = MessagingResponse()
        response.message(f"{EMOJIS['warning']} Error interno. Intenta más tarde.")
        return str(response), 200, {'Content-Type': 'text/xml'}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

