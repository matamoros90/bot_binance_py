"""
Expo Push Notifications — Módulo para enviar push notifications via Expo Push API.
V5.10: Archivo NUEVO — no modifica nada existente del bot.
"""
import os
import json
import requests

# Archivo donde se almacena el token de push del dispositivo
PUSH_TOKEN_FILE = os.path.join(
    os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__))),
    ".expo_push_token"
)

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


def guardar_push_token(token: str):
    """Guarda el Expo Push Token recibido del dispositivo."""
    try:
        with open(PUSH_TOKEN_FILE, "w") as f:
            f.write(token.strip())
    except Exception as e:
        print(f"⚠️ Error guardando push token: {e}")


def obtener_push_token() -> str | None:
    """Lee el Expo Push Token almacenado."""
    try:
        if os.path.exists(PUSH_TOKEN_FILE):
            with open(PUSH_TOKEN_FILE, "r") as f:
                token = f.read().strip()
                return token if token else None
    except Exception:
        pass
    return None


def enviar_push_notification(titulo: str, cuerpo: str, datos: dict | None = None):
    """
    Envía una push notification al dispositivo usando Expo Push API.
    
    Args:
        titulo: Título de la notificación
        cuerpo: Cuerpo/contenido de la notificación
        datos: Datos adicionales (JSON) para la app
    """
    token = obtener_push_token()
    if not token:
        return False

    try:
        payload = {
            "to": token,
            "title": titulo,
            "body": cuerpo,
            "sound": "default",
            "priority": "high",
            "channelId": "trading",
        }
        if datos:
            payload["data"] = datos

        response = requests.post(
            EXPO_PUSH_URL,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=10,
        )
        return response.status_code == 200
    except Exception as e:
        print(f"⚠️ Error enviando push notification: {e}")
        return False
