#!/usr/bin/env python3
"""
actualizar_precio.py — Actualiza el precio de costo de un producto base en la KB de Palishopping.

Uso: python3 actualizar_precio.py
"""

import json
import sys
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich import box

KB_ROOT = Path(__file__).resolve().parent.parent
PRODUCTOS_BASE = KB_ROOT / "productos-base"
CATALOGO = KB_ROOT / "catalogo.json"

console = Console()


# ── Helpers ───────────────────────────────────────────────────────────────────

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


def cargar_producto_json(sku: str) -> dict | None:
    path = PRODUCTOS_BASE / sku / "producto.json"
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def guardar_producto_json(sku: str, data: dict):
    path = PRODUCTOS_BASE / sku / "producto.json"
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def fmt_precio(valor: float) -> str:
    return f"${valor:,.2f}"


# ── Interfaz ──────────────────────────────────────────────────────────────────

def mostrar_bienvenida():
    console.print()
    console.print(Panel(
        "[bold cyan]Actualizar Precio de Costo — Palishopping KB[/bold cyan]\n"
        "[dim]Modifica el precio de costo de un producto base existente.[/dim]",
        box=box.ROUNDED,
        padding=(0, 2),
    ))
    console.print()


def mostrar_tabla(catalogo: list) -> dict:
    """Muestra la tabla de productos y devuelve un dict {numero: entrada}."""
    table = Table(box=box.ROUNDED, show_lines=False, padding=(0, 1))
    table.add_column("N°",           style="bold cyan",  width=4,  justify="right")
    table.add_column("SKU",          style="bold yellow", min_width=14)
    table.add_column("Nombre",       min_width=30)
    table.add_column("Precio costo", style="bold white",  width=14, justify="right")

    indice = {}
    for i, entrada in enumerate(catalogo, 1):
        precio = entrada.get("precio_costo", 0)
        table.add_row(str(i), entrada["sku"], entrada["nombre"], fmt_precio(precio))
        indice[str(i)] = entrada

    console.print(table)
    console.print()
    return indice


def elegir_producto(catalogo: list) -> dict | None:
    if not catalogo:
        console.print("[yellow]El catálogo está vacío. Primero creá un producto con nuevo_producto.py[/yellow]")
        return None

    console.rule("[bold cyan]Productos disponibles")
    console.print()
    indice = mostrar_tabla(catalogo)

    skus = {e["sku"].upper(): e for e in catalogo}
    numeros = list(indice.keys())

    while True:
        respuesta = Prompt.ask(
            f"[bold]Elegí un producto[/bold] [dim](número 1-{len(catalogo)} o SKU, Enter para cancelar)[/dim]",
            default="",
        )

        if not respuesta.strip():
            return None

        if respuesta.strip() in numeros:
            return indice[respuesta.strip()]

        clave = respuesta.strip().upper()
        if clave in skus:
            return skus[clave]

        console.print("[red]No encontrado. Ingresá un número de la lista o el SKU exacto.[/red]")


def pedir_nuevo_precio(sku: str, precio_actual: float) -> float | None:
    console.print()
    console.print(f"  Precio de costo actual de [bold yellow]{sku}[/bold yellow]: [bold]{fmt_precio(precio_actual)}[/bold] ARS")
    console.print()

    while True:
        valor = Prompt.ask(
            "[bold]Nuevo precio de costo[/bold] [dim](ARS, Enter para cancelar)[/dim]",
            default="",
        )

        if not valor.strip():
            return None

        try:
            nuevo = float(valor.strip().replace(",", ".").replace("$", "").replace(" ", ""))
            if nuevo < 0:
                console.print("[red]El precio no puede ser negativo.[/red]")
                continue
            return nuevo
        except ValueError:
            console.print("[red]Ingresá un número válido (ej: 3500 o 3500.50).[/red]")


def mostrar_confirmacion(sku: str, precio_viejo: float, precio_nuevo: float) -> bool:
    diferencia = precio_nuevo - precio_viejo
    signo = "+" if diferencia >= 0 else ""
    color = "green" if diferencia >= 0 else "red"

    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table.add_column("Campo", style="bold cyan", min_width=18)
    table.add_column("Valor")
    table.add_row("SKU",                 f"[bold yellow]{sku}[/bold yellow]")
    table.add_row("Precio actual",       f"[dim]{fmt_precio(precio_viejo)}[/dim]")
    table.add_row("Nuevo precio",        f"[bold green]{fmt_precio(precio_nuevo)}[/bold green]")
    table.add_row("Diferencia",          f"[{color}]{signo}{fmt_precio(diferencia)}[/{color}]")

    console.print()
    console.print(table)
    console.print()
    return Confirm.ask("[bold]¿Confirmar cambio?[/bold]", default=True)


def actualizar(sku: str, precio_nuevo: float):
    now = datetime.now().isoformat(timespec="seconds")

    producto = cargar_producto_json(sku)
    if producto is not None:
        producto["precio_costo"] = precio_nuevo
        producto["ultima_actualizacion"] = now
        guardar_producto_json(sku, producto)


def mostrar_resultado(sku: str, precio_viejo: float, precio_nuevo: float):
    diferencia = precio_nuevo - precio_viejo
    signo = "+" if diferencia >= 0 else ""
    color = "green" if diferencia >= 0 else "red"

    console.print()
    console.print(Panel(
        f"[bold green]Precio actualizado.[/bold green]\n"
        f"[bold yellow]{sku}[/bold yellow]: "
        f"[dim]{fmt_precio(precio_viejo)}[/dim] → [bold]{fmt_precio(precio_nuevo)}[/bold]  "
        f"[{color}]({signo}{fmt_precio(diferencia)})[/{color}]",
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
        precio_actual = entrada.get("precio_costo", 0.0)

        console.rule("[bold cyan]Actualizar precio de costo")
        precio_nuevo = pedir_nuevo_precio(sku, precio_actual)

        if precio_nuevo is None:
            console.print("\n[yellow]Cancelado.[/yellow]\n")
            sys.exit(0)

        if not mostrar_confirmacion(sku, precio_actual, precio_nuevo):
            console.print("[yellow]Cancelado. No se realizaron cambios.[/yellow]\n")
            sys.exit(0)

        actualizar(sku, precio_nuevo)
        mostrar_resultado(sku, precio_actual, precio_nuevo)

    except (KeyboardInterrupt, EOFError):
        console.print("\n[yellow]Cancelado.[/yellow]\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
