"""Constantes, rutas y configuración global de la aplicación."""

from pathlib import Path

# ── Rutas base ────────────────────────────────────────────────────────────────

KB_ROOT = Path(__file__).resolve().parent.parent
PRODUCTOS_BASE = KB_ROOT / "productos-base"
CATALOGO_PATH = KB_ROOT / "catalogo.json"
MODELOS_PATH = KB_ROOT / "modelos.json"
BUNDLES_DIR = KB_ROOT / "bundles"
LISTINGS_DIR = KB_ROOT / "listings"
DRAFTS_DIR = LISTINGS_DIR / "drafts"
PROVEEDORES_DIR = KB_ROOT / "proveedores"

# ── Constantes de negocio ─────────────────────────────────────────────────────

FACTOR_NACIONALIZACION = 1.9
MARGEN = 2.5  # precio_venta_sugerido = costo_total * MARGEN
PROVEEDORES = ["andres", "sao-bernardo"]

BLUE_DOLLAR_API = "https://api.bluelytics.com.ar/v2/latest"

# ── Tipos de producto → prefijo SKU ──────────────────────────────────────────

TIPOS_PRODUCTO: dict[str, tuple[str, str]] = {
    "1": ("ORG-ZAP", "Organizador de zapatos"),
    "2": ("ORG-BOT", "Organizador de botas"),
    "3": ("ORG-COL", "Organizador colgante"),
    "4": ("BOL-VAC", "Bolsa al vacío"),
    "5": ("PER-ROP", "Percha ropa"),
    "6": ("CAJ-DEC", "Caja decorada"),
    "7": ("MISC",    "Otro / Misceláneo"),
    "8": ("ARM-MOD", "Armario modular"),
}

# Mapeo inverso: nombre legible → prefijo
TIPO_NOMBRE_A_PREFIJO: dict[str, str] = {
    nombre: prefijo for prefijo, nombre in TIPOS_PRODUCTO.values()
}

# ── Abreviaciones de color para SKU ──────────────────────────────────────────

COLORES_ABREV: dict[str, str] = {
    "blanco":       "BLA",
    "negro":        "NEG",
    "gris":         "GRI",
    "beige":        "BEI",
    "rosa":         "ROS",
    "rojo":         "ROJ",
    "azul":         "AZU",
    "verde":        "VER",
    "amarillo":     "AMA",
    "marron":       "MAR",
    "transparente": "TRA",
    "multicolor":   "MUL",
}

# ── Configuración de imágenes ─────────────────────────────────────────────────

IMG_CANVAS_OPTIMIZE = 1024     # px — canvas para optimización (con_fondo, listas_gemini)
IMG_CANVAS_CENTER = 1200       # px — canvas para centrado de producto
IMG_QUALITY_HIGH = 95          # JPEG — copia de originales
IMG_QUALITY_OPTIMIZE = 92      # JPEG — optimización Gemini
IMG_QUALITY_TEXT = 93           # JPEG — con texto overlay
IMG_PRODUCT_COVERAGE = 0.80    # 80% del canvas al centrar

# ── Configuración de IA ──────────────────────────────────────────────────────

CLAUDE_MODEL = "claude-sonnet-4-20250514"
TITULO_ML_MAX_CHARS = 60
DESCRIPCION_ML_MAX_CHARS = 1500

# ── Estructura de carpetas por producto ───────────────────────────────────────

PRODUCT_SUBDIRS = [
    "fotos/originales",
    "fotos/procesadas",
    "fotos/con_fondo",
    "fotos/listas_gemini",
    "fotos/con_texto",
    "fotos/gemini",
    "fotos/generadas",
    "inteligencia",
    "media",
]

# ── Extensiones de imagen soportadas ─────────────────────────────────────────

IMG_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

# ── Cookies / Credentials ────────────────────────────────────────────────────

ML_COOKIES_PATH = Path.home() / ".ml_cookies.json"
