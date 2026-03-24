"""Gestión de tokens de MercadoLibre para palishopping y cajasordenadoras.

Lectura de credenciales, renovación de token vía refresh_token grant,
y funciones de acceso rápido para obtener tokens.
"""

import json
import logging
import time
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

# ── Paths de credenciales ─────────────────────────────────────────────────────

ML_CREDENTIALS_PALISHOPPING = Path(
    "/home/pepe/Proyectos/ml-scripts/config/ml_credentials_palishopping.json"
)
ML_CREDENTIALS_CAJASORDENADORAS = Path(
    "/home/pepe/Proyectos/ml-scripts/config/ml_credentials_cajasordenadoras.json"
)
ML_OAUTH_URL = "https://api.mercadolibre.com/oauth/token"

# Buffer de 5 minutos antes de expiración
_EXPIRY_BUFFER = 300


def _load_credentials(path: Path) -> dict:
    """Carga credenciales desde un archivo JSON."""
    if not path.exists():
        raise FileNotFoundError(f"Archivo de credenciales no encontrado: {path}")
    with open(path) as f:
        return json.load(f)


def _save_credentials(path: Path, creds: dict) -> None:
    """Guarda credenciales actualizadas en el archivo JSON."""
    with open(path, "w") as f:
        json.dump(creds, f, indent=2)
    logger.info("Credenciales guardadas en %s", path)


def _is_token_expired(creds: dict) -> bool:
    """Verifica si el token está expirado o próximo a expirar."""
    timestamp = creds.get("timestamp", 0)
    expires_in = creds.get("expires_in", 21600)
    return time.time() - timestamp >= (expires_in - _EXPIRY_BUFFER)


def refresh_token(credentials_path: Path) -> dict:
    """Renueva el access_token usando el refresh_token grant.

    Args:
        credentials_path: Path al archivo de credenciales JSON.

    Returns:
        Dict con las credenciales actualizadas.

    Raises:
        requests.HTTPError: Si ML rechaza el refresh.
        FileNotFoundError: Si el archivo no existe.
    """
    creds = _load_credentials(credentials_path)

    data = {
        "grant_type": "refresh_token",
        "client_id": creds["app_id"],
        "client_secret": creds["client_secret"],
        "refresh_token": creds["refresh_token"],
    }

    logger.info("Renovando token para app_id=%s...", creds["app_id"])
    response = requests.post(ML_OAUTH_URL, data=data, timeout=30)
    response.raise_for_status()

    new_data = response.json()
    creds["access_token"] = new_data["access_token"]
    creds["refresh_token"] = new_data["refresh_token"]
    creds["timestamp"] = time.time()
    creds["expires_in"] = new_data.get("expires_in", 21600)

    _save_credentials(credentials_path, creds)
    logger.info("Token renovado exitosamente")
    return creds


def get_palishopping_token(auto_refresh: bool = True) -> str:
    """Retorna el access_token de palishopping.

    Args:
        auto_refresh: Si True, renueva automáticamente si está expirado.

    Returns:
        El access_token como string.

    Raises:
        FileNotFoundError: Si el archivo de credenciales no existe.
        requests.HTTPError: Si falla el refresh.
    """
    creds = _load_credentials(ML_CREDENTIALS_PALISHOPPING)

    if auto_refresh and _is_token_expired(creds):
        logger.info("Token palishopping expirado, renovando...")
        creds = refresh_token(ML_CREDENTIALS_PALISHOPPING)

    return creds["access_token"]


def get_reader_token() -> str | None:
    """Retorna el access_token de cajasordenadoras (solo lectura).

    Este token se usa como fallback cuando el token de palishopping
    recibe un 403 (PolicyAgent) al leer ítems de competidores.

    Returns:
        El access_token o None si no hay credenciales disponibles.
    """
    try:
        creds = _load_credentials(ML_CREDENTIALS_CAJASORDENADORAS)
        return creds.get("access_token")
    except FileNotFoundError:
        logger.warning("Credenciales de cajasordenadoras no encontradas")
        return None


def get_token_status(credentials_path: Path | None = None) -> dict:
    """Retorna información de estado del token.

    Args:
        credentials_path: Path al archivo (default: palishopping).

    Returns:
        Dict con: user_id, app_id, expired (bool), expires_at (timestamp),
        seconds_remaining, timestamp.
    """
    path = credentials_path or ML_CREDENTIALS_PALISHOPPING
    try:
        creds = _load_credentials(path)
    except FileNotFoundError:
        return {"error": f"Archivo no encontrado: {path}"}

    timestamp = creds.get("timestamp", 0)
    expires_in = creds.get("expires_in", 21600)
    expires_at = timestamp + expires_in
    remaining = max(0, expires_at - time.time())

    return {
        "user_id": creds.get("user_id"),
        "app_id": creds.get("app_id"),
        "expired": _is_token_expired(creds),
        "expires_at": expires_at,
        "seconds_remaining": int(remaining),
        "timestamp": timestamp,
    }
