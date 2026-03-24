"""Notificaciones vía Telegram bot para Palishopping."""

import logging

import requests

logger = logging.getLogger(__name__)

BOT_TOKEN = "7982922688:AAE9yeGiWOGtTHtr7VblJfyMZuUSXDBhsfQ"
CHAT_ID = "8239777724"
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"


def send_notification(text: str, parse_mode: str = "HTML") -> bool:
    """Envía un mensaje de texto vía Telegram.

    Args:
        text: Contenido del mensaje (soporta HTML por defecto).
        parse_mode: "HTML" o "Markdown".

    Returns:
        True si el mensaje se envió correctamente, False en caso de error.
    """
    try:
        resp = requests.post(
            f"{TELEGRAM_API}/sendMessage",
            json={
                "chat_id": CHAT_ID,
                "text": text,
                "parse_mode": parse_mode,
            },
            timeout=10,
        )
        resp.raise_for_status()
        logger.info("Telegram: mensaje enviado OK")
        return True
    except Exception as e:
        logger.error("Telegram: error al enviar mensaje: %s", e)
        return False


def send_photo(photo_path: str, caption: str = "") -> bool:
    """Envía una foto vía Telegram.

    Args:
        photo_path: Path al archivo de imagen.
        caption: Texto opcional debajo de la foto.

    Returns:
        True si se envió correctamente.
    """
    try:
        with open(photo_path, "rb") as f:
            resp = requests.post(
                f"{TELEGRAM_API}/sendPhoto",
                data={"chat_id": CHAT_ID, "caption": caption, "parse_mode": "HTML"},
                files={"photo": f},
                timeout=30,
            )
        resp.raise_for_status()
        logger.info("Telegram: foto enviada OK")
        return True
    except Exception as e:
        logger.error("Telegram: error al enviar foto: %s", e)
        return False
