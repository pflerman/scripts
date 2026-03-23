"""Funciones de procesamiento de fotos extraídas de scripts/gestionar_fotos.py.

Estas funciones son la lógica pura (sin Rich ni input interactivo),
para ser usadas tanto desde la GUI como desde los scripts CLI.
"""

import logging
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from app.config import IMG_EXTENSIONS, PRODUCTOS_BASE

logger = logging.getLogger(__name__)


# ── Helpers ──────────────────────────────────────────────────────────────────

def listar_fotos(directorio: Path) -> list[Path]:
    """Retorna las fotos en directorio ordenadas por nombre."""
    if not directorio.exists():
        return []
    return sorted(
        f for f in directorio.iterdir()
        if f.is_file() and f.suffix.lower() in IMG_EXTENSIONS
    )


def contar_fotos_por_subcarpeta(sku: str) -> dict[str, int]:
    """Retorna {subcarpeta: cantidad} para las carpetas de fotos de un producto."""
    base = PRODUCTOS_BASE / sku / "fotos"
    subcarpetas = ["originales", "procesadas", "con_fondo",
                   "listas_gemini", "con_texto", "gemini"]
    return {sub: len(listar_fotos(base / sub)) for sub in subcarpetas}


def copiar_imagen_a_jpg(src: Path, dest: Path) -> None:
    """Copia src a dest, convirtiendo a JPEG si es necesario."""
    if src.suffix.lower() in {".jpg", ".jpeg"}:
        shutil.copy2(src, dest)
    else:
        img = Image.open(src).convert("RGB")
        img.save(dest, "JPEG", quality=95)


def importar_fotos(archivos: list[Path], dir_originales: Path) -> list[str]:
    """Importa fotos a originales/. Retorna lista de mensajes de resultado."""
    dir_originales.mkdir(parents=True, exist_ok=True)
    existentes = listar_fotos(dir_originales)
    nums = []
    for f in existentes:
        try:
            nums.append(int(f.stem))
        except ValueError:
            pass
    offset = max(nums) if nums else len(existentes)

    resultados = []
    for i, src in enumerate(archivos, start=offset + 1):
        dest = dir_originales / f"{i:02d}.jpg"
        try:
            copiar_imagen_a_jpg(src, dest)
            resultados.append(f"OK: {src.name} → {dest.name}")
        except Exception as e:
            resultados.append(f"ERROR: {src.name}: {e}")
    return resultados


# ── Procesamiento: quitar fondo (Pipeline B) ────────────────────────────────

def _rembg_disponible() -> bool:
    try:
        import rembg  # noqa: F401
        return True
    except ImportError:
        return False


def _remover_fondo_rembg(src: Path) -> Image.Image:
    import rembg
    from io import BytesIO
    data = src.read_bytes()
    result = rembg.remove(data)
    return Image.open(BytesIO(result)).convert("RGBA")


def _remover_fondo_pillow(src: Path) -> Image.Image:
    return Image.open(src).convert("RGBA")


def _componer_fondo_blanco(img_rgba: Image.Image) -> Image.Image:
    fondo = Image.new("RGB", img_rgba.size, (255, 255, 255))
    fondo.paste(img_rgba, mask=img_rgba.split()[3])
    return fondo


def procesar_fondo_blanco(fotos: list[Path], dir_procesadas: Path,
                          callback=None) -> tuple[int, list[str]]:
    """Pipeline B paso 1: originales → procesadas (fondo blanco).
    callback(msg) se llama por cada foto procesada.
    Retorna (n_procesadas, mensajes).
    """
    dir_procesadas.mkdir(parents=True, exist_ok=True)
    usar_rembg = _rembg_disponible()
    procesadas = 0
    mensajes = []

    if not usar_rembg:
        mensajes.append("rembg no disponible, usando Pillow (sin quitar fondo)")

    for foto in fotos:
        dest = dir_procesadas / foto.name
        try:
            if usar_rembg:
                img_rgba = _remover_fondo_rembg(foto)
            else:
                img_rgba = _remover_fondo_pillow(foto)
            img_rgb = _componer_fondo_blanco(img_rgba)
            img_rgb.save(dest, "JPEG", quality=95)
            msg = f"OK: {foto.name} → procesadas/{dest.name}"
            mensajes.append(msg)
            procesadas += 1
            if callback:
                callback(msg)
        except Exception as e:
            msg = f"ERROR: {foto.name}: {e}"
            mensajes.append(msg)
            if callback:
                callback(msg)

    return procesadas, mensajes


# ── Optimización: autocrop + sharpen + pad (Pipelines A y B) ─────────────────

def _autocrop(img: Image.Image, umbral: int = 245) -> Image.Image:
    import numpy as np
    arr = np.array(img)
    mascara = (arr[:, :, 0] < umbral) | (arr[:, :, 1] < umbral) | (arr[:, :, 2] < umbral)
    filas = np.any(mascara, axis=1)
    cols = np.any(mascara, axis=0)
    if not filas.any():
        return img
    r_min, r_max = int(np.where(filas)[0][0]), int(np.where(filas)[0][-1])
    c_min, c_max = int(np.where(cols)[0][0]), int(np.where(cols)[0][-1])
    h, w = arr.shape[:2]
    margen_y = max(int(h * 0.02), 4)
    margen_x = max(int(w * 0.02), 4)
    r_min = max(0, r_min - margen_y)
    r_max = min(h - 1, r_max + margen_y)
    c_min = max(0, c_min - margen_x)
    c_max = min(w - 1, c_max + margen_x)
    return img.crop((c_min, r_min, c_max + 1, r_max + 1))


def _pad_a_cuadrado(img: Image.Image, size: int = 1024) -> Image.Image:
    img.thumbnail((size, size), Image.LANCZOS)
    fondo = Image.new("RGB", (size, size), (255, 255, 255))
    offset_x = (size - img.width) // 2
    offset_y = (size - img.height) // 2
    fondo.paste(img, (offset_x, offset_y))
    return fondo


def _optimizar_pillow(path_src: Path, path_dest: Path) -> None:
    """autocrop + sharpening + contraste + saturación + pad 1024x1024."""
    img = Image.open(path_src).convert("RGB")
    img = _autocrop(img)
    img = img.filter(ImageFilter.UnsharpMask(radius=1.5, percent=130, threshold=2))
    img = ImageEnhance.Contrast(img).enhance(1.1)
    img = ImageEnhance.Brightness(img).enhance(1.03)
    img = ImageEnhance.Color(img).enhance(1.12)
    img = _pad_a_cuadrado(img, size=1024)
    img.save(path_dest, "JPEG", quality=92, optimize=True)


def optimizar_para_gemini(fotos: list[Path], dir_destino: Path,
                          callback=None) -> tuple[int, list[str]]:
    """Pipeline B paso 2: procesadas → listas_gemini.
    También se usa para Pipeline A: originales → con_fondo.
    """
    dir_destino.mkdir(parents=True, exist_ok=True)
    optimizadas = 0
    mensajes = []

    for foto in fotos:
        dest = dir_destino / (foto.stem + ".jpg")
        try:
            _optimizar_pillow(foto, dest)
            msg = f"OK: {foto.name} → {dir_destino.name}/{dest.name}"
            mensajes.append(msg)
            optimizadas += 1
            if callback:
                callback(msg)
        except Exception as e:
            msg = f"ERROR: {foto.name}: {e}"
            mensajes.append(msg)
            if callback:
                callback(msg)

    return optimizadas, mensajes


# ── Agregar texto a fotos ────────────────────────────────────────────────────

_COLOR_MARCA = (30, 30, 30)
_COLOR_PRECIO = (15, 100, 175)
_COLOR_SPECS = (70, 70, 70)
_COLOR_WATERMARK = (180, 180, 180)
_COLOR_BANDA_BG = (245, 248, 252)
_COLOR_LINEA = (200, 215, 230)

_FUENTES_BOLD = [
    "/usr/share/fonts/liberation-sans-fonts/LiberationSans-Bold.ttf",
    "/usr/share/fonts/google-carlito-fonts/Carlito-Bold.ttf",
    "/usr/share/fonts/google-droid-sans-fonts/DroidSans-Bold.ttf",
    "/usr/share/fonts/adwaita-sans-fonts/AdwaitaSans-Regular.ttf",
]
_FUENTES_REGULAR = [
    "/usr/share/fonts/liberation-sans-fonts/LiberationSans-Regular.ttf",
    "/usr/share/fonts/google-carlito-fonts/Carlito-Regular.ttf",
    "/usr/share/fonts/google-droid-sans-fonts/DroidSans.ttf",
    "/usr/share/fonts/adwaita-sans-fonts/AdwaitaSans-Regular.ttf",
]


def _cargar_fuente(candidatos: list[str], size: int):
    for ruta in candidatos:
        if Path(ruta).exists():
            return ImageFont.truetype(ruta, size)
    return ImageFont.load_default(size=size)


def _text_size(draw, text: str, font) -> tuple[int, int]:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def _agregar_texto_a_foto(path_src: Path, path_dest: Path,
                          precio: str, specs: str) -> None:
    img = Image.open(path_src).convert("RGB")
    W, H = img.size

    banda_h = int(H * 0.22)
    banda_y0 = H - banda_h
    margen_x = int(W * 0.05)
    margen_y = int(banda_h * 0.12)

    draw = ImageDraw.Draw(img, "RGBA")

    # Marca de agua diagonal
    wm_size = int(W * 0.04)
    fuente_wm = _cargar_fuente(_FUENTES_REGULAR, wm_size)
    wm_text = "Palishopping"
    wm_w, wm_h = _text_size(draw, wm_text, fuente_wm)

    wm_img = Image.new("RGBA", (wm_w + 10, wm_h + 10), (0, 0, 0, 0))
    wm_draw = ImageDraw.Draw(wm_img)
    wm_draw.text((5, 5), wm_text, font=fuente_wm, fill=(*_COLOR_WATERMARK, 60))
    wm_img = wm_img.rotate(25, expand=True)

    wm_x = W - wm_img.width - int(W * 0.04)
    wm_y = int(banda_y0 * 0.08)
    img.paste(wm_img, (wm_x, wm_y), wm_img)

    # Banda inferior
    draw.rectangle([(0, banda_y0), (W, H)], fill=(*_COLOR_BANDA_BG, 255))
    linea_h = max(2, int(H * 0.003))
    draw.rectangle([(0, banda_y0), (W, banda_y0 + linea_h)], fill=(*_COLOR_LINEA, 255))

    # Precio
    precio_size = int(banda_h * 0.38)
    fuente_precio = _cargar_fuente(_FUENTES_BOLD, precio_size)
    precio_y = banda_y0 + margen_y + linea_h
    draw.text((margen_x, precio_y), precio, font=fuente_precio, fill=_COLOR_PRECIO)
    _, precio_h = _text_size(draw, precio, fuente_precio)

    # Specs
    specs_size = int(banda_h * 0.19)
    fuente_specs = _cargar_fuente(_FUENTES_REGULAR, specs_size)
    specs_y = precio_y + precio_h + int(banda_h * 0.07)
    draw.text((margen_x, specs_y), specs, font=fuente_specs, fill=_COLOR_SPECS)

    # Marca discreta
    brand_size = int(banda_h * 0.17)
    fuente_brand = _cargar_fuente(_FUENTES_BOLD, brand_size)
    brand_text = "Palishopping"
    brand_w, brand_h = _text_size(draw, brand_text, fuente_brand)
    brand_x = W - margen_x - brand_w
    brand_y = H - margen_y - brand_h
    draw.text((brand_x, brand_y), brand_text,
              font=fuente_brand, fill=(*_COLOR_WATERMARK, 255))

    img.save(path_dest, "JPEG", quality=93, optimize=True)


def agregar_texto(fotos: list[Path], dir_con_texto: Path,
                  precio: str, specs: str, sufijo: str = "_sinfondo",
                  callback=None) -> tuple[int, list[str]]:
    """Agrega texto branding a fotos. sufijo: '_sinfondo' (pipeline B) o '_confondo' (pipeline A)."""
    dir_con_texto.mkdir(parents=True, exist_ok=True)
    procesadas = 0
    mensajes = []

    for foto in fotos:
        dest = dir_con_texto / f"{foto.stem}{sufijo}.jpg"
        try:
            _agregar_texto_a_foto(foto, dest, precio, specs)
            msg = f"OK: {foto.name} → con_texto/{dest.name}"
            mensajes.append(msg)
            procesadas += 1
            if callback:
                callback(msg)
        except Exception as e:
            msg = f"ERROR: {foto.name}: {e}"
            mensajes.append(msg)
            if callback:
                callback(msg)

    return procesadas, mensajes
