#!/usr/bin/env python3
import json
import sys
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table
from rich import box

MESES = [
    "", "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]

KB_ROOT = Path(__file__).resolve().parent.parent
PRODUCTOS_BASE = KB_ROOT / "productos-base"
CATALOGO = KB_ROOT / "catalogo.json"

console = Console()


def cargar_catalogo() -> list[dict]:
    skus = json.loads(CATALOGO.read_text())
    productos = []
    for sku in skus:
        path = PRODUCTOS_BASE / sku / "producto.json"
        if path.exists():
            productos.append(json.loads(path.read_text()))
    return productos


def mostrar_lista(productos: list[dict]) -> str:
    table = Table(box=box.SIMPLE, show_header=True, padding=(0, 2))
    table.add_column("N°", style="bold cyan", width=4, justify="right")
    table.add_column("SKU", style="bold yellow", no_wrap=True)
    table.add_column("Nombre")
    table.add_column("Tipo", style="dim")

    for i, p in enumerate(productos, 1):
        table.add_row(str(i), p["sku"], p.get("nombre", "—"), p.get("tipo", "—"))

    console.print()
    console.print(table)

    skus = [p["sku"] for p in productos]
    while True:
        resp = Prompt.ask("[bold]Elegí número o SKU[/bold]").strip()
        if resp.isdigit() and 1 <= int(resp) <= len(productos):
            return productos[int(resp) - 1]["sku"]
        if resp.upper() in [s.upper() for s in skus]:
            return next(s for s in skus if s.upper() == resp.upper())
        console.print("[red]Opción inválida.[/red]")


def _cargar_modelos() -> dict[str, str]:
    modelos_path = KB_ROOT / "modelos.json"
    if modelos_path.exists():
        return {m["codigo"]: m["nombre"] for m in json.loads(modelos_path.read_text())}
    return {}


def _resolver_nombre(valor: str, modelos: dict[str, str]) -> str:
    if not valor:
        return "—"
    upper = valor.upper()
    if upper in modelos:
        return modelos[upper]
    return valor


def _formato_fecha(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso)
        return f"{dt.day} de {MESES[dt.month]} de {dt.year}, {dt.strftime('%H:%M')}"
    except (ValueError, TypeError):
        return iso or "—"


def _formato_precio_ar(valor: float) -> str:
    """Formato argentino: $1.234,56"""
    entero = int(valor)
    decimales = f"{valor:.2f}".split(".")[1]
    if entero == 0:
        return f"$0,{decimales}"
    grupos = []
    n = abs(entero)
    while n:
        grupos.append(f"{n % 1000}")
        n //= 1000
    grupos.reverse()
    parte_entera = grupos[0]
    for g in grupos[1:]:
        parte_entera += "." + g.zfill(3)
    signo = "-" if entero < 0 else ""
    return f"${signo}{parte_entera},{decimales}"


def mostrar_detalle(sku: str):
    path = PRODUCTOS_BASE / sku / "producto.json"
    if not path.exists():
        console.print(f"[red]No se encontró {path}[/red]")
        sys.exit(1)

    p = json.loads(path.read_text())
    v = p.get("variante", {})
    modelos = _cargar_modelos()
    sin_datos = "[bold red]— sin datos —[/bold red]"

    # — Resolver modelo —
    modelo = _resolver_nombre(v.get("modelo", ""), modelos)
    falta_modelo = modelo == "—"

    # — Dimensiones —
    dims = p.get("dimensiones") or {}
    largo = dims.get("largo_cm")
    ancho = dims.get("ancho_cm")
    alto = dims.get("alto_cm")
    faltan_dims = largo is None or ancho is None or alto is None

    # — Construir contenido del panel —
    lines = []

    # Sección 1 — Identidad
    lines.append(f"[bold yellow]🏷️  SKU:[/]          {p['sku']}")
    lines.append(f"[bold white]📦 Nombre:[/]       {p.get('nombre', '—')}")

    lines.append("")

    # Sección 2 — Clasificación
    tipo = _resolver_nombre(p.get("tipo", ""), modelos)
    lines.append(f"[bold white]📂 Tipo:[/]         {tipo}")
    if falta_modelo:
        lines.append("[bold white]🔧 Modelo:[/]       [dim italic]— sin asignar —[/dim italic]")
    else:
        lines.append(f"[bold white]🔧 Modelo:[/]       {modelo}")
    lines.append(f"[bold white]🎨 Color:[/]        {v.get('color') or '—'}")
    lines.append(f"[bold white]📏 Talle:[/]        {v.get('talle') or '—'}")

    lines.append("")

    # Sección 3 — Dimensiones
    lines.append(f"[bold white]↔️  Largo:[/]        {f'{largo} cm' if largo is not None else sin_datos}")
    lines.append(f"[bold white]↕️  Ancho:[/]        {f'{ancho} cm' if ancho is not None else sin_datos}")
    lines.append(f"[bold white]📐 Alto:[/]         {f'{alto} cm' if alto is not None else sin_datos}")
    if not faltan_dims:
        volumen = largo * ancho * alto
        vol_fmt = f"{volumen:,.0f}".replace(",", ".")
        lines.append(f"[bold white]📦 Volumen:[/]      {vol_fmt} cm³")

    lines.append("")

    # Sección 4 — Comercial
    proveedor = p.get("proveedor", "—")
    prov_display = proveedor.capitalize() if proveedor != "—" else "—"
    lines.append(f"[bold white]🏭 Proveedor:[/]    {prov_display}")

    precio = p.get("precio_costo", 0)
    lines.append(f"[bold white]💰 Costo:[/]        [bold green]{_formato_precio_ar(precio)}[/bold green]")

    if proveedor == "andres":
        fob = p.get("precio_fob_usd")
        factor = p.get("factor_nacionalizacion")
        tc = p.get("tipo_cambio_usado")
        if fob is not None and factor is not None and tc is not None:
            nac = fob * factor
            fob_s = f"{fob:.2f}".replace(".", ",")
            nac_s = f"{nac:.2f}".replace(".", ",")
            tc_ar = _formato_precio_ar(tc)
            resultado = _formato_precio_ar(nac * tc)
            lines.append(f"   [dim]💵 FOB:       USD {fob_s}[/dim]")
            lines.append(f"   [dim]📈 Nacional:  USD {fob_s} × {factor} = USD {nac_s}[/dim]")
            lines.append(f"   [dim]💱 TC blue:   {tc_ar}[/dim]")
            lines.append(f"   [dim]🧮 Cálculo:   USD {nac_s} × {tc_ar} = {resultado}[/dim]")

    stock = p.get("stock", 0)
    if stock > 0:
        lines.append(f"[bold white]📊 Stock:[/]        [bold green]🟢 {stock} unidades[/bold green]")
    else:
        lines.append(f"[bold white]📊 Stock:[/]        [bold red]🔴 Sin stock[/bold red]")

    lines.append("")

    # Sección 5 — Extras
    notas = p.get("notas")
    if notas:
        lines.append(f"[bold white]📝 Notas:[/]        {notas}")
    else:
        lines.append("[bold white]📝 Notas:[/]        [dim]— sin notas —[/dim]")
    lines.append(f"[bold white]📅 Creado:[/]       {_formato_fecha(p.get('fecha_creacion', ''))}")

    contenido = "\n".join(lines)

    console.print()
    console.print("[bold cyan]✨ Detalle del producto ✨[/bold cyan]", justify="center")
    console.print()
    console.print(contenido)

    # — Mini resumen —
    avisos = []
    if faltan_dims:
        avisos.append("⚠️  Faltan medidas — corré nuevo_producto.py para completarlas")
    if falta_modelo:
        avisos.append("⚠️  Sin modelo asignado")

    if avisos:
        for aviso in avisos:
            console.print(f"[yellow]{aviso}[/yellow]")
    else:
        console.print("✅ Producto completo y listo para publicar", style="bold green")
    console.print()


def main():
    productos = cargar_catalogo()
    if not productos:
        console.print("[red]catalogo.json está vacío.[/red]")
        sys.exit(1)

    try:
        sku = mostrar_lista(productos)
        mostrar_detalle(sku)
    except (KeyboardInterrupt, EOFError):
        console.print("\n[yellow]Cancelado.[/yellow]")
        sys.exit(0)


if __name__ == "__main__":
    main()
