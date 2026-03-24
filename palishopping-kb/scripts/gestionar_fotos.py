#!/usr/bin/env python3
"""
gestionar_fotos.py — Revisá, eliminá, agregá y procesá fotos de un producto base en la KB.

Uso: python3 gestionar_fotos.py
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich import box

KB_ROOT = Path(__file__).resolve().parent.parent
PRODUCTOS_BASE = KB_ROOT / "productos-base"
CATALOGO = KB_ROOT / "catalogo.json"

EXTENSIONES_IMAGEN = {".jpg", ".jpeg", ".png", ".webp"}

console = Console()


# ── Helpers ───────────────────────────────────────────────────────────────────

import json

def cargar_catalogo() -> list[dict]:
    if not CATALOGO.exists():
        return []
    skus = json.loads(CATALOGO.read_text())
    productos = []
    for sku in skus:
        path = PRODUCTOS_BASE / sku / "producto.json"
        if path.exists():
            productos.append(json.loads(path.read_text()))
    return productos


def listar_fotos(directorio: Path) -> list[Path]:
    """Retorna las fotos en directorio ordenadas por nombre."""
    return sorted(
        f for f in directorio.iterdir()
        if f.is_file() and f.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
    )


def renombrar_secuencial(directorio: Path):
    """Renombra todas las fotos del directorio como 01.jpg, 02.jpg... sin huecos."""
    fotos = listar_fotos(directorio)
    if not fotos:
        return

    # Renombrar a nombres temporales primero para evitar colisiones
    tmp_dir = directorio / "_tmp_rename"
    tmp_dir.mkdir()
    tmp_nombres = []
    for i, f in enumerate(fotos):
        tmp = tmp_dir / f"{i:02d}_tmp{f.suffix}"
        f.rename(tmp)
        tmp_nombres.append(tmp)

    for i, tmp in enumerate(tmp_nombres, 1):
        final = directorio / f"{i:02d}.jpg"
        # Convertir a JPEG si hace falta
        if tmp.suffix.lower() != ".jpg":
            img = Image.open(tmp).convert("RGB")
            img.save(final, "JPEG", quality=95)
            tmp.unlink()
        else:
            tmp.rename(final)

    tmp_dir.rmdir()


def mostrar_tabla_fotos(fotos: list[Path], carpeta: str = "originales/") -> None:
    if not fotos:
        console.print(f"  [dim]No hay fotos en {carpeta}[/dim]")
        return

    table = Table(box=box.ROUNDED, padding=(0, 1))
    table.add_column("N°",     style="bold cyan",   width=4,  justify="right")
    table.add_column("Nombre", style="bold yellow",  width=10)
    table.add_column("Tamaño",                       width=10, justify="right")

    total = 0
    for i, f in enumerate(fotos, 1):
        size = f.stat().st_size
        total += size
        table.add_row(str(i), f.name, f"{size // 1024} KB")

    console.print(table)
    console.print(f"  Total: [bold]{len(fotos)} foto(s)[/bold]  •  {total // 1024} KB\n")


def parsear_numeros(raw: str, maximo: int) -> list[int] | None:
    """Parsea '3' o '3,7,11' a lista de índices (1-based). Retorna None si hay error."""
    partes = [p.strip() for p in raw.split(",") if p.strip()]
    resultado = []
    for p in partes:
        try:
            n = int(p)
            if not (1 <= n <= maximo):
                console.print(f"[red]Número {n} fuera de rango (1-{maximo}).[/red]")
                return None
            resultado.append(n)
        except ValueError:
            console.print(f"[red]'{p}' no es un número válido.[/red]")
            return None
    return resultado


def abrir_foto(path: Path):
    try:
        subprocess.Popen(["eog", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        console.print(f"  [dim]Abriendo {path.name} con eog...[/dim]")
    except FileNotFoundError:
        console.print("[yellow]'eog' no está instalado. Abrí la foto manualmente:[/yellow]")
        console.print(f"  [dim]{path}[/dim]")


# ── Interfaz ──────────────────────────────────────────────────────────────────

def mostrar_bienvenida():
    console.print()
    console.print(Panel(
        "[bold cyan]Gestionar Fotos — Palishopping KB[/bold cyan]\n"
        "[dim]Revisá, eliminá y agregá fotos de un producto base.[/dim]",
        box=box.ROUNDED,
        padding=(0, 2),
    ))
    console.print()


def mostrar_tabla_catalogo(catalogo: list) -> dict:
    table = Table(box=box.ROUNDED, show_lines=False, padding=(0, 1))
    table.add_column("N°",     style="bold cyan",  width=4,  justify="right")
    table.add_column("SKU",    style="bold yellow", min_width=14)
    table.add_column("Nombre", min_width=30)
    table.add_column("Tipo",   min_width=18)

    indice = {}
    for i, entrada in enumerate(catalogo, 1):
        table.add_row(str(i), entrada["sku"], entrada["nombre"], entrada.get("tipo", "—"))
        indice[str(i)] = entrada

    console.print(table)
    console.print()
    return indice


def elegir_producto(catalogo: list) -> dict | None:
    if not catalogo:
        console.print("[yellow]El catálogo está vacío.[/yellow]")
        return None

    console.rule("[bold cyan]Productos disponibles")
    console.print()
    indice = mostrar_tabla_catalogo(catalogo)
    skus = {e["sku"].upper(): e for e in catalogo}

    while True:
        r = Prompt.ask(
            f"[bold]Elegí un producto[/bold] [dim](número 1-{len(catalogo)} o SKU, Enter para cancelar)[/dim]",
            default="",
        )
        if not r.strip():
            return None
        if r.strip() in indice:
            return indice[r.strip()]
        if r.strip().upper() in skus:
            return skus[r.strip().upper()]
        console.print("[red]No encontrado.[/red]")


# ── Opción 1: Ver y eliminar ──────────────────────────────────────────────────

def opcion_ver_eliminar(directorio: Path) -> bool:
    """Retorna True si se eliminó alguna foto."""
    console.print()
    console.rule("[bold cyan]Fotos en originales/")
    console.print()

    fotos = listar_fotos(directorio)
    mostrar_tabla_fotos(fotos)

    if not fotos:
        return False

    eliminado_algo = False

    while True:
        r = Prompt.ask(
            "[bold]Acción[/bold] [dim](número(s) a eliminar, 'ver N', 'ver todas', Enter para terminar)[/dim]",
            default="",
        )
        raw = r.strip()

        if not raw:
            break

        # Comando "ver todas"
        if raw.lower() == "ver todas":
            try:
                subprocess.Popen(
                    ["eog", str(directorio) + "/"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                console.print(f"  [dim]Abriendo {directorio.name}/ en eog... navegá con las flechas.[/dim]")
            except FileNotFoundError:
                console.print("[yellow]'eog' no está instalado. Abrí la carpeta manualmente:[/yellow]")
                console.print(f"  [dim]{directorio}[/dim]")
            continue

        # Comando "ver N"
        if raw.lower().startswith("ver "):
            parte = raw[4:].strip()
            try:
                n = int(parte)
                if 1 <= n <= len(fotos):
                    abrir_foto(fotos[n - 1])
                else:
                    console.print(f"[red]Número {n} fuera de rango.[/red]")
            except ValueError:
                console.print("[red]Usá 'ver N' o 'ver todas'.[/red]")
            continue

        # Números a eliminar
        indices = parsear_numeros(raw, len(fotos))
        if indices is None:
            continue

        a_eliminar = [fotos[i - 1] for i in indices]

        console.print()
        console.print("[bold]Fotos a eliminar:[/bold]")
        for f in a_eliminar:
            console.print(f"  [red]✗[/red] {f.name}  [dim]({f.stat().st_size // 1024} KB)[/dim]")
        console.print()

        if not Confirm.ask(f"[bold]¿Eliminar estas {len(a_eliminar)} foto(s)?[/bold]", default=False):
            console.print("[dim]Cancelado, no se eliminó nada.[/dim]")
            continue

        for f in a_eliminar:
            f.unlink()
            console.print(f"  [green]✓[/green] Eliminada: {f.name}")

        eliminado_algo = True
        # Actualizar lista para la próxima iteración
        fotos = listar_fotos(directorio)

        console.print()
        console.print(f"  [dim]Quedan {len(fotos)} foto(s).[/dim]")
        mostrar_tabla_fotos(fotos)

    return eliminado_algo


# ── Opción 2: Agregar fotos propias ───────────────────────────────────────────

def resolver_imagenes_desde_path(raw_path: str) -> list[Path]:
    """
    Dado un path (archivo o carpeta), retorna las imágenes encontradas.
    """
    p = Path(raw_path.strip()).expanduser().resolve()

    if not p.exists():
        console.print(f"[red]No existe: {p}[/red]")
        return []

    if p.is_file():
        if p.suffix.lower() in EXTENSIONES_IMAGEN:
            return [p]
        console.print(f"[red]El archivo no es una imagen soportada ({', '.join(EXTENSIONES_IMAGEN)}).[/red]")
        return []

    if p.is_dir():
        imgs = sorted(f for f in p.iterdir() if f.is_file() and f.suffix.lower() in EXTENSIONES_IMAGEN)
        if not imgs:
            console.print(f"[yellow]No se encontraron imágenes en {p}[/yellow]")
        return imgs

    return []


def elegir_imagenes_de_lista(imagenes: list[Path]) -> list[Path]:
    """Muestra tabla y permite elegir todas o por número."""
    table = Table(box=box.ROUNDED, padding=(0, 1))
    table.add_column("N°",     style="bold cyan",  width=4,  justify="right")
    table.add_column("Nombre", style="bold yellow", min_width=20)
    table.add_column("Tamaño",                      width=10, justify="right")

    for i, img in enumerate(imagenes, 1):
        size = img.stat().st_size
        table.add_row(str(i), img.name, f"{size // 1024} KB")

    console.print(table)
    console.print()

    r = Prompt.ask(
        f"[bold]¿Cuáles agregar?[/bold] [dim](Enter = todas, o números separados por coma)[/dim]",
        default="",
    )

    if not r.strip():
        return imagenes

    indices = parsear_numeros(r.strip(), len(imagenes))
    if indices is None:
        return []

    return [imagenes[i - 1] for i in indices]


def copiar_imagen_a_jpg(src: Path, dest: Path):
    """Copia src a dest, convirtiendo a JPEG si es necesario."""
    if src.suffix.lower() in {".jpg", ".jpeg"}:
        shutil.copy2(src, dest)
    else:
        img = Image.open(src).convert("RGB")
        img.save(dest, "JPEG", quality=95)


def opcion_agregar_fotos(directorio: Path) -> bool:
    """Retorna True si se agregó alguna foto."""
    console.print()
    console.rule("[bold cyan]Agregar fotos propias")
    console.print()

    raw_path = Prompt.ask("[bold]Path de la foto o carpeta[/bold] [dim](soporte: jpg, jpeg, png, webp)[/dim]")
    imagenes_disponibles = resolver_imagenes_desde_path(raw_path)

    if not imagenes_disponibles:
        return False

    console.print()
    if len(imagenes_disponibles) == 1:
        img = imagenes_disponibles[0]
        console.print(f"  Imagen encontrada: [bold yellow]{img.name}[/bold yellow]  [dim]({img.stat().st_size // 1024} KB)[/dim]")
        console.print()
        seleccionadas = imagenes_disponibles if Confirm.ask("[bold]¿Agregar esta imagen?[/bold]", default=True) else []
    else:
        console.print(f"  [bold]{len(imagenes_disponibles)} imágenes encontradas:[/bold]\n")
        seleccionadas = elegir_imagenes_de_lista(imagenes_disponibles)

    if not seleccionadas:
        console.print("[dim]Nada seleccionado.[/dim]")
        return False

    # Calcular offset para la numeración
    existentes = listar_fotos(directorio)
    nums = []
    for f in existentes:
        try:
            nums.append(int(f.stem))
        except ValueError:
            pass
    offset = max(nums) if nums else len(existentes)

    # Confirmar antes de copiar
    console.print()
    console.print(f"  Se copiarán [bold]{len(seleccionadas)}[/bold] imagen(es) → [dim]{directorio}[/dim]")
    console.print()

    if not Confirm.ask("[bold]¿Confirmar copia?[/bold]", default=True):
        console.print("[dim]Cancelado.[/dim]")
        return False

    agregadas = 0
    for i, src in enumerate(seleccionadas, start=offset + 1):
        dest = directorio / f"{i:02d}.jpg"
        try:
            copiar_imagen_a_jpg(src, dest)
            console.print(f"  [green]✓[/green] {src.name} → {dest.name}")
            agregadas += 1
        except Exception as e:
            console.print(f"  [red]✗[/red] {src.name}: {e}")

    return agregadas > 0


# ── Opción 4: Procesar fotos — fondo blanco ───────────────────────────────────

def _rembg_disponible() -> bool:
    try:
        import rembg  # noqa: F401
        return True
    except ImportError:
        return False


def _instalar_rembg():
    console.print("[yellow]rembg no está instalado. Instalando...[/yellow]")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "rembg[gpu]"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        # Intentar sin GPU
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "rembg"],
            capture_output=True, text=True,
        )
    if result.returncode != 0:
        console.print("[red]No se pudo instalar rembg:[/red]")
        console.print(result.stderr[-500:])
        return False
    console.print("[green]rembg instalado correctamente.[/green]")
    return True


def _remover_fondo_rembg(src: Path) -> Image.Image:
    """Usa rembg para quitar el fondo. Retorna imagen RGBA."""
    import rembg
    data = src.read_bytes()
    result = rembg.remove(data)
    from io import BytesIO
    return Image.open(BytesIO(result)).convert("RGBA")


def _remover_fondo_pillow(src: Path) -> Image.Image:
    """Fallback sin rembg: devuelve la imagen original convertida a RGBA (sin quitar fondo)."""
    return Image.open(src).convert("RGBA")


def _componer_fondo_blanco(img_rgba: Image.Image) -> Image.Image:
    """Compone la imagen RGBA sobre fondo blanco y retorna RGB."""
    fondo = Image.new("RGB", img_rgba.size, (255, 255, 255))
    fondo.paste(img_rgba, mask=img_rgba.split()[3])  # canal alpha como máscara
    return fondo


def opcion_procesar_fotos(dir_originales: Path, dir_procesadas: Path) -> bool:
    """Retorna True si se procesó alguna foto."""
    console.print()
    console.rule("[bold cyan]Procesar fotos — fondo blanco")
    console.print()

    fotos = listar_fotos(dir_originales)
    if not fotos:
        console.print("  [yellow]No hay fotos en originales/ para procesar.[/yellow]")
        return False

    mostrar_tabla_fotos(fotos, "originales/")

    r = Prompt.ask(
        "[bold]¿Cuáles procesar?[/bold] [dim](Enter = todas, o números separados por coma)[/dim]",
        default="",
    )

    if r.strip():
        indices = parsear_numeros(r.strip(), len(fotos))
        if indices is None:
            return False
        seleccionadas = [fotos[i - 1] for i in indices]
    else:
        seleccionadas = fotos

    if not seleccionadas:
        return False

    # Verificar / instalar rembg
    usar_rembg = _rembg_disponible()
    if not usar_rembg:
        if Confirm.ask(
            "[bold]rembg no está instalado (necesario para quitar el fondo con IA).\n"
            "  ¿Instalarlo ahora?[/bold] [dim](~170 MB, descarga el modelo la primera vez)[/dim]",
            default=True,
        ):
            usar_rembg = _instalar_rembg()

    if usar_rembg:
        console.print(
            "\n  [dim]Usando [bold]rembg[/bold] (u2net). "
            "La primera vez descarga el modelo (~170 MB).[/dim]\n"
        )
    else:
        console.print(
            "\n  [yellow]Procesando sin rembg: se pondrá fondo blanco "
            "pero no se quitará el fondo de la imagen.[/yellow]\n"
        )

    dir_procesadas.mkdir(parents=True, exist_ok=True)
    procesadas = 0

    for foto in seleccionadas:
        dest = dir_procesadas / foto.name
        try:
            with console.status(f"  Procesando {foto.name}...", spinner="dots"):
                if usar_rembg:
                    img_rgba = _remover_fondo_rembg(foto)
                else:
                    img_rgba = _remover_fondo_pillow(foto)
                img_rgb = _componer_fondo_blanco(img_rgba)
                img_rgb.save(dest, "JPEG", quality=95)
            size = dest.stat().st_size
            console.print(f"  [green]✓[/green] {foto.name} → procesadas/{dest.name}  [dim]({size // 1024} KB)[/dim]")
            procesadas += 1
        except Exception as e:
            console.print(f"  [red]✗[/red] {foto.name}: {e}")

    console.print()
    console.print(
        f"  [bold green]{procesadas}[/bold green] foto(s) procesadas → "
        f"[dim]{dir_procesadas}[/dim]"
    )
    return procesadas > 0


# ── Opción 6: Optimizar fotos para Gemini ─────────────────────────────────────

def _autocrop(img: Image.Image, umbral: int = 245) -> Image.Image:
    """Recorta los bordes blancos innecesarios de una imagen RGB."""
    import numpy as np
    arr = np.array(img)
    # Máscara de píxeles no-blancos (cualquiera de los 3 canales < umbral)
    mascara = (arr[:, :, 0] < umbral) | (arr[:, :, 1] < umbral) | (arr[:, :, 2] < umbral)
    filas = np.any(mascara, axis=1)
    cols = np.any(mascara, axis=0)
    if not filas.any():
        return img  # imagen completamente blanca, no recortar
    r_min, r_max = np.where(filas)[0][[0, -1]]
    c_min, c_max = np.where(cols)[0][[0, -1]]
    # Agregar margen del 2% para no recortar demasiado justo
    h, w = arr.shape[:2]
    margen_y = max(int(h * 0.02), 4)
    margen_x = max(int(w * 0.02), 4)
    r_min = max(0, r_min - margen_y)
    r_max = min(h - 1, r_max + margen_y)
    c_min = max(0, c_min - margen_x)
    c_max = min(w - 1, c_max + margen_x)
    return img.crop((c_min, r_min, c_max + 1, r_max + 1))


def _pad_a_cuadrado(img: Image.Image, size: int = 1024) -> Image.Image:
    """Redimensiona manteniendo aspect ratio y agrega padding blanco hasta size x size."""
    img.thumbnail((size, size), Image.LANCZOS)
    fondo = Image.new("RGB", (size, size), (255, 255, 255))
    offset_x = (size - img.width) // 2
    offset_y = (size - img.height) // 2
    fondo.paste(img, (offset_x, offset_y))
    return fondo


def _optimizar_solo_pillow(path_src: Path, path_dest: Path):
    """Fallback sin OpenCV: autocrop + sharpening + resize con padding."""
    from PIL import ImageEnhance, ImageFilter

    img = Image.open(path_src).convert("RGB")
    img = _autocrop(img)

    # Nitidez
    img = img.filter(ImageFilter.UnsharpMask(radius=1.5, percent=130, threshold=2))
    # Contraste
    img = ImageEnhance.Contrast(img).enhance(1.1)
    # Brillo
    img = ImageEnhance.Brightness(img).enhance(1.03)
    # Saturación
    img = ImageEnhance.Color(img).enhance(1.12)
    # Pad a 1024x1024
    img = _pad_a_cuadrado(img, size=1024)

    img.save(path_dest, "JPEG", quality=92, optimize=True)


def opcion_optimizar_gemini(dir_procesadas: Path, dir_listas: Path) -> bool:
    """Retorna True si se optimizó alguna foto."""
    console.print()
    console.rule("[bold cyan]Optimizar fotos para Gemini")
    console.print()

    dir_procesadas.mkdir(parents=True, exist_ok=True)
    fotos = listar_fotos(dir_procesadas)

    if not fotos:
        console.print(
            "  [yellow]No hay fotos en procesadas/.[/yellow]\n"
            "  [dim]Hacé primero la opción [4] para procesar fotos con fondo blanco.[/dim]"
        )
        return False

    mostrar_tabla_fotos(fotos, "procesadas/")

    # Selección (con soporte de "ver N")
    seleccionadas: list[Path] = []
    while True:
        r = Prompt.ask(
            "[bold]¿Cuáles optimizar?[/bold] [dim](Enter = todas, números por coma, o 'ver N')[/dim]",
            default="",
        )
        raw = r.strip()

        if raw.lower().startswith("ver "):
            try:
                n = int(raw[4:].strip())
                if 1 <= n <= len(fotos):
                    abrir_foto(fotos[n - 1])
                else:
                    console.print(f"[red]Número {n} fuera de rango.[/red]")
            except ValueError:
                console.print("[red]Usá 'ver N' donde N es el número de la foto.[/red]")
            continue

        if not raw:
            seleccionadas = fotos
        else:
            indices = parsear_numeros(raw, len(fotos))
            if indices is None:
                continue
            seleccionadas = [fotos[i - 1] for i in indices]
        break

    if not seleccionadas:
        return False

    console.print(
        "\n  [dim]Pipeline: autocrop → sharpening → contraste → saturación → 1024×1024[/dim]\n"
    )

    dir_listas.mkdir(parents=True, exist_ok=True)
    optimizadas = 0

    for foto in seleccionadas:
        dest = dir_listas / (foto.stem + ".jpg") if foto.suffix.lower() != ".jpg" else dir_listas / foto.name
        size_antes = foto.stat().st_size
        try:
            with console.status(f"  Optimizando {foto.name}...", spinner="dots"):
                _optimizar_solo_pillow(foto, dest)
            size_despues = dest.stat().st_size
            delta = size_despues - size_antes
            signo = "+" if delta >= 0 else ""
            console.print(
                f"  [green]✓[/green] {foto.name} → listas_gemini/{dest.name}  "
                f"[dim]{size_antes // 1024} KB → {size_despues // 1024} KB "
                f"({signo}{delta // 1024} KB)[/dim]"
            )
            optimizadas += 1
        except Exception as e:
            console.print(f"  [red]✗[/red] {foto.name}: {e}")

    if optimizadas:
        fotos_listas = listar_fotos(dir_listas)
        total = sum(f.stat().st_size for f in fotos_listas)
        console.print()
        console.print(Panel(
            f"[bold green]{optimizadas} foto(s) optimizadas.[/bold green]\n"
            f"[dim]{dir_listas}[/dim]\n"
            f"Total en listas_gemini/: [bold]{len(fotos_listas)} foto(s)[/bold]  •  {total // 1024} KB",
            box=box.ROUNDED,
            padding=(0, 2),
        ))
        console.print()

    return optimizadas > 0


# ── Opción 5: Revisar fotos procesadas ────────────────────────────────────────

def opcion_revisar_procesadas(dir_procesadas: Path) -> bool:
    """Retorna True si se eliminó alguna foto."""
    console.print()
    console.rule("[bold cyan]Revisar fotos procesadas")
    console.print()

    dir_procesadas.mkdir(parents=True, exist_ok=True)
    fotos = listar_fotos(dir_procesadas)
    mostrar_tabla_fotos(fotos, "procesadas/")

    if not fotos:
        return False

    eliminado_algo = False

    while True:
        r = Prompt.ask(
            "[bold]Acción[/bold] [dim](número(s) a eliminar, 'ver N', Enter para terminar)[/dim]",
            default="",
        )
        raw = r.strip()

        if not raw:
            break

        # Comando "ver N"
        if raw.lower().startswith("ver "):
            parte = raw[4:].strip()
            try:
                n = int(parte)
                if 1 <= n <= len(fotos):
                    abrir_foto(fotos[n - 1])
                else:
                    console.print(f"[red]Número {n} fuera de rango.[/red]")
            except ValueError:
                console.print("[red]Usá 'ver N' donde N es el número de la foto.[/red]")
            continue

        # Números a eliminar
        indices = parsear_numeros(raw, len(fotos))
        if indices is None:
            continue

        a_eliminar = [fotos[i - 1] for i in indices]

        console.print()
        console.print("[bold]Fotos a eliminar de procesadas/:[/bold]")
        for f in a_eliminar:
            console.print(f"  [red]✗[/red] {f.name}  [dim]({f.stat().st_size // 1024} KB)[/dim]")
        console.print()

        if not Confirm.ask(f"[bold]¿Eliminar estas {len(a_eliminar)} foto(s)?[/bold]", default=False):
            console.print("[dim]Cancelado.[/dim]")
            continue

        for f in a_eliminar:
            f.unlink()
            console.print(f"  [green]✓[/green] Eliminada: {f.name}")

        eliminado_algo = True
        fotos = listar_fotos(dir_procesadas)

        console.print()
        console.print(f"  [dim]Quedan {len(fotos)} foto(s) en procesadas/.[/dim]")
        mostrar_tabla_fotos(fotos, "procesadas/")

    if eliminado_algo:
        renombrar_secuencial(dir_procesadas)

    return eliminado_algo


# ── Opción 7: Agregar texto a fotos ──────────────────────────────────────────

# Paleta de colores de marca
_COLOR_MARCA      = (30, 30, 30)       # casi negro para textos principales
_COLOR_PRECIO     = (15, 100, 175)     # azul medio — destaca sin ser chillón
_COLOR_SPECS      = (70, 70, 70)       # gris oscuro para specs
_COLOR_WATERMARK  = (180, 180, 180)    # gris claro para marca de agua
_COLOR_BANDA_BG   = (245, 248, 252)    # blanco azulado muy suave para la banda
_COLOR_LINEA      = (200, 215, 230)    # azul muy claro para separadores

# Candidatos de fuentes en orden de preferencia
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
    from PIL import ImageFont
    for ruta in candidatos:
        if Path(ruta).exists():
            return ImageFont.truetype(ruta, size)
    return ImageFont.load_default(size=size)


def _text_size(draw, text: str, font) -> tuple[int, int]:
    """Retorna (ancho, alto) del texto renderizado."""
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def _agregar_texto_a_foto(
    path_src: Path,
    path_dest: Path,
    precio: str,
    specs: str,
):
    """
    Diseño:
    - Imagen de producto ocupa el 78% superior (zona limpia, sin texto encima)
    - Banda inferior (22%) con fondo blanco-azulado suave y borde superior delgado
      - Línea azul delgada de separación
      - Precio grande en azul medio  (alineado a la izquierda con margen)
      - Especificaciones en gris oscuro, debajo del precio
      - "Palishopping" pequeño y discreto, alineado a la derecha en la banda
    - Marca de agua muy suave "Palishopping" en diagonal, centrada en el área del producto
    """
    from PIL import ImageDraw, ImageFont, Image as PILImage

    img = PILImage.open(path_src).convert("RGB")
    W, H = img.size  # debería ser 1024x1024

    # Alturas de zonas
    banda_h  = int(H * 0.22)
    banda_y0 = H - banda_h
    margen_x = int(W * 0.05)   # 5% de margen lateral
    margen_y = int(banda_h * 0.12)

    draw = ImageDraw.Draw(img, "RGBA")

    # ── 1. Marca de agua diagonal en área del producto ────────────────────────
    wm_size = int(W * 0.04)
    fuente_wm = _cargar_fuente(_FUENTES_REGULAR, wm_size)
    wm_text = "Palishopping"
    wm_w, wm_h = _text_size(draw, wm_text, fuente_wm)

    # Renderizar en imagen temporal RGBA para rotar
    wm_img = PILImage.new("RGBA", (wm_w + 10, wm_h + 10), (0, 0, 0, 0))
    wm_draw = ImageDraw.Draw(wm_img)
    wm_draw.text((5, 5), wm_text, font=fuente_wm, fill=(*_COLOR_WATERMARK, 60))
    wm_img = wm_img.rotate(25, expand=True)

    # Posición: tercio superior derecho del área del producto
    wm_x = W - wm_img.width - int(W * 0.04)
    wm_y = int(banda_y0 * 0.08)
    img.paste(wm_img, (wm_x, wm_y), wm_img)

    # ── 2. Banda inferior ─────────────────────────────────────────────────────
    draw.rectangle(
        [(0, banda_y0), (W, H)],
        fill=(*_COLOR_BANDA_BG, 255),
    )

    # Línea de separación azul delgada
    linea_h = max(2, int(H * 0.003))
    draw.rectangle(
        [(0, banda_y0), (W, banda_y0 + linea_h)],
        fill=(*_COLOR_LINEA, 255),
    )

    # ── 3. Precio ─────────────────────────────────────────────────────────────
    precio_size = int(banda_h * 0.38)
    fuente_precio = _cargar_fuente(_FUENTES_BOLD, precio_size)

    precio_y = banda_y0 + margen_y + linea_h
    draw.text(
        (margen_x, precio_y),
        precio,
        font=fuente_precio,
        fill=_COLOR_PRECIO,
    )
    _, precio_h = _text_size(draw, precio, fuente_precio)

    # ── 4. Especificaciones ───────────────────────────────────────────────────
    specs_size = int(banda_h * 0.19)
    fuente_specs = _cargar_fuente(_FUENTES_REGULAR, specs_size)

    specs_y = precio_y + precio_h + int(banda_h * 0.07)
    draw.text(
        (margen_x, specs_y),
        specs,
        font=fuente_specs,
        fill=_COLOR_SPECS,
    )

    # ── 5. "Palishopping" marca discreta en la banda, alineada a la derecha ──
    brand_size = int(banda_h * 0.17)
    fuente_brand = _cargar_fuente(_FUENTES_BOLD, brand_size)
    brand_text = "Palishopping"
    brand_w, brand_h = _text_size(draw, brand_text, fuente_brand)

    brand_x = W - margen_x - brand_w
    brand_y = H - margen_y - brand_h
    draw.text(
        (brand_x, brand_y),
        brand_text,
        font=fuente_brand,
        fill=(*_COLOR_WATERMARK, 255),
    )

    img.save(path_dest, "JPEG", quality=93, optimize=True)


def opcion_agregar_texto(dir_listas: Path, dir_con_texto: Path) -> bool:
    """Retorna True si se procesó alguna foto."""
    console.print()
    console.rule("[bold cyan]Agregar texto a fotos")
    console.print()

    dir_listas.mkdir(parents=True, exist_ok=True)
    fotos = listar_fotos(dir_listas)

    if not fotos:
        console.print(
            "  [yellow]No hay fotos en listas_gemini/.[/yellow]\n"
            "  [dim]Hacé primero la opción [6] para optimizar fotos para Gemini.[/dim]"
        )
        return False

    mostrar_tabla_fotos(fotos, "listas_gemini/")

    # Selección con soporte de "ver N"
    seleccionadas: list[Path] = []
    while True:
        r = Prompt.ask(
            "[bold]¿Cuáles procesar?[/bold] [dim](Enter = todas, números por coma, o 'ver N')[/dim]",
            default="",
        )
        raw = r.strip()

        if raw.lower().startswith("ver "):
            try:
                n = int(raw[4:].strip())
                if 1 <= n <= len(fotos):
                    abrir_foto(fotos[n - 1])
                else:
                    console.print(f"[red]Número {n} fuera de rango.[/red]")
            except ValueError:
                console.print("[red]Usá 'ver N' donde N es el número de la foto.[/red]")
            continue

        if not raw:
            seleccionadas = fotos
        else:
            indices = parsear_numeros(raw, len(fotos))
            if indices is None:
                continue
            seleccionadas = [fotos[i - 1] for i in indices]
        break

    if not seleccionadas:
        return False

    # Pedir datos de texto
    console.print()
    console.rule("[bold cyan]Datos para el diseño")
    console.print()

    precio = Prompt.ask("[bold]Precio[/bold] [dim](ej: $18.900)[/dim]")
    precio = precio.strip() or "$0"

    specs = Prompt.ask(
        "[bold]Especificaciones técnicas[/bold] [dim](ej: Talle 40 · Transparente · Apilable)[/dim]"
    )
    specs = specs.strip()

    # Preview del diseño
    console.print()
    table_prev = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table_prev.add_column("Campo", style="bold cyan", min_width=14)
    table_prev.add_column("Valor")
    table_prev.add_row("Precio",  precio)
    table_prev.add_row("Specs",   specs or "[dim]—[/dim]")
    table_prev.add_row("Fotos",   str(len(seleccionadas)))
    table_prev.add_row("Destino", "fotos/con_texto/")
    console.print(table_prev)
    console.print()

    if not Confirm.ask("[bold]¿Aplicar diseño?[/bold]", default=True):
        console.print("[dim]Cancelado.[/dim]")
        return False

    dir_con_texto.mkdir(parents=True, exist_ok=True)
    procesadas = 0

    console.print()
    for foto in seleccionadas:
        dest = dir_con_texto / f"{foto.stem}_sinfondo.jpg"
        size_antes = foto.stat().st_size
        try:
            with console.status(f"  Procesando {foto.name}...", spinner="dots"):
                _agregar_texto_a_foto(foto, dest, precio, specs)
            size_despues = dest.stat().st_size
            console.print(
                f"  [green]✓[/green] {foto.name} → con_texto/{dest.name}  "
                f"[dim]{size_antes // 1024} KB → {size_despues // 1024} KB[/dim]"
            )
            procesadas += 1
        except Exception as e:
            console.print(f"  [red]✗[/red] {foto.name}: {e}")

    if procesadas:
        fotos_dest = listar_fotos(dir_con_texto)
        total = sum(f.stat().st_size for f in fotos_dest)
        console.print()
        console.print(Panel(
            f"[bold green]{procesadas} foto(s) con texto (pipeline B) generadas.[/bold green]\n"
            f"[dim]Archivos: *_sinfondo.jpg en con_texto/[/dim]",
            box=box.ROUNDED,
            padding=(0, 2),
        ))
        console.print()

    return procesadas > 0


# ── Opción 8: Detectar y descartar fotos malas ────────────────────────────────

def _analizar_calidad(path: Path) -> dict:
    """
    Retorna dict con keys: blur, brillo, cobertura, problemas (list[str]), score (0-100).
    Usa OpenCV si está disponible, Pillow como fallback.
    """
    import numpy as np

    img_pil = Image.open(path).convert("RGB")
    arr = np.array(img_pil, dtype=np.float32)

    # Brillo promedio
    brillo = float(arr.mean())

    # Varianza del Laplaciano (nitidez)
    try:
        import cv2
        gray = cv2.cvtColor(arr.astype("uint8"), cv2.COLOR_RGB2GRAY)
        blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    except ImportError:
        # Fallback: gradiente simple con numpy
        gy = np.diff(arr[:, :, 0], axis=0)
        gx = np.diff(arr[:, :, 0], axis=1)
        blur_score = float(np.var(gy) + np.var(gx))

    # Cobertura del producto: porcentaje de píxeles no-blancos
    blanco = (arr[:, :, 0] > 240) & (arr[:, :, 1] > 240) & (arr[:, :, 2] > 240)
    cobertura = float((~blanco).mean())  # 0.0 - 1.0

    problemas = []
    if blur_score < 100:
        problemas.append(f"borrosa (blur={blur_score:.0f})")
    if brillo < 50:
        problemas.append(f"muy oscura (brillo={brillo:.0f})")
    if brillo > 240:
        problemas.append(f"sobreexpuesta (brillo={brillo:.0f})")
    if cobertura < 0.20:
        problemas.append(f"producto pequeño ({cobertura*100:.0f}% del frame)")

    # Score compuesto 0-100 (más alto = mejor)
    score_blur   = min(100, blur_score / 5)
    score_brillo = 100 - abs(brillo - 145) / 1.45
    score_cob    = min(100, cobertura * 250)
    score = int((score_blur * 0.4 + score_brillo * 0.3 + score_cob * 0.3))
    score = max(0, min(100, score))

    return {
        "blur":       blur_score,
        "brillo":     brillo,
        "cobertura":  cobertura,
        "problemas":  problemas,
        "score":      score,
    }


def opcion_filtrar_calidad(dir_originales: Path) -> bool:
    console.print()
    console.rule("[bold cyan]Detectar y descartar fotos malas")
    console.print()

    fotos = listar_fotos(dir_originales)
    if not fotos:
        console.print("  [yellow]No hay fotos en originales/.[/yellow]")
        return False

    # Analizar todas
    resultados = []
    with console.status("[bold cyan]Analizando calidad...[/bold cyan]", spinner="dots"):
        for f in fotos:
            r = _analizar_calidad(f)
            r["path"] = f
            resultados.append(r)

    # Tabla de resultados
    console.print()
    table = Table(box=box.ROUNDED, padding=(0, 1))
    table.add_column("N°",       style="bold cyan",  width=4,  justify="right")
    table.add_column("Nombre",   style="bold yellow", width=10)
    table.add_column("Score",                         width=7,  justify="right")
    table.add_column("Problemas detectados")

    malas = []
    for i, r in enumerate(resultados, 1):
        score = r["score"]
        color = "green" if score >= 70 else ("yellow" if score >= 45 else "red")
        prob_str = ", ".join(r["problemas"]) if r["problemas"] else "[dim]OK[/dim]"
        table.add_row(str(i), r["path"].name, f"[{color}]{score}[/{color}]", prob_str)
        if r["problemas"]:
            malas.append(i)

    console.print(table)
    console.print()

    if not malas:
        console.print("  [green]Todas las fotos pasaron el filtro de calidad.[/green]")
        return False

    console.print(
        f"  [yellow]{len(malas)} foto(s) con problemas detectados:[/yellow] "
        f"{', '.join(str(m) for m in malas)}\n"
    )

    # Bucle de decisión
    a_eliminar: list[Path] = []
    while True:
        r = Prompt.ask(
            "[bold]¿Qué descartar?[/bold] [dim](números, 'malas' para todas las detectadas, 'ver N', Enter para nada)[/dim]",
            default="",
        )
        raw = r.strip()

        if not raw:
            console.print("[dim]Sin cambios.[/dim]")
            return False

        if raw.lower().startswith("ver "):
            try:
                n = int(raw[4:].strip())
                if 1 <= n <= len(fotos):
                    abrir_foto(fotos[n - 1])
                else:
                    console.print(f"[red]Número {n} fuera de rango.[/red]")
            except ValueError:
                console.print("[red]Usá 'ver N'.[/red]")
            continue

        if raw.lower() == "malas":
            a_eliminar = [resultados[i - 1]["path"] for i in malas]
            break

        indices = parsear_numeros(raw, len(fotos))
        if indices is None:
            continue
        a_eliminar = [fotos[i - 1] for i in indices]
        break

    if not a_eliminar:
        return False

    console.print()
    console.print("[bold]Fotos a eliminar:[/bold]")
    for f in a_eliminar:
        console.print(f"  [red]✗[/red] {f.name}")
    console.print()

    if not Confirm.ask(f"[bold]¿Eliminar {len(a_eliminar)} foto(s)?[/bold]", default=False):
        console.print("[dim]Cancelado.[/dim]")
        return False

    for f in a_eliminar:
        f.unlink()
        console.print(f"  [green]✓[/green] Eliminada: {f.name}")

    renombrar_secuencial(dir_originales)
    fotos_restantes = listar_fotos(dir_originales)
    console.print(f"\n  [dim]Quedan {len(fotos_restantes)} foto(s) en originales/.[/dim]")
    return True


# ── Opción 9: Centrar y normalizar producto en el frame ────────────────────────

def _centrar_producto(path_src: Path, path_dest: Path, canvas: int = 1200, margen: float = 0.10):
    """
    Detecta el bounding box del área no-blanca, la centra en canvas×canvas
    y escala para que el producto ocupe (1 - 2*margen) del lado menor.
    """
    import numpy as np

    img = Image.open(path_src).convert("RGB")
    arr = np.array(img)

    # Máscara de píxeles no-blancos (umbral 245)
    mascara = (arr[:, :, 0] < 245) | (arr[:, :, 1] < 245) | (arr[:, :, 2] < 245)
    filas = np.any(mascara, axis=1)
    cols  = np.any(mascara, axis=0)

    if not filas.any():
        # Imagen completamente blanca: devolver tal cual en canvas
        resultado = Image.new("RGB", (canvas, canvas), (255, 255, 255))
        img.thumbnail((canvas, canvas), Image.LANCZOS)
        offset_x = (canvas - img.width) // 2
        offset_y = (canvas - img.height) // 2
        resultado.paste(img, (offset_x, offset_y))
        resultado.save(path_dest, "JPEG", quality=93)
        return

    filas_idx = np.where(filas)[0]
    cols_idx  = np.where(cols)[0]
    r_min, r_max = int(filas_idx[0]), int(filas_idx[-1])
    c_min, c_max = int(cols_idx[0]),  int(cols_idx[-1])

    crop = img.crop((c_min, r_min, c_max + 1, r_max + 1))

    # Escalar para que ocupe el 80% del canvas (margen 10% por lado)
    area_util = int(canvas * (1 - 2 * margen))
    crop.thumbnail((area_util, area_util), Image.LANCZOS)

    resultado = Image.new("RGB", (canvas, canvas), (255, 255, 255))
    offset_x = (canvas - crop.width) // 2
    offset_y = (canvas - crop.height) // 2
    resultado.paste(crop, (offset_x, offset_y))
    resultado.save(path_dest, "JPEG", quality=93, optimize=True)


def opcion_centrar_producto(dir_procesadas: Path) -> bool:
    console.print()
    console.rule("[bold cyan]Centrar y normalizar producto en el frame")
    console.print()

    dir_procesadas.mkdir(parents=True, exist_ok=True)
    fotos = listar_fotos(dir_procesadas)

    if not fotos:
        console.print(
            "  [yellow]No hay fotos en procesadas/.[/yellow]\n"
            "  [dim]Hacé primero la opción [4] para procesar fotos con fondo blanco.[/dim]"
        )
        return False

    mostrar_tabla_fotos(fotos, "procesadas/")

    r = Prompt.ask(
        "[bold]¿Cuáles procesar?[/bold] [dim](Enter = todas, números por coma)[/dim]",
        default="",
    )

    if r.strip():
        indices = parsear_numeros(r.strip(), len(fotos))
        if indices is None:
            return False
        seleccionadas = [fotos[i - 1] for i in indices]
    else:
        seleccionadas = fotos

    if not seleccionadas:
        return False

    console.print(
        f"\n  Canvas: [bold]1200×1200[/bold] px · "
        f"Producto ocupa [bold]80%[/bold] del frame · Fondo blanco\n"
    )

    procesadas = 0
    for foto in seleccionadas:
        size_antes = foto.stat().st_size
        # Sobreescribir en procesadas/
        tmp = foto.with_suffix(".tmp.jpg")
        try:
            with console.status(f"  Centrando {foto.name}...", spinner="dots"):
                _centrar_producto(foto, tmp)
            tmp.replace(foto)
            size_despues = foto.stat().st_size
            delta = size_despues - size_antes
            signo = "+" if delta >= 0 else ""
            console.print(
                f"  [green]✓[/green] {foto.name}  "
                f"[dim]{size_antes // 1024} KB → {size_despues // 1024} KB ({signo}{delta // 1024} KB)[/dim]"
            )
            procesadas += 1
        except Exception as e:
            if tmp.exists():
                tmp.unlink()
            console.print(f"  [red]✗[/red] {foto.name}: {e}")

    console.print()
    console.print(Panel(
        f"[bold green]{procesadas} foto(s) centradas y normalizadas.[/bold green]\n"
        f"[dim]Guardadas en fotos/procesadas/ (sobreescritas)[/dim]",
        box=box.ROUNDED,
        padding=(0, 2),
    ))
    console.print()
    return procesadas > 0


# ── Opción 10: Generar collage multi-ángulo ────────────────────────────────────

def _collage_2(fotos: list[Image.Image], canvas: int = 1200, margen: int = 20) -> Image.Image:
    """Dos fotos lado a lado con margen entre ellas."""
    ancho_celda = (canvas - margen * 3) // 2
    alto_celda  = canvas - margen * 2

    resultado = Image.new("RGB", (canvas, canvas), (255, 255, 255))
    for i, img in enumerate(fotos[:2]):
        img = img.copy()
        img.thumbnail((ancho_celda, alto_celda), Image.LANCZOS)
        x = margen + i * (ancho_celda + margen)
        y = margen + (alto_celda - img.height) // 2
        resultado.paste(img, (x, y))
    return resultado


def _collage_3(fotos: list[Image.Image], canvas: int = 1200, margen: int = 20) -> Image.Image:
    """Una foto grande arriba, dos pequeñas abajo."""
    # Fila superior: 60% de la altura
    alto_sup  = int(canvas * 0.60) - margen * 2
    ancho_sup = canvas - margen * 2
    # Fila inferior: 40%
    alto_inf  = canvas - alto_sup - margen * 3
    ancho_inf = (canvas - margen * 3) // 2

    resultado = Image.new("RGB", (canvas, canvas), (255, 255, 255))

    # Foto principal arriba
    img0 = fotos[0].copy()
    img0.thumbnail((ancho_sup, alto_sup), Image.LANCZOS)
    x0 = margen + (ancho_sup - img0.width) // 2
    y0 = margen + (alto_sup - img0.height) // 2
    resultado.paste(img0, (x0, y0))

    # Dos fotos abajo
    y_inf = margen * 2 + alto_sup
    for i, img in enumerate(fotos[1:3]):
        img = img.copy()
        img.thumbnail((ancho_inf, alto_inf), Image.LANCZOS)
        x = margen + i * (ancho_inf + margen)
        y = y_inf + (alto_inf - img.height) // 2
        resultado.paste(img, (x, y))

    return resultado


def opcion_collage(dir_procesadas: Path) -> bool:
    console.print()
    console.rule("[bold cyan]Generar collage multi-ángulo")
    console.print()

    dir_procesadas.mkdir(parents=True, exist_ok=True)
    fotos = listar_fotos(dir_procesadas)

    if len(fotos) < 2:
        console.print(
            "  [yellow]Necesitás al menos 2 fotos en procesadas/ para hacer un collage.[/yellow]"
        )
        return False

    mostrar_tabla_fotos(fotos, "procesadas/")

    # Elegir fotos
    while True:
        r = Prompt.ask(
            "[bold]Elegí 2 o 3 fotos[/bold] [dim](números separados por coma, ej: 1,3 o 2,4,5)[/dim]",
            default="",
        )
        if not r.strip():
            console.print("[dim]Cancelado.[/dim]")
            return False

        indices = parsear_numeros(r.strip(), len(fotos))
        if indices is None:
            continue
        if len(indices) < 2 or len(indices) > 3:
            console.print("[red]Elegí exactamente 2 o 3 fotos.[/red]")
            continue
        seleccionadas = [fotos[i - 1] for i in indices]
        break

    nombre_out = Prompt.ask(
        "[bold]Nombre del archivo de salida[/bold] [dim](sin extensión)[/dim]",
        default="collage",
    )
    nombre_out = nombre_out.strip().replace(" ", "_") or "collage"
    path_dest = dir_procesadas / f"{nombre_out}.jpg"

    n = len(seleccionadas)
    console.print(f"\n  Collage de [bold]{n}[/bold] foto(s) · Canvas 1200×1200 px\n")

    try:
        with console.status("[bold cyan]Generando collage...[/bold cyan]", spinner="dots"):
            imgs = [Image.open(f).convert("RGB") for f in seleccionadas]
            if n == 2:
                resultado = _collage_2(imgs)
            else:
                resultado = _collage_3(imgs)
            resultado.save(path_dest, "JPEG", quality=93, optimize=True)

        size = path_dest.stat().st_size
        console.print(Panel(
            f"[bold green]Collage generado.[/bold green]  {size // 1024} KB\n"
            f"[dim]{path_dest}[/dim]",
            box=box.ROUNDED,
            padding=(0, 2),
        ))
        console.print()
        return True

    except Exception as e:
        console.print(f"[red]Error generando collage:[/red] {e}")
        return False


# ── Opciones 6A / 7A: pipeline con fondo ─────────────────────────────────────

def opcion_optimizar_con_fondo(dir_originales: Path, dir_con_fondo: Path) -> bool:
    """6A — Igual que opcion_optimizar_gemini pero originales/ → con_fondo/."""
    console.print()
    console.rule("[bold cyan]Pipeline A — Optimizar fotos con fondo (→ con_fondo/)")
    console.print()

    fotos = listar_fotos(dir_originales)
    if not fotos:
        console.print(
            "  [yellow]No hay fotos en originales/.[/yellow]\n"
            "  [dim]Agregá fotos primero con las opciones [1] o [2].[/dim]"
        )
        return False

    mostrar_tabla_fotos(fotos, "originales/")

    seleccionadas: list[Path] = []
    while True:
        r = Prompt.ask(
            "[bold]¿Cuáles optimizar?[/bold] [dim](Enter = todas, números por coma, o 'ver N')[/dim]",
            default="",
        )
        raw = r.strip()
        if raw.lower().startswith("ver "):
            try:
                n = int(raw[4:].strip())
                if 1 <= n <= len(fotos):
                    abrir_foto(fotos[n - 1])
                else:
                    console.print(f"[red]Número {n} fuera de rango.[/red]")
            except ValueError:
                console.print("[red]Usá 'ver N'.[/red]")
            continue
        if not raw:
            seleccionadas = fotos
        else:
            indices = parsear_numeros(raw, len(fotos))
            if indices is None:
                continue
            seleccionadas = [fotos[i - 1] for i in indices]
        break

    console.print(
        "\n  [dim]Pipeline: autocrop → sharpening → contraste → saturación → 1024×1024[/dim]\n"
    )

    dir_con_fondo.mkdir(parents=True, exist_ok=True)
    optimizadas = 0
    for foto in seleccionadas:
        dest = dir_con_fondo / (foto.stem + ".jpg") if foto.suffix.lower() != ".jpg" else dir_con_fondo / foto.name
        size_antes = foto.stat().st_size
        try:
            with console.status(f"  Optimizando {foto.name}...", spinner="dots"):
                _optimizar_solo_pillow(foto, dest)
            size_despues = dest.stat().st_size
            delta = size_despues - size_antes
            signo = "+" if delta >= 0 else ""
            console.print(
                f"  [green]✓[/green] {foto.name} → con_fondo/{dest.name}  "
                f"[dim]{size_antes // 1024} KB → {size_despues // 1024} KB ({signo}{delta // 1024} KB)[/dim]"
            )
            optimizadas += 1
        except Exception as e:
            console.print(f"  [red]✗[/red] {foto.name}: {e}")

    if optimizadas:
        fotos_listas = listar_fotos(dir_con_fondo)
        total = sum(f.stat().st_size for f in fotos_listas)
        console.print()
        console.print(Panel(
            f"[bold green]{optimizadas} foto(s) optimizadas.[/bold green]\n"
            f"[dim]{dir_con_fondo}[/dim]\n"
            f"Total en con_fondo/: [bold]{len(fotos_listas)} foto(s)[/bold]  •  {total // 1024} KB",
            box=box.ROUNDED,
            padding=(0, 2),
        ))
        console.print()
    return optimizadas > 0


def opcion_agregar_texto_con_fondo(dir_con_fondo: Path, dir_con_texto: Path) -> bool:
    """7A — Igual que opcion_agregar_texto pero desde con_fondo/, sufijo _confondo.jpg."""
    console.print()
    console.rule("[bold cyan]Pipeline A — Agregar texto a fotos con fondo (→ con_texto/)")
    console.print()

    dir_con_fondo.mkdir(parents=True, exist_ok=True)
    fotos = listar_fotos(dir_con_fondo)

    if not fotos:
        console.print(
            "  [yellow]No hay fotos en con_fondo/.[/yellow]\n"
            "  [dim]Hacé primero la opción [6A].[/dim]"
        )
        return False

    mostrar_tabla_fotos(fotos, "con_fondo/")

    seleccionadas: list[Path] = []
    while True:
        r = Prompt.ask(
            "[bold]¿Cuáles procesar?[/bold] [dim](Enter = todas, números por coma, o 'ver N')[/dim]",
            default="",
        )
        raw = r.strip()
        if raw.lower().startswith("ver "):
            try:
                n = int(raw[4:].strip())
                if 1 <= n <= len(fotos):
                    abrir_foto(fotos[n - 1])
                else:
                    console.print(f"[red]Número {n} fuera de rango.[/red]")
            except ValueError:
                console.print("[red]Usá 'ver N'.[/red]")
            continue
        if not raw:
            seleccionadas = fotos
        else:
            indices = parsear_numeros(raw, len(fotos))
            if indices is None:
                continue
            seleccionadas = [fotos[i - 1] for i in indices]
        break

    if not seleccionadas:
        return False

    console.print()
    console.rule("[bold cyan]Datos para el diseño")
    console.print("[dim]Todo es opcional — presioná Enter para saltear.[/dim]\n")

    precio = Prompt.ask("[bold]Precio[/bold] [dim](ej: $18.900)[/dim]")
    precio = precio.strip() or "$0"
    specs  = Prompt.ask(
        "[bold]Especificaciones técnicas[/bold] [dim](ej: Talle 40 · Transparente · Apilable)[/dim]"
    ).strip()

    console.print()
    if not Confirm.ask("[bold]¿Aplicar diseño?[/bold]", default=True):
        console.print("[dim]Cancelado.[/dim]")
        return False

    dir_con_texto.mkdir(parents=True, exist_ok=True)
    procesadas = 0
    for foto in seleccionadas:
        dest = dir_con_texto / f"{foto.stem}_confondo.jpg"
        size_antes = foto.stat().st_size
        try:
            with console.status(f"  Procesando {foto.name}...", spinner="dots"):
                _agregar_texto_a_foto(foto, dest, precio, specs)
            size_despues = dest.stat().st_size
            console.print(
                f"  [green]✓[/green] {foto.name} → con_texto/{dest.name}  "
                f"[dim]{size_antes // 1024} KB → {size_despues // 1024} KB[/dim]"
            )
            procesadas += 1
        except Exception as e:
            console.print(f"  [red]✗[/red] {foto.name}: {e}")

    if procesadas:
        console.print()
        console.print(Panel(
            f"[bold green]{procesadas} foto(s) con texto (pipeline A) generadas.[/bold green]\n"
            f"[dim]Archivos: *_confondo.jpg en con_texto/[/dim]",
            box=box.ROUNDED,
            padding=(0, 2),
        ))
        console.print()
    return procesadas > 0


# ── Opción 3: Limpiar carpetas de salida ─────────────────────────────────────

def opcion_limpiar_resultados(dir_fotos: Path):
    """Borra carpetas de salida enteras o fotos individuales dentro de ellas."""
    CARPETAS_DEF = [
        ("con_fondo",     "con_fondo/"),
        ("procesadas",    "procesadas/"),
        ("listas_gemini", "listas_gemini/"),
        ("con_texto",     "con_texto/"),
    ]

    def _construir_filas() -> list:
        """Retorna lista de (label, path, n_fotos, kb) con datos actualizados."""
        filas = []
        for nombre, label in CARPETAS_DEF:
            path = dir_fotos / nombre
            if path.exists():
                fotos = listar_fotos(path)
                n  = len(fotos)
                kb = sum(f.stat().st_size for f in fotos) // 1024
            else:
                n, kb = 0, 0
            filas.append((label, path, n, kb))
        return filas

    def _mostrar_tabla_carpetas(filas: list):
        table = Table(box=box.ROUNDED, padding=(0, 1))
        table.add_column("N°",      style="bold cyan",  width=4,  justify="right")
        table.add_column("Carpeta", style="bold yellow", min_width=18)
        table.add_column("Fotos",   width=7,  justify="right")
        table.add_column("Tamaño",  width=10, justify="right")
        table.add_column("Estado",  width=12)
        for i, (label, path, n, kb) in enumerate(filas, 1):
            existe = path.exists()
            estado = "[green]existe[/green]" if existe else "[dim]no existe[/dim]"
            table.add_row(
                str(i), label,
                str(n) if existe else "—",
                f"{kb} KB" if existe else "—",
                estado,
            )
        console.print(table)
        console.print()

    # ── Encabezado y tabla inicial ─────────────────────────────────────────────
    console.print()
    console.rule("[bold cyan]Limpiar resultados")
    console.print()
    filas = _construir_filas()
    _mostrar_tabla_carpetas(filas)

    existentes = [(i + 1, label, path, n, kb)
                  for i, (label, path, n, kb) in enumerate(filas)
                  if path.exists()]
    if not existentes:
        console.print("  [dim]No hay carpetas de salida para limpiar.[/dim]\n")
        return

    # ── Elección de modo ───────────────────────────────────────────────────────
    table_modo = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table_modo.add_column("N°",  style="bold cyan", width=4)
    table_modo.add_column("Modo")
    table_modo.add_row("1", "Borrar carpeta entera")
    table_modo.add_row("2", "Borrar fotos individuales")
    console.print(table_modo)
    console.print()

    modo = Prompt.ask("[bold]Modo[/bold]", choices=["1", "2"], default="1")

    # ── MODO 1: Borrar carpeta entera ─────────────────────────────────────────
    if modo == "1":
        while True:
            raw = Prompt.ask(
                "[bold]¿Cuáles borrar?[/bold] [dim](número(s) por coma, 'todas', Enter para cancelar)[/dim]",
                default="",
            )
            raw = raw.strip()
            if not raw:
                console.print("[dim]Cancelado.[/dim]\n")
                return

            if raw.lower() == "todas":
                seleccionadas = existentes
                break

            indices = parsear_numeros(raw, len(filas))
            if indices is None:
                continue
            seleccionadas = [e for e in existentes if e[0] in indices]
            no_existen = [i for i in indices if i not in {e[0] for e in existentes}]
            if no_existen:
                console.print(f"  [yellow]Carpeta(s) {no_existen} no existen, se ignoran.[/yellow]")
            if not seleccionadas:
                console.print("  [yellow]Ninguna carpeta seleccionada existe.[/yellow]")
                continue
            break

        console.print()
        console.print("  [bold]Se borrarán:[/bold]")
        total_fotos = sum(n for _, _, _, n, _ in seleccionadas)
        for _, label, _, n, kb in seleccionadas:
            console.print(f"    [red]✗[/red] {label}  ({n} fotos, {kb} KB)")
        console.print()

        if not Confirm.ask(
            f"[bold red]¿Confirmar borrado de {total_fotos} foto(s) en "
            f"{len(seleccionadas)} carpeta(s)?[/bold red]",
            default=False,
        ):
            console.print("[dim]Cancelado. No se borró nada.[/dim]\n")
            return

        console.print()
        borradas = []
        for _, label, path, n, kb in seleccionadas:
            try:
                shutil.rmtree(path)
                console.print(f"  [green]✓[/green] {label} borrada  [dim]({n} fotos, {kb} KB)[/dim]")
                borradas.append(label)
            except Exception as e:
                console.print(f"  [red]✗[/red] Error borrando {label}: {e}")

        console.print()
        console.print(Panel(
            f"[bold green]{len(borradas)} carpeta(s) borrada(s).[/bold green]\n"
            f"[dim]{', '.join(borradas)}[/dim]",
            box=box.ROUNDED,
            padding=(0, 2),
        ))
        console.print()

    # ── MODO 2: Borrar fotos individuales ─────────────────────────────────────
    else:
        # Elegir carpeta
        while True:
            raw = Prompt.ask(
                "[bold]¿De qué carpeta?[/bold] [dim](número, Enter para cancelar)[/dim]",
                default="",
            )
            raw = raw.strip()
            if not raw:
                console.print("[dim]Cancelado.[/dim]\n")
                return
            indices = parsear_numeros(raw, len(filas))
            if indices is None or len(indices) != 1:
                console.print("[red]Ingresá un único número.[/red]")
                continue
            idx = indices[0]
            entrada = next((e for e in existentes if e[0] == idx), None)
            if entrada is None:
                console.print(f"[red]La carpeta {idx} no existe.[/red]")
                continue
            _, label, path_carpeta, _, _ = entrada
            break

        # Listar fotos de la carpeta elegida
        fotos = listar_fotos(path_carpeta)
        if not fotos:
            console.print(f"  [yellow]{label} está vacía.[/yellow]\n")
            return

        console.print()
        console.rule(f"[bold cyan]Fotos en {label}")
        console.print()
        mostrar_tabla_fotos(fotos, label)

        # Selección de fotos (con soporte "ver N")
        seleccionadas_fotos: list[Path] = []
        while True:
            raw = Prompt.ask(
                "[bold]¿Cuáles eliminar?[/bold] [dim](números por coma, 'ver N', 'ver todas', Enter para cancelar)[/dim]",
                default="",
            )
            raw = raw.strip()
            if not raw:
                console.print("[dim]Cancelado.[/dim]\n")
                return

            if raw.lower() == "ver todas":
                try:
                    subprocess.Popen(
                        ["eog", str(path_carpeta) + "/"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    console.print(f"  [dim]Abriendo {label} en eog... navegá con las flechas.[/dim]")
                except FileNotFoundError:
                    console.print("[yellow]'eog' no está instalado. Abrí la carpeta manualmente:[/yellow]")
                    console.print(f"  [dim]{path_carpeta}[/dim]")
                continue

            if raw.lower().startswith("ver "):
                try:
                    n = int(raw[4:].strip())
                    if 1 <= n <= len(fotos):
                        abrir_foto(fotos[n - 1])
                    else:
                        console.print(f"[red]Número {n} fuera de rango.[/red]")
                except ValueError:
                    console.print("[red]Usá 'ver N' o 'ver todas'.[/red]")
                continue

            indices = parsear_numeros(raw, len(fotos))
            if indices is None:
                continue
            seleccionadas_fotos = [fotos[i - 1] for i in indices]
            break

        # Confirmación
        console.print()
        console.print("  [bold]Se eliminarán:[/bold]")
        total_kb = 0
        for f in seleccionadas_fotos:
            kb = f.stat().st_size // 1024
            total_kb += kb
            console.print(f"    [red]✗[/red] {f.name}  [dim]{kb} KB[/dim]")
        console.print()

        if not Confirm.ask(
            f"[bold red]¿Confirmar eliminación de {len(seleccionadas_fotos)} foto(s)?[/bold red]",
            default=False,
        ):
            console.print("[dim]Cancelado. No se eliminó nada.[/dim]\n")
            return

        # Eliminar y renombrar secuencialmente
        console.print()
        eliminadas = 0
        for f in seleccionadas_fotos:
            try:
                f.unlink()
                console.print(f"  [green]✓[/green] {f.name} eliminada")
                eliminadas += 1
            except Exception as e:
                console.print(f"  [red]✗[/red] {f.name}: {e}")

        if eliminadas:
            quedan = listar_fotos(path_carpeta)
            if quedan:
                renombrar_secuencial(path_carpeta)
                console.print(f"  [dim]Fotos restantes renombradas secuencialmente ({len(quedan)} foto(s)).[/dim]")

        console.print()
        console.print(Panel(
            f"[bold green]{eliminadas} foto(s) eliminada(s) de {label}[/bold green]\n"
            f"[dim]{total_kb} KB liberados[/dim]",
            box=box.ROUNDED,
            padding=(0, 2),
        ))
        console.print()


# ── Resumen final ─────────────────────────────────────────────────────────────

def mostrar_resumen_final(directorio: Path):
    fotos = listar_fotos(directorio)
    total_bytes = sum(f.stat().st_size for f in fotos)

    console.print()
    console.rule("[bold green]Estado final de originales/")
    console.print()
    mostrar_tabla_fotos(fotos)

    console.print(Panel(
        f"[bold green]Listo.[/bold green]  "
        f"[bold]{len(fotos)}[/bold] foto(s) en [dim]{directorio.relative_to(KB_ROOT)}[/dim]  •  "
        f"{total_bytes // 1024} KB totales",
        box=box.ROUNDED,
        padding=(0, 2),
    ))
    console.print()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    mostrar_bienvenida()

    try:
        catalogo = cargar_catalogo()
        entrada = elegir_producto(catalogo)
        if entrada is None:
            console.print("[yellow]Cancelado.[/yellow]\n")
            sys.exit(0)

        sku = entrada["sku"]
        dir_fotos      = PRODUCTOS_BASE / sku / "fotos"
        dir_originales = dir_fotos / "originales"
        dir_procesadas = dir_fotos / "procesadas"
        dir_con_fondo  = dir_fotos / "con_fondo"
        dir_listas     = dir_fotos / "listas_gemini"
        dir_con_texto  = dir_fotos / "con_texto"
        dir_originales.mkdir(parents=True, exist_ok=True)
        dir_con_fondo.mkdir(parents=True, exist_ok=True)

        # ── Loop del menú ──────────────────────────────────────────────────────
        while True:
            console.print()
            console.rule(f"[bold cyan]{sku} — ¿Qué querés hacer?")
            console.print()

            table_menu = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
            table_menu.add_column("N°",    style="bold cyan", width=5)
            table_menu.add_column("Opción")

            table_menu.add_row("[dim]──[/dim]", "[bold]PIPELINE A: con fondo[/bold]")
            table_menu.add_row("1",  "Ver y eliminar fotos en originales/")
            table_menu.add_row("2",  "Agregar fotos propias a originales/")
            table_menu.add_row("11", "Ver fotos optimizadas con fondo (con_fondo/)")
            table_menu.add_row("6A", "Optimizar fotos con fondo → con_fondo/")
            table_menu.add_row("7A", "Agregar texto a fotos con fondo → con_texto/ (*_confondo.jpg)")

            table_menu.add_row("[dim]──[/dim]", "[bold]PIPELINE B: sin fondo[/bold]")
            table_menu.add_row("4",  "Procesar fotos con rembg → procesadas/")
            table_menu.add_row("5",  "Revisar procesadas — descartar las malas")
            table_menu.add_row("9",  "Centrar y normalizar → procesadas/")
            table_menu.add_row("6B", "Optimizar fotos sin fondo → listas_gemini/")
            table_menu.add_row("7B", "Agregar texto a fotos sin fondo → con_texto/ (*_sinfondo.jpg)")

            table_menu.add_row("[dim]──[/dim]", "[bold]UTILIDADES[/bold]")
            table_menu.add_row("3",  "Limpiar resultados — borrar carpetas de salida")
            table_menu.add_row("8",  "Detectar y descartar fotos malas en originales/")
            table_menu.add_row("10", "Generar collage multi-ángulo")
            table_menu.add_row("0",  "Salir")

            console.print(table_menu)
            console.print()

            opcion = Prompt.ask(
                "[bold]Opción[/bold]",
                choices=["0","1","2","3","4","5","6a","6b","7a","7b","8","9","10","11"],
                default="0",
            )
            opcion = opcion.lower()

            if opcion == "0":
                console.print("[dim]Hasta luego.[/dim]\n")
                break

            elif opcion == "1":
                opcion_ver_eliminar(dir_originales)
                fotos_orig = listar_fotos(dir_originales)
                if fotos_orig:
                    renombrar_secuencial(dir_originales)
                mostrar_resumen_final(dir_originales)

            elif opcion == "2":
                opcion_agregar_fotos(dir_originales)
                fotos_orig = listar_fotos(dir_originales)
                if fotos_orig:
                    renombrar_secuencial(dir_originales)
                mostrar_resumen_final(dir_originales)

            elif opcion == "3":
                opcion_limpiar_resultados(dir_fotos)

            elif opcion == "4":
                opcion_procesar_fotos(dir_originales, dir_procesadas)

            elif opcion == "5":
                opcion_revisar_procesadas(dir_procesadas)
                fotos_proc = listar_fotos(dir_procesadas)
                total = sum(f.stat().st_size for f in fotos_proc)
                console.print()
                console.print(Panel(
                    f"[bold green]Listo.[/bold green]  "
                    f"[bold]{len(fotos_proc)}[/bold] foto(s) en [dim]fotos/procesadas/[/dim]  •  "
                    f"{total // 1024} KB totales",
                    box=box.ROUNDED,
                    padding=(0, 2),
                ))
                console.print()

            elif opcion == "6a":
                opcion_optimizar_con_fondo(dir_originales, dir_con_fondo)

            elif opcion == "6b":
                opcion_optimizar_gemini(dir_procesadas, dir_listas)

            elif opcion == "7a":
                opcion_agregar_texto_con_fondo(dir_con_fondo, dir_con_texto)

            elif opcion == "7b":
                opcion_agregar_texto(dir_listas, dir_con_texto)

            elif opcion == "8":
                opcion_filtrar_calidad(dir_originales)

            elif opcion == "9":
                opcion_centrar_producto(dir_procesadas)

            elif opcion == "10":
                opcion_collage(dir_procesadas)

            elif opcion == "11":
                if not dir_con_fondo.exists() or not listar_fotos(dir_con_fondo):
                    console.print("\n  [yellow]con_fondo/ está vacía o no existe. "
                                  "Primero ejecutá la opción [6A].[/yellow]\n")
                else:
                    try:
                        subprocess.Popen(
                            ["eog", str(dir_con_fondo) + "/"],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                        console.print(f"\n  [dim]Abriendo con_fondo/ en eog... navegá con las flechas.[/dim]\n")
                    except FileNotFoundError:
                        console.print("[yellow]'eog' no está instalado. Abrí la carpeta manualmente:[/yellow]")
                        console.print(f"  [dim]{dir_con_fondo}[/dim]\n")

    except (KeyboardInterrupt, EOFError):
        console.print("\n[yellow]Cancelado.[/yellow]\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
