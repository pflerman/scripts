"""Funciones de generación con Claude AI extraídas de los scripts CLI.

Lógica pura sin Rich ni input interactivo, para usar desde la GUI.
"""

import base64
import json
import logging
import os
from datetime import datetime
from pathlib import Path

from app.config import CLAUDE_MODEL, PRODUCTOS_BASE, TITULO_ML_MAX_CHARS

logger = logging.getLogger(__name__)


def get_anthropic_client():
    """Retorna un cliente Anthropic o None si no hay API key."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    import anthropic
    return anthropic.Anthropic(api_key=api_key)


def generar_titulos(sku: str, producto_data: dict,
                    palabras_clave: list[str] | None = None) -> list[str]:
    """Genera 10 títulos ML con Claude AI. Retorna lista de títulos."""
    client = get_anthropic_client()
    if not client:
        raise RuntimeError("ANTHROPIC_API_KEY no configurada")

    nombre = producto_data.get("nombre", "")
    tipo = producto_data.get("tipo", "")
    color = producto_data.get("variante", {}).get("color", "")
    talle = producto_data.get("variante", {}).get("talle", "")
    kws = palabras_clave or producto_data.get("palabras_clave", [])

    prompt = f"""Generá exactamente 10 títulos para una publicación en MercadoLibre Argentina.

Producto:
- Nombre: {nombre}
- Tipo: {tipo}
- Color: {color}
- Talle/Tamaño: {talle if talle else "no aplica"}
- Palabras clave: {", ".join(kws) if kws else "ninguna especificada"}

Reglas estrictas:
- Cada título debe tener MÁXIMO 60 caracteres (contarlos con cuidado)
- Usar la mayor cantidad de caracteres posible dentro del límite
- Optimizados para búsqueda en MercadoLibre Argentina
- Sin signos de puntuación, sin caracteres especiales, sin emojis, sin comas
- No usar mayúsculas innecesarias (solo primera letra de sustantivos propios)
- Mezclar palabras clave con variaciones creativas y términos de búsqueda populares
- Variar el orden y estructura entre títulos para cubrir distintas búsquedas

Respondé ÚNICAMENTE con los 10 títulos, uno por línea, sin numeración ni prefijos."""

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    titulos = [linea.strip() for linea in raw.splitlines() if linea.strip()]
    # Limpiar numeración
    titulos_limpios = []
    for t in titulos:
        if t and t[0].isdigit() and len(t) > 2 and t[1] in ".)-":
            t = t[2:].strip()
        titulos_limpios.append(t)

    return titulos_limpios[:10]


def generar_descripciones(sku: str, producto_data: dict,
                          info_adicional: dict | None = None) -> list[str]:
    """Genera 3 descripciones ML con Claude AI. Retorna lista de descripciones."""
    client = get_anthropic_client()
    if not client:
        raise RuntimeError("ANTHROPIC_API_KEY no configurada")

    nombre = producto_data.get("nombre", "")
    tipo = producto_data.get("tipo", "")
    color = producto_data.get("variante", {}).get("color", "")
    talle = producto_data.get("variante", {}).get("talle", "")
    titulo = producto_data.get("titulo_ml", "")
    kws = producto_data.get("palabras_clave", [])
    notas = producto_data.get("notas", "")
    info = info_adicional or {}

    extras = []
    if info.get("medidas"):
        extras.append(f"- Medidas: {info['medidas']}")
    if info.get("material"):
        extras.append(f"- Material: {info['material']}")
    if info.get("cantidad"):
        extras.append(f"- Contenido del pack: {info['cantidad']}")
    if info.get("destacar"):
        extras.append(f"- Característica especial: {info['destacar']}")
    extras_str = "\n".join(extras) if extras else "No se especificaron datos adicionales."

    prompt = f"""Generá exactamente 3 descripciones diferentes para una publicación en MercadoLibre Argentina.

Datos del producto:
- Nombre: {nombre}
- Tipo: {tipo}
- Color: {color}
- Talle/Tamaño: {talle if talle else "no especificado"}
- Título ML: {titulo if titulo else "no definido aún"}
- Palabras clave: {", ".join(kws) if kws else "ninguna"}
- Notas internas: {notas if notas else "ninguna"}

Información adicional:
{extras_str}

Criterios de escritura:
- Estilo de vendedor argentino: cálido, directo, confiable, sin exagerar
- Estructura: párrafo de apertura + lista de puntos destacados + cierre con llamado a la acción breve
- Máximo 1500 caracteres por descripción
- Incluir las palabras clave de forma natural, sin forzar
- Sin emojis, sin mayúsculas raras, sin signos de exclamación excesivos
- Sin HTML ni markdown, sin asteriscos ni símbolos especiales
- Solo párrafos de texto plano separados por líneas en blanco
- Nada de listas: todo redactado en prosa continua
- Cada versión debe tener un enfoque diferente: una más funcional, una más emocional, una más informativa

Respondé ÚNICAMENTE con las 3 descripciones separadas por esta línea exacta:
---DESCRIPCION---

No pongas numeración, títulos ni nada antes de cada descripción."""

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    partes = [p.strip() for p in raw.split("---DESCRIPCION---") if p.strip()]
    return partes[:3]


def generar_prompts_gemini(sku: str, foto_path: Path) -> list[dict]:
    """Genera prompts Gemini desde una foto usando Claude Vision.
    Retorna lista de {id, ambiente, prompt}.
    """
    client = get_anthropic_client()
    if not client:
        raise RuntimeError("ANTHROPIC_API_KEY no configurada")

    with open(foto_path, "rb") as f:
        imagen_bytes = f.read()
    imagen_b64 = base64.standard_b64encode(imagen_bytes).decode("utf-8")

    ext = foto_path.suffix.lower()
    media_type = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png"

    system_prompt = """Sos un experto en fotografía de producto para e-commerce en Argentina.
Generás prompts en inglés para Gemini Image Generation (AI Studio)
optimizados para productos de organización del hogar vendidos en MercadoLibre.
Cada prompt debe ser detallado, creativo y realista."""

    user_prompt = """Analizá esta foto de producto y generá 5 prompts variados para generar fotos lifestyle en AI Studio.
Cada prompt debe especificar: ambiente, iluminación, estilo fotográfico y detalles de escena.
Variá los ambientes: placard, habitación, entrada de casa, living, fondo de estudio.
Respondé SOLO con JSON válido, sin texto extra, sin markdown, sin backticks:
{"prompts": [{"id": 1, "ambiente": "...", "prompt": "..."}, ...]}"""

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=2048,
        system=system_prompt,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": imagen_b64,
                    },
                },
                {"type": "text", "text": user_prompt},
            ],
        }],
    )

    raw = response.content[0].text.strip()
    data = json.loads(raw)
    return data.get("prompts", [])
