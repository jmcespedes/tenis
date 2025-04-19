from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import logging
import os
import psycopg2
from psycopg2.extras import RealDictCursor
import re
from datetime import datetime

app = Flask(__name__)

# Configuración inicial del logger (MANTENIENDO TU CONFIGURACIÓN ORIGINAL)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# [El resto de tu configuración inicial se mantiene IGUAL]
# [Tus funciones auxiliares (get_db_connection, cargar_sesion, etc.) se mantienen IGUAL]

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

        # Función auxiliar para botones (NUEVA pero compatible)
        def agregar_botones(mensaje, opciones):
            msg = response.message(mensaje)
            for opcion in opciones:
                msg.action(opcion)
            return response

        # [TODA TU LÓGICA ORIGINAL SE MANTIENE IGUAL HASTA DONDE NECESITES BOTONES]

        if paso == 'esperando_hora':
            hora = user_message
            canchas = obtener_canchas_disponibles(sesion['fecha'], hora)
            if not canchas:
                response.message(f"{EMOJIS['cross']} No hay canchas disponibles a las {hora}")
            else:
                guardar_sesion(user_number, 'esperando_cancha', sesion['fecha'], hora)
                # Versión con botones (opcional)
                if len(canchas) <= 3:  # Solo usamos botones si hay pocas canchas
                    return agregar_botones(
                        f"{EMOJIS['court']} Canchas disponibles a las {hora}:",
                        [f"Cancha {c}" for c in canchas]
                    )
                else:  # Mantenemos tu formato original si hay muchas
                    response.message(
                        f"{EMOJIS['court']} Canchas disponibles a las {hora}:\n\n"
                        f"{', '.join([f'Cancha {c}' for c in canchas])}\n\n"
                        f"Por favor, escribe el número de cancha que deseas (ej: 1)"
                    )
            return str(response), 200, {'Content-Type': 'text/xml'}

        # [EL RESTO DE TU LÓGICA SE MANTIENE IGUAL]

        if socio:
            if 'si' in user_message.lower() or 'sí' in user_message.lower():
                response.message(
                    f"{EMOJIS['hand']} ¡Hola {socio['nombre']}! {EMOJIS['happy']}\n\n"
                    f"{EMOJIS['calendar']} Por favor, escribe el día que deseas reservar (DD-MM)\n"
                    f"Ejemplo: 10-03 para el 10 de Marzo"
                )
            else:
                # Solo agregamos botones aquí sin cambiar nada más
                if not user_message:  # Mensaje inicial
                    return agregar_botones(
                        f"{EMOJIS['hand']} ¡Hola! {EMOJIS['happy']}\n\n"
                        f"{EMOJIS['tennis']} *Bienvenido a Club de Tenis Melipilla* {EMOJIS['tennis']}",
                        ["Sí", "No"]
                    )
                else:
                    response.message(
                        f"{EMOJIS['hand']} ¡Hola! {EMOJIS['happy']}\n\n"
                        f"{EMOJIS['tennis']} *Bienvenido a Club de Tenis Melipilla* {EMOJIS['tennis']}\n\n"
                        f"{EMOJIS['calendar']} ¿Deseas reservar una cancha? Responde 'SI'"
                    )
        else:
            response.message(
                f"{EMOJIS['cross']} No encontramos tu número en la base de datos.\n"
                f"Si es un error, contáctanos para verificar tus datos. {EMOJIS['info']}"
            )

        return str(response), 200, {'Content-Type': 'text/xml'}

    except Exception as e:
        logger.error(f"Error: {e}")  # Ahora el logger está definido
        response = MessagingResponse()
        response.message(f"{EMOJIS['warning']} Error interno. Intenta más tarde.")
        return str(response), 200, {'Content-Type': 'text/xml'}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)