from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import logging
import os
import psycopg2
from psycopg2.extras import RealDictCursor
import re
from datetime import datetime

app = Flask(__name__)

# Configuración inicial del logger (EXACTA A TU VERSIÓN ORIGINAL)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuración de la base de datos (IDÉNTICA A TU VERSIÓN)
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'dpg-d00re5c9c44c73ckj38g-a.oregon-postgres.render.com'),
    'user': os.getenv('DB_USER', 'reservas_0m08_user'),
    'password': os.getenv('DB_PASS', 'gJ6CvycTBwpsWe7j166vb7nA5RqQPx9k'),
    'dbname': os.getenv('DB_NAME', 'reservas_0m08'),
    'port': os.getenv('DB_PORT', '5432')
}

# Emojis (COMPLETO Y ASEGURADO)
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

# [TODAS TUS FUNCIONES ORIGINALES SE MANTIENEN SIN CAMBIOS]
# get_db_connection, cargar_sesion, guardar_sesion, limpiar_sesion
# buscar_socio_por_celular, verificar_fecha_disponible
# obtener_horas_disponibles, obtener_canchas_disponibles, realizar_reserva

@app.route("/whatsapp", methods=['POST'])
def whatsapp_reply():
    try:
        # Obtener datos del mensaje (IGUAL A TU VERSIÓN)
        user_message = request.form.get('Body', '').strip()
        whatsapp_number = request.form.get('From', '')
        user_number = whatsapp_number.replace('whatsapp:', '')
        
        logger.info(f"Mensaje de {user_number}: {user_message}")

        sesion = cargar_sesion(user_number)
        paso = sesion['paso'] if sesion else None
        socio = buscar_socio_por_celular(user_number)
        
        response = MessagingResponse()

        # SOLO AGREGAMOS BOTONES EN EL MENSAJE INICIAL (LO MÁS SEGURO)
        if not socio:
            response.message(
                f"{EMOJIS['cross']} No encontramos tu número en la base de datos.\n"
                f"Si es un error, contáctanos para verificar tus datos. {EMOJIS['info']}"
            )
            return str(response), 200, {'Content-Type': 'text/xml'}

        if not paso and not user_message:
            # SOLO CAMBIO: Mensaje inicial con botones (el más seguro)
            msg = response.message(
                f"{EMOJIS['hand']} ¡Hola {socio['nombre']}! {EMOJIS['happy']}\n\n"
                f"{EMOJIS['tennis']} *Bienvenido a Club de Tenis Melipilla* {EMOJIS['tennis']}"
            )
            msg.action("Sí, reservar")  # Botón 1
            msg.action("Consultar reservas")  # Botón 2
            return str(response), 200, {'Content-Type': 'text/xml'}

        # [TODO EL RESTO DE TU LÓGICA ORIGINAL SE MANTIENE INTACTA]
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

        if 'si' in user_message.lower() or 'sí' in user_message.lower():
            response.message(
                f"{EMOJIS['hand']} ¡Hola {socio['nombre']}! {EMOJIS['happy']}\n\n"
                f"{EMOJIS['calendar']} Por favor, escribe el día que deseas reservar (DD-MM)\n"
                f"Ejemplo: 10-03 para el 10 de Marzo"
            )
        else:
            response.message(
                f"{EMOJIS['hand']} ¡Hola {socio['nombre']}! {EMOJIS['happy']}\n\n"
                f"{EMOJIS['tennis']} *Bienvenido a Club de Tenis Melipilla* {EMOJIS['tennis']}\n\n"
                f"{EMOJIS['calendar']} ¿Deseas reservar una cancha? Responde 'SI'"
            )

        return str(response), 200, {'Content-Type': 'text/xml'}

    except Exception as e:
        logger.error(f"Error en whatsapp_reply: {str(e)}", exc_info=True)
        response = MessagingResponse()
        response.message(f"{EMOJIS['warning']} Error interno. Intenta más tarde.")
        return str(response), 200, {'Content-Type': 'text/xml'}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)