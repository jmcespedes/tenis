from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import logging
import os
import psycopg2
from psycopg2.extras import RealDictCursor

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

@app.route("/whatsapp", methods=['POST'])
def whatsapp_reply():
    """Endpoint para respuestas de WhatsApp"""
    try:
        # El número de Twilio ya viene en formato whatsapp:+569XXXXXXXX
        whatsapp_number = request.form.get('From', '')
        logger.info(f"Número recibido de Twilio: {whatsapp_number}")
        
        # Extraer solo la parte del número (+569XXXXXXXX)
        user_number = whatsapp_number.replace('whatsapp:', '')
        
        # Buscar socio en BD
        socio = buscar_socio_por_celular(user_number)
        
        if socio:
            logger.info(f"Socio encontrado: {socio['nombre']}")
            response_text = (
                f"🎾 *Bienvenido a Club de Tenis Chocalán* 🎾\n\n"
                f"🙌 Hola *{socio['nombre']}*, tu número está registrado.\n\n"
                f"📅 ¿Deseas reservar una cancha?"
            )
        else:
            logger.warning(f"Número no encontrado: {user_number}")
            response_text = (
                "🚫 No encontramos tu número en la base de datos.\n"
                "Si es un error, contáctanos para verificar tus datos."
            )
            
        response = MessagingResponse()
        response.message(response_text)
        return str(response), 200, {'Content-Type': 'text/xml'}
        
    except Exception as e:
        logger.error(f"Error: {e}")
        response = MessagingResponse()
        response.message("⚠️ Error interno. Intenta más tarde.")
        return str(response), 200, {'Content-Type': 'text/xml'}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)