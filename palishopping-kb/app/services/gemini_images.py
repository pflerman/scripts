"""Generación y mejora de imágenes con Gemini (Nano Banana 2).

Modelo: gemini-2.5-flash-image
Requiere: GEMINI_API_KEY en env o en ~/Proyectos/gemini-test/.env
"""

import logging
import os
import random
import shutil
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from pathlib import Path

logger = logging.getLogger(__name__)

MODEL = "gemini-2.5-flash-image"
TIMEOUT = 90  # segundos por imagen

# Prompt default para mejorar fotos de producto (fondo blanco profesional)
DEFAULT_PRODUCT_PROMPT = """\
You are a professional e-commerce product photographer.
Using the attached image as a visual reference to understand what the product looks like,
generate a brand new high-quality product photo with:
- Pure white background (#FFFFFF), no shadows, no gradients
- The product centered, complete, fully visible
- Professional studio lighting, soft and even
- Photorealistic, sharp, high resolution
- NO text, NO logos, NO watermarks, NO brands, NO people, NO hands
- Minimalist catalog style, like Apple or IKEA product photos
Do NOT copy the original photo. Generate a clean, professional new version.\
"""


def _get_client():
    """Crea un cliente de Gemini con la API key disponible."""
    from google import genai

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        env_path = Path("/home/pepe/Proyectos/gemini-test/.env")
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith("GEMINI_API_KEY="):
                    api_key = line.split("=", 1)[1].strip()
                    break
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY no encontrada en el entorno ni en gemini-test/.env")
    return genai.Client(api_key=api_key)


def _extract_image(response) -> bytes:
    """Extrae los bytes de imagen de la respuesta de Gemini."""
    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            return part.inline_data.data
    raise RuntimeError("Gemini no devolvió imagen en la respuesta")


def generate_image(prompt: str, output_path: Path) -> Path:
    """Genera una imagen a partir de un prompt de texto.

    Args:
        prompt: Descripción de la imagen a generar.
        output_path: Donde guardar la imagen resultante.

    Returns:
        Path al archivo generado.

    Raises:
        RuntimeError: Si Gemini no responde o hace timeout.
    """
    from google.genai import types

    output_path = Path(output_path)
    client = _get_client()

    def _call():
        return client.models.generate_content(
            model=MODEL,
            contents=[types.Content(parts=[types.Part.from_text(text=prompt)])],
            config=types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"]),
        )

    with ThreadPoolExecutor(max_workers=1) as ex:
        future = ex.submit(_call)
        try:
            response = future.result(timeout=TIMEOUT)
        except FuturesTimeoutError:
            raise RuntimeError(f"Gemini timeout ({TIMEOUT}s)")

    img_bytes = _extract_image(response)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(img_bytes)
    logger.info("Imagen generada: %s (%d KB)", output_path, len(img_bytes) // 1024)
    return output_path


def enhance_image(img_path: Path, output_path: Path,
                  prompt: str | None = None) -> Path:
    """Mejora/transforma una imagen existente usando Gemini.

    Args:
        img_path: Imagen de referencia.
        output_path: Donde guardar el resultado.
        prompt: Instrucciones para Gemini (default: foto de producto profesional).

    Returns:
        Path al archivo generado.

    Raises:
        RuntimeError: Si Gemini no responde o hace timeout.
    """
    from google.genai import types

    img_path = Path(img_path)
    output_path = Path(output_path)
    prompt = prompt or DEFAULT_PRODUCT_PROMPT

    img_bytes = img_path.read_bytes()
    suffix = img_path.suffix.lower()
    mime = "image/jpeg" if suffix in (".jpg", ".jpeg") else "image/png"

    client = _get_client()

    def _call():
        return client.models.generate_content(
            model=MODEL,
            contents=[
                types.Content(parts=[
                    types.Part.from_bytes(data=img_bytes, mime_type=mime),
                    types.Part.from_text(text=prompt),
                ])
            ],
            config=types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"]),
        )

    with ThreadPoolExecutor(max_workers=1) as ex:
        future = ex.submit(_call)
        try:
            response = future.result(timeout=TIMEOUT)
        except FuturesTimeoutError:
            raise RuntimeError(f"Gemini timeout ({TIMEOUT}s)")

    img_bytes_out = _extract_image(response)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(img_bytes_out)
    logger.info("Imagen mejorada: %s (%d KB)", output_path, len(img_bytes_out) // 1024)
    return output_path


def enhance_photos_batch(
    photos: list[Path],
    dest_dir: Path,
    prompt: str | None = None,
    max_workers: int = 3,
    callback=None,
) -> list[tuple[Path, bool, str]]:
    """Mejora múltiples fotos en paralelo con fallback a redimensionado.

    Args:
        photos: Lista de paths a fotos originales.
        dest_dir: Carpeta destino para las fotos mejoradas.
        prompt: Prompt personalizado (default: producto fondo blanco).
        max_workers: Workers paralelos (default 3).
        callback: Función callback(msg: str) para reportar progreso.

    Returns:
        Lista de tuplas (output_path, gemini_ok, info_msg) en orden original.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from PIL import Image

    dest_dir.mkdir(parents=True, exist_ok=True)
    results: list[tuple[Path, bool, str] | None] = [None] * len(photos)

    def _process(idx: int, photo: Path) -> tuple[int, Path, bool, str]:
        output = dest_dir / f"mejorada_{idx + 1}.png"
        try:
            enhance_image(photo, output, prompt)
            size_kb = output.stat().st_size // 1024
            return idx, output, True, f"{size_kb} KB"
        except Exception as e:
            # Fallback: redimensionar original a 1200x1200
            try:
                img = Image.open(photo).convert("RGB")
                fondo = Image.new("RGB", (1200, 1200), (255, 255, 255))
                img.thumbnail((1200, 1200), Image.LANCZOS)
                offset = ((1200 - img.width) // 2, (1200 - img.height) // 2)
                fondo.paste(img, offset)
                output.parent.mkdir(parents=True, exist_ok=True)
                fondo.save(output, format="PNG", optimize=True)
                return idx, output, False, str(e)
            except Exception as e2:
                return idx, output, False, f"fallback también falló: {e2}"

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_process, i, p): i
            for i, p in enumerate(photos)
        }
        for future in as_completed(futures):
            idx, output, ok, info = future.result()
            results[idx] = (output, ok, info)
            msg = (
                f"Foto {idx + 1}: mejorada ({info})"
                if ok
                else f"Foto {idx + 1}: fallback ({info})"
            )
            logger.info(msg)
            if callback:
                callback(msg)

    return [r for r in results if r is not None]


def add_hype_text(foto_path: Path, producto_info: dict, dest_dir: Path) -> Path:
    """Agrega texto hype overlay a una foto de producto usando Gemini.

    Args:
        foto_path: Foto (ya mejorada o original) a la que agregar texto.
        producto_info: Dict con titulo, categoria, precio del producto.
        dest_dir: Carpeta destino.

    Returns:
        Path a la foto con texto hype (o la original si falla).
    """
    from google.genai import types

    foto_path = Path(foto_path)
    output = dest_dir / f"hype_{foto_path.name}"

    titulo = producto_info.get("titulo", "Producto")
    categoria = producto_info.get("categoria", "")
    precio = producto_info.get("precio", "")

    prompt = f"""\
Tenés esta foto de un producto de MercadoLibre Argentina. Necesito que le agregues un BANNER DE VENTA llamativo y profesional, como los que usan los vendedores TOP de MercadoLibre.

El banner debe incluir:
- Una frase CORTA de impacto (3-6 palabras): 'ENVÍO GRATIS HOY', 'OFERTA IMPERDIBLE', 'LLEGÓ LO QUE BUSCABAS', 'TU HOGAR MERECE ESTO', etc.
- Elementos gráficos llamativos: estrellas, destellos, flechas, iconos de envío, badges de descuento, sellos de garantía, cintas de oferta
- Colores vibrantes que contrasten: rojo, amarillo, naranja para urgencia; dorado para premium; verde para envío gratis
- Puede ser una franja diagonal, un sello circular, un banner en esquina, una cinta cruzada, un sticker estilo 'SALE'
- Opcionalmente agregar un personaje o ilustración simple: una mano señalando, un pulgar arriba, un ícono de camión de envío, estrellas de rating
- El estilo debe ser VENDEDOR AGRESIVO de marketplace, no elegante ni minimalista
- NO tapar el producto principal, usar las esquinas, bordes o zonas libres de la foto

Producto: {titulo}
Categoría: {categoria}
Precio: ${precio}

IMPORTANTE: Que el banner se vea como publicidad REAL de MercadoLibre, no como un texto plano sobre la foto. Pensá en los banners que ves en las publicaciones más vendidas de ML.

Devolvé la imagen con el banner agregado."""

    img_bytes = foto_path.read_bytes()
    suffix = foto_path.suffix.lower()
    mime = "image/jpeg" if suffix in (".jpg", ".jpeg") else "image/png"

    client = _get_client()

    def _call():
        return client.models.generate_content(
            model=MODEL,
            contents=[
                types.Content(parts=[
                    types.Part.from_bytes(data=img_bytes, mime_type=mime),
                    types.Part.from_text(text=prompt),
                ])
            ],
            config=types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"]),
        )

    try:
        with ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(_call)
            response = future.result(timeout=TIMEOUT)

        img_bytes_out = _extract_image(response)
        dest_dir.mkdir(parents=True, exist_ok=True)
        output.write_bytes(img_bytes_out)
        logger.info("Hype text agregado: %s (%d KB)", output, len(img_bytes_out) // 1024)
        return output
    except Exception as e:
        logger.warning("Error agregando hype text a %s: %s — usando original", foto_path.name, e)
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(foto_path, output)
        return output


def add_hype_text_batch(
    fotos: list[Path],
    cantidad_hype: int,
    producto_info: dict,
    dest_dir: Path,
    callback=None,
) -> list[Path]:
    """Agrega texto hype a una cantidad aleatoria de fotos del lote.

    Args:
        fotos: Lista de fotos (mejoradas o originales).
        cantidad_hype: Cuántas fotos llevan hype (0 = ninguna).
        producto_info: Dict con titulo, categoria, precio.
        dest_dir: Carpeta destino para las fotos con hype.
        callback: Función callback(msg) para progreso.

    Returns:
        Lista de paths en el mismo orden, con hype aplicado a las elegidas.
    """
    if cantidad_hype <= 0 or not fotos:
        return list(fotos)

    cantidad_hype = min(cantidad_hype, len(fotos))
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Elegir al azar cuáles llevan hype
    indices_hype = set(random.sample(range(len(fotos)), cantidad_hype))
    msg = f"Agregando texto hype a {cantidad_hype} de {len(fotos)} fotos..."
    logger.info(msg)
    if callback:
        callback(msg)

    resultado: list[Path] = []
    for i, foto in enumerate(fotos):
        if i in indices_hype:
            msg = f"Hype foto {i + 1}/{len(fotos)}..."
            logger.info(msg)
            if callback:
                callback(msg)
            resultado.append(add_hype_text(foto, producto_info, dest_dir))
        else:
            # Copiar tal cual
            output = dest_dir / f"hype_{foto.name}"
            shutil.copy2(foto, output)
            resultado.append(output)

    msg = f"Hype completado: {cantidad_hype} fotos con texto, {len(fotos) - cantidad_hype} sin cambios"
    logger.info(msg)
    if callback:
        callback(msg)

    return resultado
