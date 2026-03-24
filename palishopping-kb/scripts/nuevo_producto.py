#!/usr/bin/env python3
"""
nuevo_producto.py — Agrega un producto base a la Knowledge Base de Palishopping.

Uso: python3 nuevo_producto.py
"""

import json
import sys
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich import box
from rich.text import Text

KB_ROOT = Path(__file__).resolve().parent.parent
PRODUCTOS_BASE = KB_ROOT / "productos-base"
CATALOGO = KB_ROOT / "catalogo.json"
PROVEEDORES_DIR = KB_ROOT / "proveedores"

console = Console()

# ── Mapeo de tipos a prefijos SKU ────────────────────────────────────────────

TIPOS = {
    "1": ("ORG-ZAP", "Organizador de zapatos"),
    "2": ("ORG-BOT", "Organizador de botas"),
    "3": ("ORG-COL", "Organizador colgante"),
    "4": ("BOL-VAC", "Bolsa al vacío"),
    "5": ("PER-ROP", "Percha ropa"),
    "6": ("CAJ-DEC", "Caja decorada"),
    "7": ("MISC",    "Otro / Misceláneo"),
    "8": ("ARM-MOD", "Armario modular"),
}

COLORES_ABREV = {
    "blanco":   "BLA",
    "negro":    "NEG",
    "gris":     "GRI",
    "beige":    "BEI",
    "rosa":     "ROS",
    "rojo":     "ROJ",
    "azul":     "AZU",
    "verde":    "VER",
    "amarillo": "AMA",
    "marron":   "MAR",
    "transparente": "TRA",
    "multicolor":   "MUL",
}

def _cargar_modelos() -> dict:
    path = Path(__file__).resolve().parent.parent / "modelos.json"
    items = json.loads(path.read_text())
    return {m["codigo"]: m["nombre"] for m in items}

MODELOS = _cargar_modelos()

PROVEEDORES = ["andres", "sao-bernardo"]

FACTOR_NACIONALIZACION = 1.9


# ── Helpers ───────────────────────────────────────────────────────────────────

def obtener_tipo_cambio_blue() -> float:
    url = "https://api.bluelytics.com.ar/v2/latest"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())
    return float(data["blue"]["value_sell"])

def abreviar_color(color: str) -> str:
    c = color.strip().lower()
    for nombre, abrev in COLORES_ABREV.items():
        if c.startswith(nombre[:4]):
            return abrev
    # Tomar primeras 3 letras en mayúscula si no hay match
    return c[:3].upper()


def normalizar_talle(talle: str) -> str:
    t = talle.strip().upper()
    # Eliminar espacios y caracteres raros
    return t.replace(" ", "").replace("/", "-")[:6]


def generar_sku(prefijo: str, modelo: str, color: str, talle: str) -> str:
    partes = [prefijo, modelo]
    color_abrev = abreviar_color(color)
    if color_abrev:
        partes.append(color_abrev)
    talle_norm = normalizar_talle(talle)
    if talle_norm:
        partes.append(talle_norm)
    return "-".join(partes)


def sku_existe(sku: str) -> bool:
    return (PRODUCTOS_BASE / sku).exists()


def cargar_catalogo_skus() -> list[str]:
    if CATALOGO.exists():
        with open(CATALOGO) as f:
            return json.load(f)
    return []


def guardar_catalogo_skus(skus: list[str]):
    with open(CATALOGO, "w") as f:
        json.dump(skus, f, ensure_ascii=False, indent=2)


# ── Interfaz ──────────────────────────────────────────────────────────────────

def mostrar_bienvenida():
    console.print()
    console.print(Panel(
        "[bold cyan]Nuevo Producto — Palishopping KB[/bold cyan]\n"
        "[dim]Crea un producto base y lo registra en el catálogo.[/dim]",
        box=box.ROUNDED,
        padding=(0, 2),
    ))
    console.print()


def elegir_tipo() -> tuple[str, str]:
    """Devuelve (prefijo_sku, nombre_tipo)."""
    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table.add_column("N°", style="bold cyan", width=4)
    table.add_column("Prefijo", style="bold yellow", width=10)
    table.add_column("Tipo")
    for num, (prefijo, nombre) in TIPOS.items():
        table.add_row(num, prefijo, nombre)
    console.print(table)

    while True:
        opcion = Prompt.ask("[bold]Tipo de producto[/bold]", choices=list(TIPOS.keys()))
        return TIPOS[opcion]


def elegir_modelo() -> tuple[str, str]:
    """Devuelve (codigo_modelo, nombre_modelo)."""
    items = list(MODELOS.items())
    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table.add_column("N°", style="bold cyan", width=4)
    table.add_column("Código", style="bold yellow", width=6)
    table.add_column("Modelo")
    for i, (cod, nombre) in enumerate(items, 1):
        table.add_row(str(i), cod, nombre)
    console.print(table)

    while True:
        opcion = Prompt.ask("[bold]Modelo[/bold]", choices=[str(i) for i in range(1, len(items)+1)])
        return items[int(opcion) - 1]


def elegir_proveedor() -> str:
    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table.add_column("N°", style="bold cyan", width=4)
    table.add_column("Proveedor")
    for i, p in enumerate(PROVEEDORES, 1):
        table.add_row(str(i), p)
    console.print(table)

    while True:
        opcion = Prompt.ask("[bold]Proveedor[/bold]", choices=[str(i) for i in range(1, len(PROVEEDORES)+1)])
        return PROVEEDORES[int(opcion) - 1]


def pedir_precio_andres() -> dict:
    """Pide FOB en USD, obtiene tipo de cambio y calcula precio en ARS. Retorna campos extra para datos."""
    fob_str = Prompt.ask("\n[bold]Precio FOB[/bold] [dim](USD, ej: 0.52)[/dim]")
    try:
        fob_usd = float(fob_str.replace(",", ".").replace("$", "").strip())
    except ValueError:
        console.print("[red]Precio inválido, se usará 0.[/red]")
        fob_usd = 0.0

    console.print("  [dim]Obteniendo tipo de cambio dólar blue...[/dim]")
    try:
        tipo_cambio = obtener_tipo_cambio_blue()
    except Exception as e:
        console.print(f"[red]Error al obtener tipo de cambio: {e}[/red]")
        tc_str = Prompt.ask("[bold]Ingresá el tipo de cambio manualmente[/bold] [dim](ARS/USD)[/dim]")
        try:
            tipo_cambio = float(tc_str.replace(",", ".").strip())
        except ValueError:
            tipo_cambio = 0.0

    fob_nacionalizado_usd = fob_usd * FACTOR_NACIONALIZACION
    precio_costo = fob_nacionalizado_usd * tipo_cambio

    console.print()
    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table.add_column("Concepto", style="bold cyan", min_width=30)
    table.add_column("Valor", justify="right")
    table.add_row("FOB original",                  f"USD {fob_usd:.4f}")
    table.add_row(f"Factor nacionalización (×{FACTOR_NACIONALIZACION})", f"USD {fob_nacionalizado_usd:.4f}")
    table.add_row(f"Tipo de cambio blue (venta)",   f"${tipo_cambio:,.2f}")
    table.add_row("[bold green]Precio de costo ARS[/bold green]", f"[bold green]${precio_costo:,.2f}[/bold green]")
    console.print(table)
    console.print()

    return {
        "precio_fob_usd": fob_usd,
        "factor_nacionalizacion": FACTOR_NACIONALIZACION,
        "tipo_cambio_usado": tipo_cambio,
        "precio_costo": precio_costo,
    }


def pedir_datos() -> dict:
    console.rule("[bold cyan]Datos del producto")
    console.print()

    nombre = Prompt.ask("[bold]Nombre del producto[/bold]")

    console.print("\n[bold]Tipo de producto:[/bold]")
    prefijo_sku, tipo_nombre = elegir_tipo()

    console.print("\n[bold]Modelo:[/bold]")
    modelo_cod, modelo_nombre = elegir_modelo()

    color = Prompt.ask("\n[bold]Color[/bold]", default="Blanco")
    talle = Prompt.ask("[bold]Talle / Tamaño[/bold] [dim](ej: 40, L, 30x20cm, vacío si no aplica)[/dim]", default="")

    console.print("\n[bold]Dimensiones[/bold] [dim](opcional — Enter para omitir)[/dim]")
    dimensiones = {}
    for campo, etiqueta in [("largo_cm", "Largo (cm)"), ("ancho_cm", "Ancho (cm)"), ("alto_cm", "Alto (cm)")]:
        val = Prompt.ask(f"  [bold]{etiqueta}[/bold]", default="").strip()
        if val:
            try:
                dimensiones[campo] = float(val.replace(",", "."))
            except ValueError:
                console.print(f"  [yellow]Valor inválido para {etiqueta}, se omite.[/yellow]")

    console.print("\n[bold]Proveedor:[/bold]")
    proveedor = elegir_proveedor()

    precio_extra = {}
    if proveedor == "andres":
        precio_extra = pedir_precio_andres()
    else:
        precio_str = Prompt.ask("\n[bold]Precio de costo[/bold] [dim](ARS)[/dim]")
        try:
            precio_costo = float(precio_str.replace(",", ".").replace("$", "").strip())
        except ValueError:
            console.print("[red]Precio inválido, se usará 0.[/red]")
            precio_costo = 0.0
        precio_extra = {"precio_costo": precio_costo}

    stock_str = Prompt.ask("[bold]Stock inicial[/bold]", default="0")
    try:
        stock = int(stock_str)
    except ValueError:
        stock = 0

    notas = Prompt.ask("[bold]Notas[/bold] [dim](opcional)[/dim]", default="")

    return {
        "nombre": nombre,
        "tipo": tipo_nombre,
        "prefijo_sku": prefijo_sku,
        "modelo_cod": modelo_cod,
        "modelo": modelo_nombre,
        "color": color,
        "talle": talle,
        "dimensiones": dimensiones,
        "proveedor": proveedor,
        **precio_extra,
        "stock": stock,
        "notas": notas,
    }


def confirmar_sku(datos: dict) -> str | None:
    """Muestra el SKU generado y permite confirmar, editar o cancelar. Retorna el SKU final o None."""
    sku_auto = generar_sku(datos["prefijo_sku"], datos["modelo_cod"], datos["color"], datos["talle"])

    console.print()
    console.rule("[bold cyan]SKU generado")
    console.print()
    console.print(f"  [bold yellow]{sku_auto}[/bold yellow]")
    console.print()

    if sku_existe(sku_auto):
        console.print(f"[yellow]Advertencia:[/yellow] Ya existe un producto con SKU [bold]{sku_auto}[/bold].")

    while True:
        opcion = Prompt.ask(
            "[bold]¿Qué hacemos?[/bold]",
            choices=["confirmar", "editar", "cancelar"],
            default="confirmar",
        )

        if opcion == "cancelar":
            return None

        if opcion == "editar":
            sku_nuevo = Prompt.ask("[bold]Ingresá el SKU manualmente[/bold]", default=sku_auto)
            sku_nuevo = sku_nuevo.strip().upper()
            if not sku_nuevo:
                console.print("[red]SKU vacío, intenta de nuevo.[/red]")
                continue
            if sku_existe(sku_nuevo):
                console.print(f"[yellow]Advertencia:[/yellow] Ya existe un producto con SKU [bold]{sku_nuevo}[/bold].")
                if not Confirm.ask("¿Continuar igual?", default=False):
                    continue
            return sku_nuevo

        # confirmar
        if sku_existe(sku_auto):
            if not Confirm.ask("Ya existe ese SKU. ¿Continuar igual?", default=False):
                continue
        return sku_auto


def crear_estructura(sku: str, datos: dict) -> Path:
    """Crea carpetas y archivos del producto. Retorna el directorio raíz del producto."""
    producto_dir = PRODUCTOS_BASE / sku
    now = datetime.now().isoformat(timespec="seconds")

    # Carpetas
    (producto_dir / "fotos" / "originales").mkdir(parents=True, exist_ok=True)
    (producto_dir / "fotos" / "generadas").mkdir(parents=True, exist_ok=True)
    (producto_dir / "media").mkdir(parents=True, exist_ok=True)
    (producto_dir / "inteligencia").mkdir(parents=True, exist_ok=True)

    # producto.json
    producto_json = {
        "sku": sku,
        "nombre": datos["nombre"],
        "tipo": datos["tipo"],
        "variante": {
            "modelo": datos["modelo"],
            "color": datos["color"],
            "talle": datos["talle"],
        },
        **({"dimensiones": datos["dimensiones"]} if datos.get("dimensiones") else {}),
        "proveedor": datos["proveedor"],
        **({"precio_fob_usd": datos["precio_fob_usd"],
            "factor_nacionalizacion": datos["factor_nacionalizacion"],
            "tipo_cambio_usado": datos["tipo_cambio_usado"]} if datos["proveedor"] == "andres" else {}),
        "precio_costo": datos["precio_costo"],
        "stock": datos["stock"],
        "descripcion": "",
        "titulo_ml": "",
        "titulo_web": "",
        "palabras_clave": [],
        "ml_categoria_id": "",
        "listings": [],
        "notas": datos["notas"],
        "fecha_creacion": now,
        "ultima_actualizacion": now,
    }
    with open(producto_dir / "producto.json", "w") as f:
        json.dump(producto_json, f, ensure_ascii=False, indent=2)

    # inteligencia/reviews.json y preguntas.json
    with open(producto_dir / "inteligencia" / "reviews.json", "w") as f:
        json.dump([], f)
    with open(producto_dir / "inteligencia" / "preguntas.json", "w") as f:
        json.dump([], f)

    return producto_dir


def agregar_a_catalogo(sku: str):
    skus = cargar_catalogo_skus()
    skus.append(sku)
    guardar_catalogo_skus(skus)


def mostrar_resumen(sku: str, datos: dict, producto_dir: Path):
    console.print()
    console.rule("[bold green]Producto creado exitosamente")
    console.print()

    table = Table(box=box.ROUNDED, show_header=False, padding=(0, 2))
    table.add_column("Campo", style="bold cyan", min_width=20)
    table.add_column("Valor")

    table.add_row("SKU",           f"[bold yellow]{sku}[/bold yellow]")
    table.add_row("Nombre",        datos["nombre"])
    table.add_row("Tipo",          datos["tipo"])
    table.add_row("Modelo",        f"{datos['modelo_cod']} — {datos['modelo']}")
    table.add_row("Color",         datos["color"])
    table.add_row("Talle",         datos["talle"] or "[dim]—[/dim]")
    if datos.get("dimensiones"):
        d = datos["dimensiones"]
        partes = [f"{d[k]} cm" for k in ("largo_cm", "ancho_cm", "alto_cm") if k in d]
        table.add_row("Dimensiones", " × ".join(partes))
    table.add_row("Proveedor",     datos["proveedor"])
    if datos["proveedor"] == "andres":
        table.add_row("FOB USD",           f"USD {datos['precio_fob_usd']:.4f}")
        table.add_row("Factor nacionalización", f"×{datos['factor_nacionalizacion']}")
        table.add_row("Tipo de cambio blue",    f"${datos['tipo_cambio_usado']:,.2f}")
    table.add_row("Precio costo",  f"${datos['precio_costo']:,.2f} ARS")
    table.add_row("Stock inicial", str(datos["stock"]))
    table.add_row("Notas",         datos["notas"] or "[dim]—[/dim]")

    console.print(table)
    console.print()

    # Archivos creados
    archivos = [
        producto_dir / "producto.json",
        producto_dir / "inteligencia" / "reviews.json",
        producto_dir / "inteligencia" / "preguntas.json",
    ]
    carpetas = [
        producto_dir / "fotos" / "originales",
        producto_dir / "fotos" / "generadas",
        producto_dir / "media",
        producto_dir / "inteligencia",
    ]

    console.print("[bold]Archivos creados:[/bold]")
    for a in archivos:
        console.print(f"  [green]✓[/green] {a.relative_to(KB_ROOT)}")

    console.print()
    console.print("[bold]Carpetas creadas:[/bold]")
    for c in carpetas:
        console.print(f"  [blue]📁[/blue] {c.relative_to(KB_ROOT)}/")

    console.print()
    console.print(f"  [green]✓[/green] Entrada agregada en [bold]catalogo.json[/bold]")
    console.print()
    console.print(Panel(
        f"[bold green]Listo.[/bold green] Producto [bold yellow]{sku}[/bold yellow] registrado en la KB.",
        box=box.ROUNDED,
        padding=(0, 2),
    ))
    console.print()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    mostrar_bienvenida()

    try:
        datos = pedir_datos()
    except (KeyboardInterrupt, EOFError):
        console.print("\n[yellow]Cancelado.[/yellow]")
        sys.exit(0)

    console.print()
    sku = confirmar_sku(datos)

    if sku is None:
        console.print("\n[yellow]Operación cancelada. No se creó ningún producto.[/yellow]\n")
        sys.exit(0)

    producto_dir = crear_estructura(sku, datos)
    agregar_a_catalogo(sku)
    mostrar_resumen(sku, datos, producto_dir)


if __name__ == "__main__":
    main()
