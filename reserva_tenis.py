from flask import Flask, request, abort
from twilio.twiml.messaging_response import MessagingResponse
from twilio.request_validator import RequestValidator
import logging
import os
import pymysql
from functools import wraps

# Configuración básica de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuración de la base de datos (usar variables de entorno en producción)
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'mysql.clubdetenismelipilla.cl'),
    'user': os.getenv('DB_USER', 'clubdet1_jmc'),
    'password': os.getenv('DB_PASS', 'sebaisi.01'),
    'database': os.getenv('DB_NAME', 'clubdet1_clubdetenis'),
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}

# Decorador para validar peticiones de Twilio
def validate_twilio_request(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        validator = RequestValidator(os.getenv('TWILIO_AUTH_TOKEN'))
        
        # Validar la firma de Twilio
        if not validator.validate(
            request.url,
            request.form,
            request.headers.get('X-Twilio-Signature', '')
        ):
            logger.warning("Intento de acceso no autorizado")
            abort(403)
        
        return f(*args, **kwargs)
    return decorated_function

def normalizar_numero(celular):
    """Normaliza números en formato +56912345678 o whatsapp:+56912345678"""
    return ''.join(filter(str.isdigit, celular.split(':')[-1]))

def get_db_connection():
    """Establece conexión a la base de datos"""
    return pymysql.connect(**DB_CONFIG)

@app.route("/")
def health_check():
    """Endpoint para verificar que el servidor está activo"""
    return "Servidor activo. Usa /whatsapp para Twilio", 200

@app.route("/whatsapp", methods=['POST'])
@validate_twilio_request
def whatsapp_reply():
    try:
        # Obtener y normalizar número
        user_number = request.form.get('From', '')
        numero_normalizado = normalizar_numero(user_number)
        logger.info(f"Mensaje recibido de: {numero_normalizado}")

        # Buscar en la base de datos
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                sql = "SELECT nombre_completo FROM socios WHERE celular LIKE %s"
                cursor.execute(sql, (f"%{numero_normalizado}%",))
                socio = cursor.fetchone()

        if socio:
            respuesta = f"🙌 Hola {socio['nombre_completo']}, tu número está registrado."
        else:
            respuesta = "❌ No encontramos tu número en nuestra base de datos."

        return build_twiml_response(respuesta)

    except pymysql.Error as e:
        logger.error(f"Error de base de datos: {e}")
        return build_twiml_response("⚠️ Error al consultar nuestros registros.")
    except Exception as e:
        logger.error(f"Error inesperado: {e}")
        return build_twiml_response("⚠️ Error interno. Por favor intenta más tarde.")

def build_twiml_response(message_text):
    """Construye respuesta compatible con Twilio"""
    response = MessagingResponse()
    response.message(message_text)
    return str(response), 200, {'Content-Type': 'text/xml'}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)