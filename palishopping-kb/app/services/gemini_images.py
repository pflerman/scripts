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


def _apply_hype(foto_path: Path, prompt: str, dest_dir: Path, prefix: str) -> Path:
    """Aplica un prompt de hype a una foto usando Gemini. Fallback: copia original."""
    from google.genai import types

    foto_path = Path(foto_path)
    output = dest_dir / f"{prefix}_{foto_path.name}"

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
        logger.info("Hype %s agregado: %s (%d KB)", prefix, output, len(img_bytes_out) // 1024)
        return output
    except Exception as e:
        logger.warning("Error hype %s en %s: %s — usando original", prefix, foto_path.name, e)
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(foto_path, output)
        return output


def add_hype_strong(foto_path: Path, producto_info: dict, dest_dir: Path) -> Path:
    """Agrega banner de venta agresivo estilo ML a una foto.

    Usa Claude para generar un prompt único y creativo, luego Gemini lo ejecuta.
    """
    from app.services.ia_generation import generar_prompt_hype_strong

    try:
        prompt = generar_prompt_hype_strong(producto_info)
        prompt += "\n\nNO tapar el producto principal. Devolvé la imagen con los cambios."
        logger.info("Prompt hype strong generado por Claude: %s", prompt[:120])
    except Exception as e:
        logger.warning("Error generando prompt con Claude: %s — usando fallback", e)
        titulo = producto_info.get("titulo", "Producto")
        prompt = (
            f"Agregale un banner de venta llamativo estilo MercadoLibre a esta foto de {titulo}. "
            f"Frase corta de impacto, colores vibrantes, estilo vendedor agresivo. "
            f"NO tapar el producto principal. Devolvé la imagen con los cambios."
        )

    return _apply_hype(foto_path, prompt, dest_dir, "strong")


def add_hype_soft(foto_path: Path, producto_info: dict, dest_dir: Path) -> Path:
    """Agrega texto de venta sutil y elegante a una foto.

    Usa Claude para generar un prompt único y creativo, luego Gemini lo ejecuta.
    """
    from app.services.ia_generation import generar_prompt_hype_soft

    try:
        prompt = generar_prompt_hype_soft(producto_info)
        prompt += "\n\nNO tapar el producto. Devolvé la imagen con el texto agregado."
        logger.info("Prompt hype soft generado por Claude: %s", prompt[:120])
    except Exception as e:
        logger.warning("Error generando prompt con Claude: %s — usando fallback", e)
        titulo = producto_info.get("titulo", "Producto")
        prompt = (
            f"Agregale un texto de venta sutil y elegante a esta foto de {titulo}. "
            f"Frase corta sofisticada, tipografía elegante, estilo premium. "
            f"NO tapar el producto. Devolvé la imagen con el texto agregado."
        )

    return _apply_hype(foto_path, prompt, dest_dir, "soft")


def add_hype_batch(
    fotos: list[Path],
    cantidad_strong: int,
    cantidad_soft: int,
    producto_info: dict,
    dest_dir: Path,
    callback=None,
) -> list[Path]:
    """Aplica hype strong y soft a fotos elegidas al azar.

    Returns:
        Lista reordenada: primero sin hype, después soft, después strong.
    """
    if (cantidad_strong + cantidad_soft) <= 0 or not fotos:
        return list(fotos)

    cantidad_strong = min(cantidad_strong, len(fotos))
    cantidad_soft = min(cantidad_soft, len(fotos) - cantidad_strong)
    dest_dir.mkdir(parents=True, exist_ok=True)

    all_indices = list(range(len(fotos)))

    # Elegir al azar cuáles llevan strong
    indices_strong = set(random.sample(all_indices, cantidad_strong))
    # De las restantes, elegir soft
    remaining = [i for i in all_indices if i not in indices_strong]
    indices_soft = set(random.sample(remaining, cantidad_soft))

    indices_clean = [i for i in all_indices if i not in indices_strong and i not in indices_soft]

    msg = (f"Hype batch: {cantidad_strong} strong, {cantidad_soft} soft, "
           f"{len(indices_clean)} sin hype de {len(fotos)} fotos")
    logger.info(msg)
    if callback:
        callback(msg)

    # Procesar cada foto
    processed: dict[int, Path] = {}
    for i, foto in enumerate(fotos):
        if i in indices_strong:
            msg = f"Hype FUERTE foto {i + 1}/{len(fotos)}..."
            logger.info(msg)
            if callback:
                callback(msg)
            processed[i] = add_hype_strong(foto, producto_info, dest_dir)
        elif i in indices_soft:
            msg = f"Hype SUAVE foto {i + 1}/{len(fotos)}..."
            logger.info(msg)
            if callback:
                callback(msg)
            processed[i] = add_hype_soft(foto, producto_info, dest_dir)
        else:
            output = dest_dir / f"clean_{foto.name}"
            shutil.copy2(foto, output)
            processed[i] = output

    # Reordenar: sin hype primero, después soft, después strong
    resultado = (
        [processed[i] for i in indices_clean]
        + [processed[i] for i in sorted(indices_soft)]
        + [processed[i] for i in sorted(indices_strong)]
    )

    msg = (f"Hype completado: {len(indices_clean)} limpias + "
           f"{cantidad_soft} soft + {cantidad_strong} strong")
    logger.info(msg)
    if callback:
        callback(msg)

    return resultado
