#!/usr/bin/env python3
"""
crear_listing.py — Prepará un draft de listing a partir de un bundle existente.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

KB_ROOT = Path(__file__).resolve().parent.parent
BUNDLES_DIR = KB_ROOT / "bundles"
DRAFTS_DIR = KB_ROOT / "listings" / "drafts"
PRODUCTOS_BASE = KB_ROOT / "productos-base"

console = Console()


# ── helpers ───────────────────────────────────────────────────────────────────

def cargar_json(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def listar_bundles() -> list[Path]:
    if not BUNDLES_DIR.exists():
        return []
    return sorted(BUNDLES_DIR.glob("*.json"))


def mostrar_bundles(bundles: list[Path]) -> dict:
    table = Table(box=box.ROUNDED, show_lines=False, padding=(0, 1))
    table.add_column("N°",      style="bold cyan",  width=4, justify="right")
    table.add_column("Slug",    style="bold yellow", min_width=30)
    table.add_column("Nombre",  min_width=28)
    table.add_column("Precio",  justify="right", style="green")
    table.add_column("Productos", justify="right")

    indice = {}
    for i, path in enumerate(bundles, 1):
        try:
            data = cargar_json(path)
            nombre  = data.get("nombre", "—")
            precio  = data.get("precio_venta_final", 0)
            n_prod  = len(data.get("productos", []))
        except Exception:
            nombre, precio, n_prod = "— error —", 0, 0

        table.add_row(str(i), path.stem, nombre, f"${precio:,.0f}", str(n_prod))
        indice[str(i)] = path

    console.print(table)
    console.print()
    return indice


def elegir_bundle() -> tuple[Path, dict]:
    bundles = listar_bundles()
    if not bundles:
        console.print(
            Panel(
                "[red]No hay bundles en bundles/.[/red]\n"
                "Primero creá uno con [bold]crear_bundle.py[/bold].",
                border_style="red",
            )
        )
        sys.exit(1)

    console.rule("[bold cyan]Paso 1 — Elegir bundle")
    console.print()
    indice = mostrar_bundles(bundles)

    while True:
        r = Prompt.ask(f"[bold]Elegí un bundle[/bold] [dim](número 1-{len(bundles)})[/dim]").strip()
        if r in indice:
            path = indice[r]
            return path, cargar_json(path)
        console.print("[red]Número inválido.[/red]")


def mostrar_resumen_bundle(bundle: dict, path: Path) -> None:
    console.rule("[bold cyan]Paso 2 — Resumen del bundle")
    console.print()

    table = Table(box=box.SIMPLE, padding=(0, 1), show_header=True)
    table.add_column("SKU",      style="bold yellow")
    table.add_column("Cantidad", justify="right")

    for item in bundle.get("productos", []):
        table.add_row(item["sku"], str(item.get("cantidad", 1)))

    console.print(table)
    console.print(f"  Costo total:    [green]${bundle.get('precio_costo_total', 0):,.0f}[/green]")
    console.print(f"  Precio final:   [bold green]${bundle.get('precio_venta_final', 0):,.0f}[/bold green]")
    portada = bundle.get("fotos", {}).get("portada", "")
    console.print(f"  Portada:        [dim]{portada or '—'}[/dim]")
    console.print()


def verificar_bundle(bundle: dict, primer_producto: dict) -> list[str]:
    errores = []
    if not primer_producto.get("titulo_ml"):
        errores.append("Falta [bold]titulo_ml[/bold] en el JSON del producto.")
    if not primer_producto.get("descripcion"):
        errores.append("Falta [bold]descripcion[/bold] en el JSON del producto.")
    if not bundle.get("fotos", {}).get("portada"):
        errores.append("El bundle no tiene [bold]foto de portada[/bold]. Editá el bundle con crear_bundle.py.")
    return errores


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    DRAFTS_DIR.mkdir(parents=True, exist_ok=True)

    console.print(Panel("[bold cyan]Crear Listing Draft[/bold cyan]", border_style="cyan"))

    # ── 1. Elegir bundle ──────────────────────────────────────────────────────
    bundle_path, bundle = elegir_bundle()

    # ── 2. Resumen ────────────────────────────────────────────────────────────
    mostrar_resumen_bundle(bundle, bundle_path)

    # ── 3. Cargar primer producto ─────────────────────────────────────────────
    primer_sku = bundle["productos"][0]["sku"]
    producto_path = PRODUCTOS_BASE / primer_sku / "producto.json"

    if not producto_path.exists():
        console.print(f"[red]No se encontró producto.json para {primer_sku}[/red]")
        sys.exit(1)

    primer_producto = cargar_json(producto_path)

    # ── 4. Verificar datos necesarios ─────────────────────────────────────────
    errores = verificar_bundle(bundle, primer_producto)
    if errores:
        console.print()
        msgs = "\n".join(f"  • {e}" for e in errores)
        console.print(
            Panel(
                f"[red bold]No se puede crear el listing. Faltan datos:[/red bold]\n\n{msgs}",
                title="Validación fallida",
                border_style="red",
            )
        )
        sys.exit(1)

    titulo     = primer_producto["titulo_ml"]
    descripcion = primer_producto["descripcion"]

    # ── 5. Precio ─────────────────────────────────────────────────────────────
    console.rule("[bold cyan]Paso 3 — Precio")
    console.print()

    precio_bundle = bundle.get("precio_venta_final", 0)
    console.print(f"  Precio del bundle: [bold green]${precio_bundle:,.0f}[/bold green]")

    while True:
        r = Prompt.ask(
            "  [bold]Precio a publicar[/bold] [dim](Enter para aceptar)[/dim]",
            default=str(int(precio_bundle)),
        )
        r = r.replace(",", "").replace(".", "").strip()
        if r.isdigit() and int(r) > 0:
            precio = int(r)
            break
        console.print("  [red]Ingresá un número entero positivo.[/red]")

    # ── 6. Stock ──────────────────────────────────────────────────────────────
    console.rule("[bold cyan]Paso 4 — Stock")
    console.print()

    while True:
        r = Prompt.ask("  [bold]Stock a publicar[/bold]").strip()
        if r.isdigit() and int(r) > 0:
            stock = int(r)
            break
        console.print("  [red]Ingresá un número entero positivo.[/red]")

    # ── 7. Fotos ──────────────────────────────────────────────────────────────
    fotos_bundle = bundle.get("fotos", {})
    portada_rel  = fotos_bundle.get("portada", "")
    apoyo_rel    = fotos_bundle.get("apoyo", [])

    # Convertir a rutas absolutas
    portada_abs = str((KB_ROOT / portada_rel).resolve()) if portada_rel else ""
    apoyo_abs   = [str((KB_ROOT / r).resolve()) for r in apoyo_rel if r]

    # ── 8. Slug y path destino ────────────────────────────────────────────────
    slug    = bundle.get("slug", bundle_path.stem)
    destino = DRAFTS_DIR / f"{slug}.json"

    if destino.exists():
        if not Confirm.ask(
            f"  [yellow]Ya existe listings/drafts/{slug}.json. ¿Sobreescribir?[/yellow]",
            default=False,
        ):
            console.print("[yellow]Cancelado.[/yellow]")
            sys.exit(0)

    # ── 9. Guardar draft ──────────────────────────────────────────────────────
    draft = {
        "slug":        slug,
        "bundle":      str(bundle_path.relative_to(KB_ROOT)),
        "titulo":      titulo,
        "descripcion": descripcion,
        "precio":      precio,
        "stock":       stock,
        "fotos": {
            "portada": portada_abs,
            "apoyo":   apoyo_abs,
        },
        "estado":     "draft",
        "creado_en":  datetime.now().isoformat(),
    }

    with open(destino, "w") as f:
        json.dump(draft, f, ensure_ascii=False, indent=2)

    # ── 10. Confirmación ──────────────────────────────────────────────────────
    rel = destino.relative_to(KB_ROOT)
    agente_cmd = (
        f"python3 ~/Proyectos/palishopping-agent/publicar_desde_kb.py "
        f"listings/drafts/{slug}.json"
    )

    console.print()
    console.print(
        Panel(
            f"[bold green]Draft creado:[/bold green] {rel}\n\n"
            f"  Título:  {titulo}\n"
            f"  Precio:  [bold green]${precio:,.0f}[/bold green]\n"
            f"  Stock:   {stock}\n"
            f"  Portada: [dim]{portada_abs or '—'}[/dim]\n\n"
            f"[bold]Para publicar en MercadoLibre:[/bold]\n"
            f"[bold cyan]{agente_cmd}[/bold cyan]",
            title="[bold cyan]✓ Listo[/bold cyan]",
            border_style="green",
        )
    )


if __name__ == "__main__":
    main()
