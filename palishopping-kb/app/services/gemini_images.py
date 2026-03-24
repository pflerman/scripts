"""Generación y mejora de imágenes con Gemini (Nano Banana 2).

Modelo: gemini-2.5-flash-image
Requiere: GEMINI_API_KEY en env o en ~/Proyectos/gemini-test/.env
"""

import logging
import os
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
