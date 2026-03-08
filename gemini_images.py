"""
Módulo centralizado para generación de imágenes con Nano Banana 2.
Modelo: gemini-3.1-flash-image-preview
API: generate_content con response_modalities=["IMAGE", "TEXT"]

Funciones:
  generar_imagen(prompt, output_path)          — texto → imagen
  mejorar_imagen(img_path, prompt, output_path) — imagen + texto → imagen mejorada
"""
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from pathlib import Path

from google import genai
from google.genai import types

MODEL = "gemini-3.1-flash-image-preview"
TIMEOUT = 90  # segundos


def _get_client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        # Fallback: leer del .env de gemini-test
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
    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            return part.inline_data.data
    raise RuntimeError("Nano Banana 2 no devolvió imagen")


def generar_imagen(prompt: str, output_path: Path) -> Path:
    """
    Genera una imagen a partir de un prompt de texto.
    Guarda el resultado en output_path y lo retorna.
    """
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
            raise RuntimeError(f"Nano Banana 2 timeout ({TIMEOUT}s)")

    img_bytes = _extract_image(response)
    output_path.write_bytes(img_bytes)
    return output_path


def mejorar_imagen(img_path: Path, prompt: str, output_path: Path) -> Path:
    """
    Mejora/transforma una imagen existente usando un prompt de texto.
    Guarda el resultado en output_path y lo retorna.
    """
    img_path = Path(img_path)
    output_path = Path(output_path)
    client = _get_client()

    img_bytes = img_path.read_bytes()
    suffix = img_path.suffix.lower()
    mime = "image/jpeg" if suffix in (".jpg", ".jpeg") else "image/png"

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
            raise RuntimeError(f"Nano Banana 2 timeout ({TIMEOUT}s)")

    img_bytes_out = _extract_image(response)
    output_path.write_bytes(img_bytes_out)
    return output_path
