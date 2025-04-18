from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import logging
import os
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Datos de conexión a la base de datos PostgreSQL (Render)
DB_HOST = os.getenv('DB_HOST', 'dpg-d00re5c9c44c73ckj38g-a.oregon-postgres.render.com')
DB_USER = os.getenv('DB_USER', 'reservas_0m08_user')
DB_PASS = os.getenv('DB_PASS', 'gJ6CvycTBwpsWe7j166vb7nA5RqQPx9k')
DB_NAME = os.getenv('DB_NAME', 'reservas_0m08')
DB_PORT = os.getenv('DB_PORT', '5432')

def buscar_socio_por_celular(celular):
    try:
        connection = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASS,
            dbname=DB_NAME,
            cursor_factory=RealDictCursor
        )

        with connection:
            with connection.cursor() as cursor:
                sql = "SELECT * FROM socios WHERE celular LIKE %s"
                cursor.execute(sql, ('%' + celular + '%',))
                result = cursor.fetchone()
                return result

    except Exception as e:
        logger.error(f"Error al conectar a la base de datos: {e}")
        return None

@app.route("/whatsapp", methods=['POST'])
def whatsapp_reply():
    try:
        user_number = request.form.get('From', '').replace('whatsapp:', '')
        logger.info(f"Número recibido: {user_number}")

        socio = buscar_socio_por_celular(user_number)

        if socio:
            nombre = socio['nombre']
            return build_twiml_response(
                f"🎾 *Bienvenido a Club de Tenis Chocalán* 🎾\n\n🙌 Hola *{nombre}*, tu número está registrado en el sistema.\n\n📅 ¿Deseas reservar una cancha?"
            )
        else:
            return build_twiml_response(
                "🚫 No encontramos tu número en la base de datos de socios.\nSi crees que esto es un error, contáctanos para verificar tus datos."
            )

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return build_twiml_response("⚠️ Error interno. Intenta más tarde.")

def build_twiml_response(message_text):
    response = MessagingResponse()
    response.message(message_text)
    return str(response), 200, {'Content-Type': 'text/xml'}

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))