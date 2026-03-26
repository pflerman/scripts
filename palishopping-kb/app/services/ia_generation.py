"""Funciones de generación con Claude AI extraídas de los scripts CLI.

Lógica pura sin Rich ni input interactivo, para usar desde la GUI.
"""

import base64
import json
import logging
import os
from datetime import datetime
from pathlib import Path

from app.config import CLAUDE_MODEL

logger = logging.getLogger(__name__)


def get_anthropic_client():
    """Retorna un cliente Anthropic o None si no hay API key."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    import anthropic
    return anthropic.Anthropic(api_key=api_key)


def generar_titulo(sku: str, producto_data: dict,
                   palabras_clave: list[str] | None = None,
                   foto_path: Path | None = None) -> str:
    """Genera UN título (family_name) ML con Claude AI.

    Si foto_path se provee, usa Claude Vision para analizar la imagen
    y generar el título desde cero (sin depender del título original).
    Si no hay foto, usa los datos textuales del producto.

    producto_data puede incluir: nombre, categoria, precio, descripcion,
    fotos_count, y cualquier campo extra del scraper.
    """
    client = get_anthropic_client()
    if not client:
        raise RuntimeError("ANTHROPIC_API_KEY no configurada")

    categoria = producto_data.get("categoria", producto_data.get("tipo", ""))
    precio = producto_data.get("precio", "")
    kws = palabras_clave or producto_data.get("palabras_clave", [])

    # Contexto mínimo (categoría y precio, sin título del competidor)
    contexto_lines = []
    if categoria:
        contexto_lines.append(f"- Categoría ML: {categoria}")
    if precio:
        contexto_lines.append(f"- Precio: ${precio}")
    if kws:
        contexto_lines.append(f"- Palabras clave: {', '.join(kws)}")
    contexto = "\n".join(contexto_lines) if contexto_lines else "Sin datos adicionales."

    reglas = """Reglas de formato:
- MÁXIMO 60 caracteres (este es el family_name, ML agrega el color automáticamente)
- Formato Title Case (Primera Letra De Cada Palabra En Mayúscula)
- Incluir cantidad si aplica (ej: "x12", "6 Niveles")
- NO incluir color (ML lo agrega del atributo COLOR)
- NO incluir la marca "Palishopping" (ML la muestra aparte)
- Sin signos de puntuación, sin comas, sin emojis

IMPORTANTE: Contá los caracteres ANTES de responder. Si supera 60, acortalo.

Respondé SOLO con el título, nada más."""

    creatividad = """PROHIBIDO usar estas palabras genéricas que TODOS usan en ML:
"organizador", "organizadora", "organizadoras", "apilable", "transparente", "pack", "set", "unidades", "cajas organizadoras", "caja organizadora", "multiuso", "multifunción", "práctico", "resistente", "hogar"

EN CAMBIO, pensá como un copywriter creativo:
- ¿Cómo le diría una persona a un amigo? "che mirá este zapatero divino"
- Usá sinónimos frescos y específicos del producto real
- Ejemplos de sinónimos creativos por categoría:
  - Zapatos: zapatero, calzadero, guardazapatos, torre de zapatos, cubos exhibidores, vitrinas, módulos
  - Ropa: perchero, colgador, rack, barra, estante, roperito, porta-trajes
  - Almacenamiento: cofre, baúl, contenedor, gabinete, estante modular, cubo, celda
- Buscá ángulos de venta únicos que transmitan valor premium
- El título debe generar curiosidad y diferenciarse de la competencia"""

    # ── Con foto: Claude Vision ──────────────────────────────────────────────
    if foto_path and foto_path.exists():
        imagen_bytes = foto_path.read_bytes()
        ext = foto_path.suffix.lower()
        media_type = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png"
        imagen_b64 = base64.standard_b64encode(imagen_bytes).decode("utf-8")

        prompt_vision = f"""Esta es la foto de un producto que se vende en MercadoLibre Argentina.

Tu trabajo es crear UN título de venta ÚNICO y CREATIVO que se destaque de los miles de títulos aburridos que ya existen en ML.

{creatividad}

Contexto:
{contexto}

{reglas}"""

        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=256,
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
                    {"type": "text", "text": prompt_vision},
                ],
            }],
        )
    else:
        # ── Sin foto: fallback a texto ───────────────────────────────────────
        nombre = producto_data.get("nombre", "")
        descripcion = producto_data.get("descripcion", "")

        contexto_texto = f"- Título original de la publicación (NO copiarlo): {nombre}"
        if contexto_lines:
            contexto_texto += "\n" + contexto
        if descripcion:
            contexto_texto += f"\n- Descripción original:\n{descripcion[:500]}"

        prompt_texto = f"""Sos un copywriter creativo experto en MercadoLibre Argentina.

Información del producto:
{contexto_texto}

Tu trabajo es crear UN título de venta ÚNICO y CREATIVO que se destaque.
NO copies ni parafrasees el título original. Reinventalo completamente.

{creatividad}

{reglas}"""

        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=256,
            messages=[{"role": "user", "content": prompt_texto}],
        )

    titulo = response.content[0].text.strip()
    # Limpiar numeración si la hay
    if titulo and titulo[0].isdigit() and len(titulo) > 2 and titulo[1] in ".)-":
        titulo = titulo[2:].strip()
    # Limpiar comillas que a veces agrega el modelo
    titulo = titulo.strip('"\'')
    # Si respondió con múltiples líneas, tomar solo la primera
    if "\n" in titulo:
        titulo = titulo.split("\n")[0].strip()

    # Detectar respuesta descriptiva (Claude "pensando en voz alta")
    _descriptive = ("," in titulo or len(titulo) > 60)
    if _descriptive:
        logger.info("Título parece descriptivo (%d chars), pidiendo resumen...", len(titulo))
        retry = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=128,
            messages=[{"role": "user", "content": (
                f"Convertí esto en un título de venta para MercadoLibre Argentina.\n"
                f"MÁXIMO 60 caracteres. Formato Title Case. Sin comas ni puntuación. "
                f"Sin color ni marca. Solo el título, nada más.\n\n"
                f"Texto: {titulo}"
            )}],
        )
        titulo = retry.content[0].text.strip().strip('"\'')
        if "\n" in titulo:
            titulo = titulo.split("\n")[0].strip()

    # Recortar por última palabra completa si supera 60 chars
    if len(titulo) > 60:
        titulo = titulo[:60].rsplit(" ", 1)[0]

    return titulo


def generar_descripcion(sku: str, producto_data: dict,
                        info_adicional: dict | None = None,
                        foto_path: Path | None = None) -> str:
    """Genera UNA descripción ML con Claude AI.

    Si foto_path se provee, usa Claude Vision para describir el producto
    desde la imagen. Si no hay foto, usa los datos textuales.

    producto_data puede incluir: nombre, categoria, precio, descripcion,
    fotos_count, titulo_ml, y cualquier campo extra del scraper.
    """
    client = get_anthropic_client()
    if not client:
        raise RuntimeError("ANTHROPIC_API_KEY no configurada")

    categoria = producto_data.get("categoria", producto_data.get("tipo", ""))
    precio = producto_data.get("precio", "")
    titulo_ml = producto_data.get("titulo_ml", "")
    kws = producto_data.get("palabras_clave", [])

    # Contexto mínimo (sin descripción del competidor cuando hay foto)
    contexto_lines = []
    if titulo_ml:
        contexto_lines.append(f"- Título ML que usamos: {titulo_ml}")
    if categoria:
        contexto_lines.append(f"- Categoría ML: {categoria}")
    if precio:
        contexto_lines.append(f"- Precio: ${precio}")
    if kws:
        contexto_lines.append(f"- Palabras clave: {', '.join(kws)}")

    info = info_adicional or {}
    if info:
        extras = []
        if info.get("medidas"):
            extras.append(f"Medidas: {info['medidas']}")
        if info.get("material"):
            extras.append(f"Material: {info['material']}")
        if info.get("cantidad"):
            extras.append(f"Contenido del pack: {info['cantidad']}")
        if info.get("destacar"):
            extras.append(f"Característica especial: {info['destacar']}")
        if extras:
            contexto_lines.append("- Info adicional: " + " | ".join(extras))

    contexto = "\n".join(contexto_lines) if contexto_lines else "Sin datos adicionales."

    criterios = """Criterios de escritura:
- Estilo de vendedor argentino: cercano, entusiasta pero creíble, como si le recomendaras algo a un amigo
- Arrancá con una frase que enganche y haga click emocional, no con "Este producto..."
- Después meté los detalles concretos del producto (medidas, material, cantidad) solo si los ves o los tenés
- Cerrá con un llamado a la acción breve y natural
- Máximo 1500 caracteres
- NO inventes datos que no se vean en la foto ni estén en el contexto
- Evitá palabras gastadas: "práctico", "ideal", "perfecto", "excelente calidad", "no te lo pierdas"
- Sin emojis, sin mayúsculas raras, sin signos de exclamación excesivos
- Sin HTML ni markdown, sin asteriscos ni símbolos especiales
- Solo párrafos de texto plano separados por líneas en blanco
- Nada de listas con viñetas: todo redactado en prosa continua

Respondé ÚNICAMENTE con la descripción, sin títulos ni explicación."""

    # ── Con foto: Claude Vision ──────────────────────────────────────────────
    if foto_path and foto_path.exists():
        imagen_bytes = foto_path.read_bytes()
        ext = foto_path.suffix.lower()
        media_type = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png"
        imagen_b64 = base64.standard_b64encode(imagen_bytes).decode("utf-8")

        prompt_vision = f"""Esta es la foto de un producto que se vende en MercadoLibre Argentina.

Escribí UNA descripción de venta que enganche, basándote en lo que ves en la imagen.
Mencioná lo que realmente se ve: material, tamaño, diseño, cantidad de piezas, para qué sirve.
NO inventes datos. NO describas la imagen como tal. Escribí como un vendedor que le cuenta a un amigo por qué este producto está bueno.
Evitá frases genéricas como "excelente calidad", "ideal para", "no te lo pierdas". Sé específico y original.

Contexto:
{contexto}

{criterios}"""

        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
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
                    {"type": "text", "text": prompt_vision},
                ],
            }],
        )
    else:
        # ── Sin foto: fallback a texto ───────────────────────────────────────
        nombre = producto_data.get("nombre", "")
        descripcion_orig = producto_data.get("descripcion", "")

        contexto_texto = f"- Título original: {nombre}"
        if contexto_lines:
            contexto_texto += "\n" + contexto
        if descripcion_orig:
            contexto_texto += f"\n- Descripción original del competidor:\n{descripcion_orig[:800]}"

        prompt_texto = f"""Sos un copywriter creativo de MercadoLibre Argentina. Generá UNA descripción de venta que enganche.

Información del producto:
{contexto_texto}

Tu trabajo:
1. Extraé las características reales: medidas, material, cantidad, uso
2. Escribí una descripción específica, original y con personalidad
3. NO copies la descripción original, reescribila completamente con tu estilo
4. Arrancá con algo que enganche, no con "Este producto..."

{criterios}"""

        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt_texto}],
        )

    return response.content[0].text.strip()


def _parse_hype_response(response_text: str) -> tuple[str, str]:
    """Extrae frase y prompt de la respuesta de Claude con formato FRASE:/PROMPT:.

    Returns:
        (frase, prompt_gemini). Si no encuentra el formato, fallback razonable.
    """
    text = response_text.strip()
    upper = text.upper()
    idx_frase = upper.find("FRASE:")
    idx_prompt = upper.find("PROMPT:")

    if idx_frase != -1 and idx_prompt != -1 and idx_prompt > idx_frase:
        frase = text[idx_frase + len("FRASE:"):idx_prompt].strip().strip('"\'')
        prompt = text[idx_prompt + len("PROMPT:"):].strip()
        if frase and prompt:
            return frase, prompt

    # Fallback: no encontró el formato
    return text[:50].strip(), text


def generar_prompt_hype_strong(producto_info: dict,
                               frases_usadas: list[str] | None = None) -> tuple[str, str]:
    """Genera un prompt creativo y único para hype fuerte usando Claude.

    Returns:
        (frase elegida, prompt para Gemini).
    """
    client = get_anthropic_client()
    if not client:
        raise RuntimeError("ANTHROPIC_API_KEY no configurada")

    titulo = producto_info.get("titulo", "Producto")
    categoria = producto_info.get("categoria", "")
    precio = producto_info.get("precio", "")

    bloque_usadas = ""
    if frases_usadas:
        bloque_usadas = f"\nFRASES YA USADAS EN ESTA PUBLICACIÓN (NO las repitas bajo ningún concepto): {', '.join(frases_usadas)}\n"

    prompt = f"""\
Generá un prompt para una IA de imágenes (Gemini) que va a recibir una foto de producto y tiene que agregarle elementos gráficos de venta AGRESIVOS.

REGLAS PARA EL PROMPT QUE GENERES:
1. Inventá una frase NUEVA y ÚNICA de 3-6 palabras en español argentino. PROHIBIDO usar: 'Elegancia Diaria', 'Calidad Premium', 'Oferta Imperdible', 'Orden Que Inspira', 'Tu Clóset Te Agradece'. Inventá algo que NUNCA se haya usado.
{bloque_usadas}\
2. Describí EXACTAMENTE qué elementos gráficos agregar. NO digas 'agregá un banner'. Sé ESPECÍFICO: 'Agregá un sticker circular 3D color verde neón en la esquina superior derecha con la frase X en tipografía bold blanca con sombra negra' o 'Agregá una cinta diagonal roja desde la esquina superior izquierda hasta el centro con texto dorado metálico que diga X' o 'Agregá un globo de texto estilo cómic en amarillo eléctrico con borde negro grueso en la parte inferior que diga X'
3. Especificá colores EXACTOS, no 'colores vibrantes'. Elegí UNA paleta concreta: verde neón + negro, fucsia + dorado, celeste eléctrico + blanco, naranja fluo + violeta, etc.
4. Especificá ubicación EXACTA: 'esquina superior derecha', 'franja diagonal de esquina a esquina', 'banner inferior ocupando el 20% de la imagen', etc.
5. El elemento debe ser GRANDE y VISIBLE, no un textito chiquito en una esquina.

PROHIBIDO mencionar precios, descuentos con números, o montos en pesos. En vez de precio usá frases como: 'Envío Gratis', 'Más de 1000 Vendidos', 'Garantía Total', 'Pack x12', 'Últimas Unidades', 'MercadoLíder', o cualquier beneficio que no sea un número de precio.

Producto: {titulo}
Categoría: {categoria}

FORMATO DE RESPUESTA:
FRASE: [la frase exacta que elegiste]
PROMPT: [el prompt completo para Gemini, largo y detallado, mínimo 100 palabras]"""

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=512,
        temperature=1.0,
        messages=[{"role": "user", "content": prompt}],
    )
    return _parse_hype_response(response.content[0].text)


def generar_prompt_hype_soft(producto_info: dict,
                             frases_usadas: list[str] | None = None) -> tuple[str, str]:
    """Genera un prompt creativo y único para hype suave usando Claude.

    Returns:
        (frase elegida, prompt para Gemini).
    """
    client = get_anthropic_client()
    if not client:
        raise RuntimeError("ANTHROPIC_API_KEY no configurada")

    titulo = producto_info.get("titulo", "Producto")
    categoria = producto_info.get("categoria", "")
    precio = producto_info.get("precio", "")

    bloque_usadas = ""
    if frases_usadas:
        bloque_usadas = f"\nFRASES YA USADAS EN ESTA PUBLICACIÓN (NO las repitas bajo ningún concepto): {', '.join(frases_usadas)}\n"

    prompt = f"""\
Generá un prompt para una IA de imágenes (Gemini) que va a recibir una foto de producto y tiene que agregarle un BANNER DE VENTA ELEGANTE pero con presencia.

REGLAS:
1. Inventá una frase NUEVA de 3-5 palabras. PROHIBIDO: 'Elegancia Diaria', 'Calidad Premium', 'Orden Que Inspira', 'Tu Espacio Perfecto', 'Simple y Genial'.
{bloque_usadas}\
2. El texto NO debe ser letras sueltas flotando. Debe tener un SOPORTE VISUAL: una franja semi-transparente, un rectángulo con bordes redondeados, una etiqueta tipo price tag, un sello circular elegante, un marco fino con fondo difuminado. ALGO que le dé cuerpo al texto.
3. Elegí UN estilo tipográfico específico y UN color que NO sea azul ni gris.
4. Elegí UNA ubicación diferente cada vez con un detalle decorativo.
5. El resultado debe verse como una publicación profesional de Instagram o una revista, no como texto pegado encima.

PROHIBIDO mencionar precios, descuentos con números, o montos en pesos. En vez de precio usá frases como: 'Envío Gratis', 'Más de 1000 Vendidos', 'Garantía Total', 'Pack x12', 'Últimas Unidades', 'MercadoLíder', o cualquier beneficio que no sea un número de precio.

Producto: {titulo}
Categoría: {categoria}

FORMATO DE RESPUESTA:
FRASE: [la frase exacta que elegiste]
PROMPT: [el prompt completo para Gemini]"""

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=512,
        temperature=1.0,
        messages=[{"role": "user", "content": prompt}],
    )
    return _parse_hype_response(response.content[0].text)


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
