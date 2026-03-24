#!/usr/bin/env python3
"""Importa fotos generadas por Gemini desde Downloads al producto correspondiente."""

import json
import re
import shutil
import sys
import unicodedata
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

console = Console()

BASE_DIR = Path(__file__).parent.parent
CATALOGO_PATH = BASE_DIR / "catalogo.json"
DOWNLOADS_DIR = Path.home() / "Downloads"


def normalizar(texto):
    """Convierte a minúsculas, saca tildes y reemplaza espacios por guiones."""
    texto = texto.lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"\s+", "-", texto.strip())
    return texto


def buscar_fotos():
    fotos = sorted(DOWNLOADS_DIR.glob("Generated Image*.png"))
    return fotos


def cargar_catalogo():
    skus = json.loads(CATALOGO_PATH.read_text())
    productos = []
    for sku in skus:
        path = BASE_DIR / "productos-base" / sku / "producto.json"
        if path.exists():
            productos.append(json.loads(path.read_text()))
    return productos


def mostrar_productos(productos):
    table = Table(title="Productos disponibles", show_header=True, header_style="bold cyan")
    table.add_column("#", style="dim", width=4)
    table.add_column("SKU", style="bold")
    table.add_column("Nombre")
    table.add_column("Tipo", style="dim")
    table.add_column("Stock", justify="right")

    for i, p in enumerate(productos, 1):
        table.add_row(
            str(i),
            p["sku"],
            p["nombre"],
            p.get("tipo", ""),
            str(p.get("stock", "-")),
        )
    console.print(table)


def elegir_producto(productos):
    mostrar_productos(productos)
    while True:
        eleccion = Prompt.ask("\nElegí el producto al que pertenecen las fotos [bold](número o SKU)[/bold]")
        if eleccion.isdigit():
            idx = int(eleccion) - 1
            if 0 <= idx < len(productos):
                return productos[idx]
            console.print(f"[red]Número inválido. Ingresá entre 1 y {len(productos)}.[/red]")
        else:
            sku = eleccion.upper()
            match = next((p for p in productos if p["sku"] == sku), None)
            if match:
                return match
            console.print(f"[red]SKU '{sku}' no encontrado.[/red]")


def cargar_producto_json(sku):
    path = BASE_DIR / "productos-base" / sku / "producto.json"
    if not path.exists():
        console.print(f"[red]No se encontró producto.json en {path}[/red]")
        sys.exit(1)
    with open(path) as f:
        return json.load(f)


def detectar_siguiente_numero(destino_dir):
    """Retorna el siguiente número libre basado en los archivos existentes."""
    existentes = list(destino_dir.glob("*.png")) + list(destino_dir.glob("*.jpg"))
    if not existentes:
        return 1
    numeros = []
    for f in existentes:
        match = re.search(r"-(\d+)\.[a-z]+$", f.name)
        if match:
            numeros.append(int(match.group(1)))
    return max(numeros, default=0) + 1


def main():
    console.print(Panel("[bold cyan]Importador de fotos Gemini[/bold cyan]", border_style="cyan"))

    # 1. Buscar fotos en Downloads
    fotos = buscar_fotos()
    if not fotos:
        console.print(
            Panel(
                f'[red bold]No se encontraron archivos "Generated Image*.png" en {DOWNLOADS_DIR}[/red bold]\n'
                "Descargá las imágenes de Gemini AI Studio antes de ejecutar este script.",
                title="Sin fotos",
                border_style="red",
            )
        )
        sys.exit(1)

    console.print(f"[green]✓ Se encontraron [bold]{len(fotos)}[/bold] foto(s) en {DOWNLOADS_DIR}[/green]\n")

    # 2. Elegir producto
    productos = cargar_catalogo()
    producto = elegir_producto(productos)
    sku = producto["sku"]
    console.print(f"\n[green]Producto seleccionado:[/green] [bold]{sku}[/bold] — {producto['nombre']}\n")

    # 3. Leer tipo y color del JSON del producto
    datos = cargar_producto_json(sku)
    tipo_raw = datos.get("tipo", "")
    color_raw = datos.get("variante", {}).get("color", "")

    if not tipo_raw or not color_raw:
        console.print(f"[red]El producto.json no tiene 'tipo' o 'variante.color' definidos.[/red]")
        sys.exit(1)

    tipo = normalizar(tipo_raw)
    color = normalizar(color_raw)
    prefijo = f"{tipo}-{color}-lifestyle"
    console.print(f"[dim]Prefijo SEO:[/dim] [bold]{prefijo}-NN.png[/bold]\n")

    # 4. Crear carpeta destino
    destino_dir = BASE_DIR / "productos-base" / sku / "fotos" / "gemini"
    destino_dir.mkdir(parents=True, exist_ok=True)

    # 5. Detectar numeración existente
    siguiente = detectar_siguiente_numero(destino_dir)

    # 6. Mover fotos
    movidas = []
    for i, foto in enumerate(fotos):
        n = siguiente + i
        nuevo_nombre = f"{prefijo}-{n:02d}.png"
        destino = destino_dir / nuevo_nombre
        shutil.move(str(foto), str(destino))
        movidas.append((foto.name, nuevo_nombre))

    # 7. Resumen
    table = Table(title=f"Resumen — {len(movidas)} foto(s) importada(s)", header_style="bold green")
    table.add_column("Archivo original", style="dim")
    table.add_column("Nombre nuevo", style="bold")
    table.add_column("Destino", style="dim")

    ruta_rel = destino_dir.relative_to(BASE_DIR)
    for orig, nuevo in movidas:
        table.add_row(orig, nuevo, str(ruta_rel))

    console.print(table)
    console.print(f"\n[green bold]✓ {len(movidas)} foto(s) movida(s) a productos-base/{sku}/fotos/gemini/[/green bold]")


if __name__ == "__main__":
    main()
