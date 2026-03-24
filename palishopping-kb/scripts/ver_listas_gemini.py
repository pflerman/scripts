#!/usr/bin/env python3
"""
ver_listas_gemini.py — Abrí la carpeta listas_gemini/ de un producto en Nautilus.
"""

import json
import subprocess
import sys
from pathlib import Path

from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table
from rich import box

KB_ROOT = Path(__file__).resolve().parent.parent
PRODUCTOS_BASE = KB_ROOT / "productos-base"
CATALOGO = KB_ROOT / "catalogo.json"

console = Console()


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


def mostrar_tabla_catalogo(catalogo: list) -> dict:
    table = Table(box=box.ROUNDED, show_lines=False, padding=(0, 1))
    table.add_column("N°",     style="bold cyan",   width=4,  justify="right")
    table.add_column("SKU",    style="bold yellow",  min_width=14)
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


def main():
    catalogo = cargar_catalogo()
    entrada = elegir_producto(catalogo)
    if entrada is None:
        console.print("[yellow]Cancelado.[/yellow]")
        sys.exit(0)

    sku = entrada["sku"]
    ruta = PRODUCTOS_BASE / sku / "fotos" / "listas_gemini"

    if not ruta.exists():
        console.print(f"[red]No existe: {ruta}[/red]")
        sys.exit(1)

    subprocess.Popen(["nautilus", "--no-desktop", str(ruta)])


if __name__ == "__main__":
    main()
