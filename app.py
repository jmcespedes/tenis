from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import logging
import os
import psycopg2
from psycopg2.extras import RealDictCursor
import re

# Configuración básica de la app
app = Flask(__name__)

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuración de la base de datos (usa variables de entorno para seguridad)
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
    'racket': '🏸',
    'ball': '🎯',
    'clock': '⏰',
    'calendar': '📅',
    'check': '✅',
    'cross': '❌',
    'warning': '⚠️',
    'info': 'ℹ️',
    'happy': '😊'
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
        # Limpiar el número manteniendo el formato +569...
        cleaned_number = ''.join([c for c in celular if c.isdigit() or c == '+'])
        
        # Asegurar que tenga el formato correcto
        if not cleaned_number.startswith('+569') and len(cleaned_number) >= 9:
            if cleaned_number.startswith('569'):
                cleaned_number = '+' + cleaned_number
            elif cleaned_number.startswith('9'):
                cleaned_number = '+56' + cleaned_number
        
        logger.info(f"Buscando número en formato BD: {cleaned_number}")
        
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

def verificar_disponibilidad(hora):
    """Verifica disponibilidad de canchas para una hora específica"""
    try:
        # Validar formato de hora (HH:MM)
        if not re.match(r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$', hora):
            return False, "Formato de hora inválido. Por favor usa HH:MM (ej: 08:00)"
        
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # Verificar disponibilidad (ejemplo básico)
            cursor.execute(
                "SELECT COUNT(*) as reservas FROM reservas WHERE hora = %s AND fecha = CURRENT_DATE",
                (hora,)
            )
            resultado = cursor.fetchone()
            
            if resultado['reservas'] >= 2:  # Suponiendo 2 canchas disponibles
                return False, f"{EMOJIS['cross']} No hay disponibilidad a las {hora}"
            else:
                return True, f"{EMOJIS['check']} Hay disponibilidad a las {hora}"
    except Exception as e:
        logger.error(f"Error al verificar disponibilidad: {e}")
        return False, f"{EMOJIS['warning']} Error al verificar disponibilidad"
    finally:
        if 'conn' in locals():
            conn.close()

@app.route("/whatsapp", methods=['POST'])
def whatsapp_reply():
    """Endpoint para respuestas de WhatsApp"""
    try:
        user_message = request.form.get('Body', '').strip().lower()
        whatsapp_number = request.form.get('From', '')
        user_number = whatsapp_number.replace('whatsapp:', '')
        
        logger.info(f"Mensaje de {user_number}: {user_message}")
        
        # Verificar si es una hora (HH:MM)
        if re.match(r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$', user_message):
            disponible, mensaje = verificar_disponibilidad(user_message)
            response = MessagingResponse()
            response.message(f"{EMOJIS['tennis']*3} {mensaje} {EMOJIS['tennis']*3}\n\n"
                           f"¿Quieres reservar para las {user_message}? Responde 'SI' para confirmar.")
            return str(response), 200, {'Content-Type': 'text/xml'}
        
        # Buscar socio si no es una hora específica
        socio = buscar_socio_por_celular(user_number)
        
        if socio:
            if 'si' in user_message or 'sí' in user_message:
                response_text = (
                    f"{EMOJIS['tennis']*3} *Club de Tenis Chocalán* {EMOJIS['tennis']*3}\n\n"
                    f"{EMOJIS['racket']} ¡Perfecto {socio['nombre']}! {EMOJIS['happy']}\n\n"
                    f"{EMOJIS['clock']} Por favor, escribe día que deseas reservar (ej: 18-04)\n\n"
                    f"{EMOJIS['info']} Para buscar disponibilidad"
                )
            else:
                response_text = (
                    f"{EMOJIS['tennis']} {EMOJIS['racket']} {EMOJIS['ball']} *Bienvenido a Club de Tenis Chocalán* {EMOJIS['ball']} {EMOJIS['racket']} {EMOJIS['tennis']}\n\n"
                    f"{EMOJIS['happy']} Hola *{socio['nombre']}*, tu número está registrado. {EMOJIS['happy']}\n\n"
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