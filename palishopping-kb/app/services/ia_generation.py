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


def generar_prompt_hype_strong(producto_info: dict) -> str:
    """Genera un prompt creativo y único para hype fuerte usando Claude."""
    client = get_anthropic_client()
    if not client:
        raise RuntimeError("ANTHROPIC_API_KEY no configurada")

    titulo = producto_info.get("titulo", "Producto")
    categoria = producto_info.get("categoria", "")
    precio = producto_info.get("precio", "")

    prompt = f"""\
Generá UN prompt creativo para agregarle un banner de venta a una foto de producto de MercadoLibre Argentina.

El prompt va a ser enviado a una IA de generación de imágenes (Gemini) que recibe la foto del producto y tiene que agregarle elementos gráficos de venta.

IMPORTANTE: Sé ÚNICO y DIFERENTE cada vez. NUNCA repitas:
- NO uses 'Elegancia Diaria', 'Calidad Premium', 'Oferta Imperdible' — esas frases ya están quemadas
- NO uses siempre rojo y amarillo — variá: neón, holográfico, degradé púrpura-rosa, verde lima, dorado metálico, celeste eléctrico
- NO uses siempre banners rectangulares — probá: stickers 3D, sellos de cera, cintas de regalo, explosiones de confetti, marcos polaroid, etiquetas colgantes, globos de texto comic

Inventá una frase NUEVA de 3-6 palabras que sea:
- Fresca, argentina, con actitud
- Ejemplos de ESTILO (no copies estas, inventá nuevas): 'Dale Vida a Tu Placard', 'Tu Casa Te Lo Pide', 'Dejá de Buscar', 'Mirá Cómo Queda', 'Esto Es Lo Tuyo', 'Llegó Para Quedarse', 'No Lo Vas a Creer'

El prompt debe especificar:
- La frase exacta a usar
- Un estilo visual ESPECÍFICO y diferente (no genérico)
- Ubicación en la foto (variá: esquina, centro-abajo, diagonal, flotando, borde superior)
- Colores específicos (elegí una paleta concreta, no 'colores vibrantes')
- Un elemento gráfico concreto (no 'estrellas y badges' genérico)

Producto: {titulo}
Categoría: {categoria}
Precio: ${precio}

Respondé SOLO con el prompt para Gemini, nada más."""

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


def generar_prompt_hype_soft(producto_info: dict) -> str:
    """Genera un prompt creativo y único para hype suave usando Claude."""
    client = get_anthropic_client()
    if not client:
        raise RuntimeError("ANTHROPIC_API_KEY no configurada")

    titulo = producto_info.get("titulo", "Producto")
    categoria = producto_info.get("categoria", "")
    precio = producto_info.get("precio", "")

    prompt = f"""\
Generá UN prompt creativo para agregarle un texto de venta SUTIL a una foto de producto de MercadoLibre Argentina.

IMPORTANTE: Sé ÚNICO cada vez. NUNCA repitas 'Elegancia Diaria' ni 'Calidad Premium'.

Inventá una frase NUEVA de 3-5 palabras que sea sofisticada y premium.
- Ejemplos de ESTILO (no copies, inventá nuevas): 'Tu Momento Merece Esto', 'Simple y Genial', 'Hecho Para Vos', 'Lo Que Faltaba', 'Dale Ese Toque'

El prompt debe especificar:
- La frase exacta
- Tipografía elegante (variá: serif clásica, script manuscrita, sans-serif fina, art deco)
- Color específico de la paleta (variá: dorado rosa, verde salvia, azul medianoche, terracota, malva)
- Ubicación precisa y diferente cada vez
- Un detalle sutil: sombra, borde fino, subrayado, marco mínimo

Producto: {titulo}
Categoría: {categoria}
Precio: ${precio}

Respondé SOLO con el prompt para Gemini, nada más."""

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


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
