"""Publicación de ítems en MercadoLibre para palishopping.

Modelo UP (User Products): cada color es un ítem separado, agrupados
por family_name. NO usar title ni variations.

Funciones: subir imagen, publicar ítem, agregar descripción.
"""

import json
import logging
import re
import time
import unicodedata
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from PIL import Image

from app.services.ml_auth import get_palishopping_token

logger = logging.getLogger(__name__)

ML_BASE_URL = "https://api.mercadolibre.com"

# Atributos extra por categoría
_ZAPATERO_EXTRA = [
    {"id": "MANUFACTURER", "value_name": "Palishopping"},
    {"id": "HEIGHT", "value_name": "14 cm", "value_struct": {"number": 14, "unit": "cm"}},
    {"id": "WIDTH", "value_name": "33 cm", "value_struct": {"number": 33, "unit": "cm"}},
    {"id": "DEPTH", "value_name": "20 cm", "value_struct": {"number": 20, "unit": "cm"}},
    {"id": "REQUIRES_ASSEMBLY", "value_id": "242084", "value_name": "No"},
    {"id": "INCLUDES_ASSEMBLY_MANUAL", "value_id": "242084", "value_name": "No"},
]

EXTRA_ATTRS_BY_CATEGORY: dict[str, list[dict]] = {
    "MLA9475": [{"id": "IS_FACTORY_KIT", "value_id": "242084", "value_name": "No"}],
    "MLA436427": _ZAPATERO_EXTRA,
    "MLA74590": _ZAPATERO_EXTRA,
}

# Color value_ids para MercadoLibre
COLOR_VALUE_IDS: dict[str, str] = {
    "Blanco": "52055",
    "Negro": "52049",
    "Rosa": "51994",
    "Turquesa": "283160",
    "Gris": "283165",
    "Combinado Blanco Negro": "63068037",
}


def _ml_request(method: str, path: str, payload: dict | None = None) -> dict:
    """HTTP request genérico a la API de ML."""
    token = get_palishopping_token()
    url = f"{ML_BASE_URL}{path}"
    body = json.dumps(payload).encode() if payload else None

    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method=method,
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def _ensure_min_size(image_path: Path, min_px: int = 800, target_px: int = 1200) -> Path:
    """Si la imagen es menor a min_px x min_px, la redimensiona a target_px x target_px
    con padding blanco manteniendo proporción. Sobreescribe el archivo original.

    Returns:
        El mismo image_path (modificado in-place si fue necesario).
    """
    with Image.open(image_path) as img:
        w, h = img.size
        if w >= min_px and h >= min_px:
            return image_path

        logger.info("Foto %s es %dx%d (< %dpx), redimensionando a %dx%d con padding...",
                     image_path.name, w, h, min_px, target_px, target_px)

        # Escalar para que el lado mayor ocupe target_px
        scale = min(target_px / w, target_px / h)
        new_w, new_h = int(w * scale), int(h * scale)
        resized = img.resize((new_w, new_h), Image.LANCZOS)

        # Centrar sobre fondo blanco
        canvas = Image.new("RGB", (target_px, target_px), (255, 255, 255))
        offset_x = (target_px - new_w) // 2
        offset_y = (target_px - new_h) // 2
        canvas.paste(resized, (offset_x, offset_y))

        canvas.save(image_path, quality=95)
        logger.info("Foto redimensionada: %dx%d → %dx%d", w, h, target_px, target_px)

    return image_path


def upload_image(image_path: Path) -> str:
    """Sube una imagen local a ML vía multipart/form-data.

    Verifica que la imagen tenga al menos 800x800px. Si es más chica,
    la redimensiona a 1200x1200 con padding blanco.

    Args:
        image_path: Path al archivo de imagen.

    Returns:
        URL de la imagen en ML (máxima resolución disponible).

    Raises:
        RuntimeError: Si ML no devuelve URL.
    """
    _ensure_min_size(image_path)

    token = get_palishopping_token()
    boundary = uuid.uuid4().hex

    image_bytes = image_path.read_bytes()
    filename = image_path.name
    mime = "image/png" if image_path.suffix.lower() == ".png" else "image/jpeg"

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: {mime}\r\n\r\n"
    ).encode() + image_bytes + f"\r\n--{boundary}--\r\n".encode()

    req = urllib.request.Request(
        f"{ML_BASE_URL}/pictures/items/upload",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Accept": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())

    # Obtener la URL de mayor resolución
    variations = result.get("variations", [])
    if variations:
        def _area(v: dict) -> int:
            try:
                w, h = v.get("size", "0x0").split("x")
                return int(w) * int(h)
            except (ValueError, AttributeError):
                return 0
        best = max(variations, key=_area)
        url = best.get("secure_url") or best.get("url", "")
    else:
        url = result.get("secure_url") or result.get("url", "")

    if not url:
        raise RuntimeError(f"ML no devolvió URL de imagen. Respuesta: {result}")

    logger.info("Imagen subida: %s", url[:80])
    return url


def build_family_name(titulo: str) -> str:
    """Construye family_name a partir del título (max 60 chars).

    Args:
        titulo: Título original del ítem.

    Returns:
        family_name truncado a 60 caracteres.
    """
    return titulo[:60]


def clean_description(texto: str) -> str:
    """Limpia la descripción: ASCII, sin emojis, con marca Palishopping.

    Args:
        texto: Descripción original.

    Returns:
        Texto limpio en ASCII con firma de Palishopping.
    """
    if not texto:
        return "Vendido por Palishopping."

    normalizado = unicodedata.normalize("NFKD", texto)
    ascii_texto = normalizado.encode("ascii", "ignore").decode("ascii")
    ascii_texto = re.sub(r"[^\x20-\x7E\n\r\t]", "", ascii_texto)
    ascii_texto = re.sub(r" {2,}", " ", ascii_texto)
    ascii_texto = re.sub(r"\n{3,}", "\n\n", ascii_texto)
    ascii_texto = ascii_texto.strip()

    if ascii_texto:
        return ascii_texto + "\n\nVendido por Palishopping."
    return "Vendido por Palishopping."


def publish_item(
    family_name: str,
    category_id: str,
    precio: float,
    picture_urls: list[str],
    descripcion: str = "",
    stock: int = 1,
    color_name: str = "Blanco",
    color_value_id: str | None = None,
) -> dict:
    """Publica un ítem en ML con modelo UP (family_name, sin title).

    Args:
        family_name: Nombre de familia (max 60 chars). ML construye el
            título como family_name + " " + COLOR.
        category_id: ID de categoría ML (ej: "MLA414192").
        precio: Precio en ARS.
        picture_urls: URLs de fotos ya subidas a ML.
        descripcion: Descripción en texto plano.
        stock: Cantidad disponible (default 1).
        color_name: Nombre del color (default "Blanco").
        color_value_id: value_id del color. Si None, se busca automáticamente.

    Returns:
        Dict con la respuesta de ML (incluye id, permalink, status, etc.).

    Raises:
        RuntimeError: Si ML rechaza la publicación.
    """
    if color_value_id is None:
        color_value_id = COLOR_VALUE_IDS.get(color_name, "52055")

    attributes = [
        {"id": "BRAND", "value_name": "Palishopping"},
        {"id": "MODEL", "value_name": family_name[:40]},
        {"id": "COLOR", "value_id": color_value_id, "value_name": color_name},
        {"id": "VALUE_ADDED_TAX", "value_id": "48405909", "value_name": "21 %"},
        {"id": "IMPORT_DUTY", "value_id": "49553239", "value_name": "0 %"},
    ]

    # Atributos extra por categoría
    attributes.extend(EXTRA_ATTRS_BY_CATEGORY.get(category_id, []))

    payload: dict = {
        "family_name": family_name,
        "category_id": category_id,
        "price": round(precio),
        "currency_id": "ARS",
        "available_quantity": stock,
        "buying_mode": "buy_it_now",
        "condition": "new",
        "listing_type_id": "gold_special",
        "attributes": attributes,
    }

    if picture_urls:
        payload["pictures"] = [{"source": u} for u in picture_urls]

    logger.info(
        "Publicando: family_name=%s, cat=%s, precio=$%d, fotos=%d, color=%s",
        family_name, category_id, precio, len(picture_urls), color_name,
    )

    try:
        item = _ml_request("POST", "/items", payload)
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        raise RuntimeError(f"ML rechazó la publicación (HTTP {e.code}): {body}") from e

    item_id = item.get("id", "N/A")
    logger.info("Ítem publicado: %s", item_id)

    # Agregar descripción
    if descripcion and item.get("id"):
        _add_description(item["id"], descripcion)

    return item


def _add_description(item_id: str, descripcion: str) -> None:
    """Agrega descripción al ítem (POST, fallback PUT)."""
    desc_payload = {"plain_text": descripcion}
    desc_path = f"/items/{item_id}/description"

    for intento, delay in enumerate([0, 1, 2]):
        time.sleep(delay)
        try:
            _ml_request("POST", desc_path, desc_payload)
            logger.info("Descripción agregada a %s", item_id)
            return
        except urllib.error.HTTPError as e:
            if e.code == 400:
                try:
                    _ml_request("PUT", desc_path, desc_payload)
                    logger.info("Descripción actualizada en %s", item_id)
                    return
                except urllib.error.HTTPError:
                    if intento < 2:
                        continue
                    logger.warning("No se pudo agregar descripción a %s", item_id)
            else:
                logger.warning("Error al agregar descripción (HTTP %d)", e.code)
                return


def update_item(item_id: str, updates: dict) -> dict:
    """Actualiza campos de un ítem publicado (PUT /items/{id}).

    Args:
        item_id: MLA ID del ítem.
        updates: Dict con campos a actualizar (price, available_quantity, status, etc.).

    Returns:
        Respuesta de ML.
    """
    return _ml_request("PUT", f"/items/{item_id}", updates)
