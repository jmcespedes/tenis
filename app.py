from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import logging
import os
import psycopg2
from psycopg2.extras import RealDictCursor
import re
from datetime import datetime

app = Flask(__name__)

# [Tus configuraciones iniciales, logging, DB_CONFIG, EMOJIS, etc. se mantienen igual]

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

        # Función auxiliar para enviar mensajes con botones
        def enviar_con_botones(mensaje, opciones):
            msg = response.message(mensaje)
            for opcion in opciones:
                msg.action(opcion)
            return response

        if paso == 'esperando_hora':
            hora = user_message
            canchas = obtener_canchas_disponibles(sesion['fecha'], hora)
            if not canchas:
                response.message(f"{EMOJIS['cross']} No hay canchas disponibles a las {hora}")
            else:
                guardar_sesion(user_number, 'esperando_cancha', sesion['fecha'], hora)
                # Modificado para usar botones
                mensaje = f"{EMOJIS['court']} Canchas disponibles a las {hora}:\n\n"
                mensaje += "\n".join([f"• Cancha {c}" for c in canchas])
                mensaje += "\n\nSelecciona una cancha:"
                return enviar_con_botones(mensaje, [f"Cancha {c}" for c in canchas])
            return str(response), 200, {'Content-Type': 'text/xml'}

        elif paso == 'esperando_cancha':
            cancha = re.search(r'\d+', user_message)  # Extrae el número de cancha aunque venga con botón
            if not cancha:
                response.message(f"{EMOJIS['cross']} Por favor selecciona una cancha válida")
                return str(response), 200, {'Content-Type': 'text/xml'}
                
            cancha = cancha.group()
            reserva = realizar_reserva(sesion['fecha'], sesion['hora'], cancha, socio)
            if reserva:
                # Mensaje de confirmación con opciones adicionales
                mensaje = (
                    f"{EMOJIS['check']} ¡Reserva confirmada!\n\n"
                    f"{EMOJIS['calendar']} Día: {sesion['fecha']}\n"
                    f"{EMOJIS['clock']} Hora: {sesion['hora']}\n"
                    f"{EMOJIS['court']} Cancha: {cancha}\n\n"
                    "¿Necesitas algo más?"
                )
                limpiar_sesion(user_number)
                return enviar_con_botones(mensaje, ["Nueva reserva", "Cancelar reserva", "No, gracias"])
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

            # Modificado para usar botones de hora
            mensaje = f"{EMOJIS['calendar']} Horarios disponibles para el {user_message}:"
            guardar_sesion(user_number, 'esperando_hora', fecha)
            return enviar_con_botones(
                mensaje,
                [f"{hora['hora_inicial']} a {hora['hora_final']}" for hora in horas]
            )

        if socio:
            if 'si' in user_message.lower() or 'sí' in user_message.lower() or 'reservar' in user_message.lower():
                response.message(
                    f"{EMOJIS['hand']} ¡Hola {socio['nombre']}! {EMOJIS['happy']}\n\n"
                    f"{EMOJIS['calendar']} Por favor, escribe el día que deseas reservar (DD-MM)\n"
                    f"Ejemplo: 10-03 para el 10 de Marzo"
                )
            else:
                # Mensaje inicial con botones
                return enviar_con_botones(
                    f"{EMOJIS['hand']} ¡Hola {socio['nombre']}! {EMOJIS['happy']}\n\n"
                    f"{EMOJIS['tennis']} *Bienvenido a Club de Tenis Melipilla* {EMOJIS['tennis']}\n\n"
                    "¿Qué deseas hacer?",
                    ["Reservar cancha", "Consultar reservas", "Ayuda"]
                )
        else:
            # Mensaje para no socios con opciones
            return enviar_con_botones(
                f"{EMOJIS['warning']} No encontramos tu número en la base de datos.\n"
                "¿Qué deseas hacer?",
                ["Verificar mi número", "Contactar al club", "Registrarme"]
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

