from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import logging
import os
import pymysql
from fuzzywuzzy import fuzz  # Por si se usa más adelante
from pathlib import Path
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Datos de conexión a la base de datos
DB_HOST = os.getenv('DB_HOST', 'tu_host_mysql')  # ejemplo: 'mysql.hosting.cl'
DB_USER = os.getenv('DB_USER', 'clubdet1')
DB_PASS = os.getenv('DB_PASS', 'tu_clave_segura')
DB_NAME = os.getenv('DB_NAME', 'clubdet1_clubdetenis')

def buscar_socio_por_celular(celular):
    try:
        connection = pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASS,
            database=DB_NAME,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )

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
            nombre = socio['nombre_completo']
            return build_twiml_response(f"🙌 Hola {nombre}, tu número está registrado en el sistema.")
        else:
            return build_twiml_response("❌ No encontramos tu número en la base de datos de socios.")

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return build_twiml_response("⚠️ Error interno. Intenta más tarde.")

def build_twiml_response(message_text):
    response = MessagingResponse()
    response.message(message_text)
    return str(response), 200, {'Content-Type': 'text/xml'}

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
