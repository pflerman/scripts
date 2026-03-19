"""Validaciones de datos de negocio."""

from app.config import COLORES_ABREV


def abreviar_color(color: str) -> str:
    """Convierte nombre de color a abreviatura de 3 letras para SKU."""
    c = color.strip().lower()
    for nombre, abrev in COLORES_ABREV.items():
        if c.startswith(nombre[:4]):
            return abrev
    return c[:3].upper()


def normalizar_talle(talle: str) -> str:
    """Normaliza talle para uso en SKU (max 6 chars, sin espacios)."""
    t = talle.strip().upper()
    return t.replace(" ", "").replace("/", "-")[:6]


def generar_sku(prefijo: str, modelo_cod: str, color: str, talle: str) -> str:
    """Genera SKU con formato TIPO-MODELO-COLOR-TALLE."""
    partes = [prefijo, modelo_cod]
    color_abrev = abreviar_color(color)
    if color_abrev:
        partes.append(color_abrev)
    talle_norm = normalizar_talle(talle)
    if talle_norm:
        partes.append(talle_norm)
    return "-".join(partes)


def validar_precio(texto: str) -> float | None:
    """Intenta parsear un texto como precio. Retorna None si es inválido."""
    try:
        limpio = texto.replace(",", ".").replace("$", "").replace(" ", "").strip()
        valor = float(limpio)
        return valor if valor >= 0 else None
    except (ValueError, AttributeError):
        return None


def validar_entero_positivo(texto: str) -> int | None:
    """Intenta parsear como entero positivo. Retorna None si es inválido."""
    limpio = texto.replace(",", "").replace(".", "").strip()
    if limpio.isdigit() and int(limpio) > 0:
        return int(limpio)
    return None
