#!/usr/bin/env python3
"""
crear_bundle.py — Armá un bundle de productos y guardalo en bundles/<slug>.json
"""

import json
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

KB_ROOT = Path(__file__).resolve().parent.parent
PRODUCTOS_BASE = KB_ROOT / "productos-base"
BUNDLES_DIR = KB_ROOT / "bundles"
CATALOGO = KB_ROOT / "catalogo.json"

MARGEN = 2.5  # precio_venta_sugerido = costo_total * MARGEN

console = Console()


# ── utilidades ────────────────────────────────────────────────────────────────

def slugify(texto: str) -> str:
    texto = texto.lower().strip()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"[^\w\s-]", "", texto)
    texto = re.sub(r"[\s_]+", "-", texto)
    return texto


def cargar_catalogo() -> list[dict]:
    if not CATALOGO.exists():
        console.print("[red]No se encontró catalogo.json[/red]")
        sys.exit(1)
    skus = json.loads(CATALOGO.read_text())
    productos = []
    for sku in skus:
        path = PRODUCTOS_BASE / sku / "producto.json"
        if path.exists():
            productos.append(json.loads(path.read_text()))
    return productos


def mostrar_tabla_catalogo(catalogo: list) -> dict:
    table = Table(box=box.ROUNDED, show_lines=False, padding=(0, 1))
    table.add_column("N°",     style="bold cyan",  width=4,  justify="right")
    table.add_column("SKU",    style="bold yellow", min_width=14)
    table.add_column("Nombre", min_width=30)
    table.add_column("Tipo",   min_width=18)
    table.add_column("Costo",  justify="right", style="green")

    indice = {}
    for i, entrada in enumerate(catalogo, 1):
        table.add_row(
            str(i),
            entrada["sku"],
            entrada["nombre"],
            entrada.get("tipo", "—"),
            f"${entrada.get('precio_costo', 0):,.0f}",
        )
        indice[str(i)] = entrada

    console.print(table)
    console.print()
    return indice


def elegir_un_producto(catalogo: list, indice: dict) -> dict | None:
    skus = {e["sku"].upper(): e for e in catalogo}
    while True:
        r = Prompt.ask(
            f"[bold]Elegí un producto[/bold] [dim](número 1-{len(catalogo)} o SKU, Enter para terminar)[/dim]",
            default="",
        )
        if not r.strip():
            return None
        if r.strip() in indice:
            return indice[r.strip()]
        if r.strip().upper() in skus:
            return skus[r.strip().upper()]
        console.print("[red]No encontrado. Intentá de nuevo.[/red]")


def listar_fotos_producto(sku: str) -> list[Path]:
    """Devuelve fotos de fotos/gemini/ y fotos/con_texto/ ordenadas."""
    fotos = []
    for subcarpeta in ("gemini", "con_texto"):
        carpeta = PRODUCTOS_BASE / sku / "fotos" / subcarpeta
        if carpeta.exists():
            fotos.extend(sorted(carpeta.glob("*.jpg")))
            fotos.extend(sorted(carpeta.glob("*.png")))
    return fotos


def mostrar_tabla_fotos(fotos: list[Path]) -> None:
    table = Table(box=box.SIMPLE, show_header=True, padding=(0, 1))
    table.add_column("N°",      style="dim",        width=4, justify="right")
    table.add_column("Carpeta", style="cyan",        min_width=12)
    table.add_column("Archivo", style="bold",        min_width=30)

    for i, f in enumerate(fotos, 1):
        carpeta = f.parent.name
        table.add_row(str(i), carpeta, f.name)

    console.print(table)


def elegir_fotos(sku: str) -> tuple[str, list[str]]:
    """Retorna (portada_relativa, [apoyos_relativos])."""
    fotos = listar_fotos_producto(sku)
    if not fotos:
        console.print(f"  [dim]No hay fotos en gemini/ ni con_texto/ para {sku}. Se saltea.[/dim]")
        return "", []

    console.print(f"\n  [bold cyan]Fotos disponibles para {sku}:[/bold cyan]")
    mostrar_tabla_fotos(fotos)

    def pedir_indices(mensaje: str) -> list[int]:
        while True:
            r = Prompt.ask(f"  {mensaje}", default="")
            if not r.strip():
                return []
            partes = re.split(r"[,\s]+", r.strip())
            resultado = []
            valido = True
            for p in partes:
                if p.isdigit() and 1 <= int(p) <= len(fotos):
                    resultado.append(int(p))
                else:
                    console.print(f"  [red]'{p}' no es válido (1-{len(fotos)})[/red]")
                    valido = False
                    break
            if valido:
                return resultado

    # Portada
    portada = ""
    idx_portada = pedir_indices("[bold]Portada[/bold] [dim](número, Enter para saltear)[/dim]")
    if idx_portada:
        foto_portada = fotos[idx_portada[0] - 1]
        portada = str(foto_portada.relative_to(KB_ROOT))

    # Apoyo
    apoyos = []
    idx_apoyos = pedir_indices("[bold]Apoyo[/bold] [dim](números separados por coma, Enter para saltear)[/dim]")
    for idx in idx_apoyos:
        apoyos.append(str(fotos[idx - 1].relative_to(KB_ROOT)))

    return portada, apoyos


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    BUNDLES_DIR.mkdir(exist_ok=True)

    console.print(Panel("[bold cyan]Crear Bundle[/bold cyan]", border_style="cyan"))

    catalogo = cargar_catalogo()

    # ── 1. Elegir productos ───────────────────────────────────────────────────
    console.rule("[bold cyan]Paso 1 — Elegir productos")
    console.print()
    indice = mostrar_tabla_catalogo(catalogo)

    seleccionados: list[dict] = []  # [{"producto": {...}, "cantidad": N}]

    while True:
        prod = elegir_un_producto(catalogo, indice)
        if prod is None:
            if not seleccionados:
                console.print("[yellow]No elegiste ningún producto. Saliendo.[/yellow]")
                sys.exit(0)
            break

        while True:
            cant_str = Prompt.ask(
                f"  Cantidad de [bold]{prod['sku']}[/bold]",
                default="1",
            )
            if cant_str.isdigit() and int(cant_str) >= 1:
                cantidad = int(cant_str)
                break
            console.print("  [red]Ingresá un número entero mayor a 0.[/red]")

        seleccionados.append({"producto": prod, "cantidad": cantidad})
        console.print(
            f"  [green]✓ Agregado:[/green] {prod['sku']} × {cantidad}\n"
        )

    # ── 2. Resumen de selección ───────────────────────────────────────────────
    console.rule("[bold cyan]Paso 2 — Resumen")
    console.print()

    costo_total = 0.0
    table = Table(box=box.ROUNDED, padding=(0, 1))
    table.add_column("SKU",      style="bold yellow")
    table.add_column("Nombre",   min_width=28)
    table.add_column("Cant.",    justify="right")
    table.add_column("Costo u.", justify="right", style="green")
    table.add_column("Subtotal", justify="right", style="bold green")

    for item in seleccionados:
        p = item["producto"]
        costo_u = p.get("precio_costo", 0)
        subtotal = costo_u * item["cantidad"]
        costo_total += subtotal
        table.add_row(
            p["sku"],
            p["nombre"],
            str(item["cantidad"]),
            f"${costo_u:,.0f}",
            f"${subtotal:,.0f}",
        )

    console.print(table)
    console.print(f"\n  [bold]Costo total:[/bold] [green]${costo_total:,.0f}[/green]")

    # ── 3. Nombre del bundle ──────────────────────────────────────────────────
    console.rule("[bold cyan]Paso 3 — Nombre del bundle")
    console.print()

    while True:
        nombre = Prompt.ask("[bold]Nombre del bundle[/bold] [dim](ej: Combo Organización Calzado)[/dim]").strip()
        if nombre:
            break
        console.print("[red]El nombre no puede estar vacío.[/red]")

    slug = slugify(nombre)
    console.print(f"  [dim]Slug generado:[/dim] [bold]{slug}[/bold]")

    # Verificar si ya existe
    destino = BUNDLES_DIR / f"{slug}.json"
    if destino.exists():
        if not Confirm.ask(f"  [yellow]Ya existe {destino.name}. ¿Sobreescribir?[/yellow]", default=False):
            console.print("[yellow]Cancelado.[/yellow]")
            sys.exit(0)

    # ── 4. Precio ─────────────────────────────────────────────────────────────
    console.rule("[bold cyan]Paso 4 — Precio de venta")
    console.print()

    precio_sugerido = round(costo_total * MARGEN)
    console.print(
        f"  Costo total: [green]${costo_total:,.0f}[/green]  ×  margen {MARGEN}x  "
        f"→  [bold green]${precio_sugerido:,.0f}[/bold green]"
    )

    while True:
        precio_str = Prompt.ask(
            f"  [bold]Precio de venta final[/bold] [dim](Enter para aceptar ${precio_sugerido:,.0f})[/dim]",
            default=str(int(precio_sugerido)),
        )
        precio_str = precio_str.replace(",", "").replace(".", "").strip()
        if precio_str.isdigit() and int(precio_str) > 0:
            precio_final = int(precio_str)
            break
        console.print("  [red]Ingresá un número entero positivo.[/red]")

    # ── 5. Fotos ──────────────────────────────────────────────────────────────
    console.rule("[bold cyan]Paso 5 — Fotos")
    console.print()

    portada_global = ""
    apoyos_global: list[str] = []

    skus_vistos: set[str] = set()
    for item in seleccionados:
        sku = item["producto"]["sku"]
        if sku in skus_vistos:
            continue
        skus_vistos.add(sku)

        portada, apoyos = elegir_fotos(sku)

        if portada and not portada_global:
            portada_global = portada
        if apoyos:
            apoyos_global.extend(apoyos)

    # ── 6. Guardar ────────────────────────────────────────────────────────────
    bundle = {
        "nombre": nombre,
        "slug": slug,
        "productos": [
            {"sku": item["producto"]["sku"], "cantidad": item["cantidad"]}
            for item in seleccionados
        ],
        "precio_costo_total": costo_total,
        "precio_venta_sugerido": precio_sugerido,
        "precio_venta_final": precio_final,
        "fotos": {
            "portada": portada_global,
            "apoyo": apoyos_global,
        },
        "creado_en": datetime.now().isoformat(),
    }

    with open(destino, "w") as f:
        json.dump(bundle, f, ensure_ascii=False, indent=2)

    # ── 7. Confirmación ───────────────────────────────────────────────────────
    console.print()
    console.print(
        Panel(
            f"[bold green]Bundle creado:[/bold green] {destino.relative_to(KB_ROOT)}\n\n"
            f"  Nombre:   {nombre}\n"
            f"  Productos: {len(bundle['productos'])} línea(s)\n"
            f"  Costo:    [green]${costo_total:,.0f}[/green]\n"
            f"  Venta:    [bold green]${precio_final:,.0f}[/bold green]"
            + (f"\n  Portada:  {portada_global}" if portada_global else ""),
            title="[bold cyan]✓ Listo[/bold cyan]",
            border_style="green",
        )
    )


if __name__ == "__main__":
    main()
