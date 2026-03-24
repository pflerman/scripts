#!/usr/bin/env python3
import json
from pathlib import Path
from rich.console import Console
from rich.table import Table

ROOT = Path(__file__).parent.parent
catalogo_path = ROOT / "catalogo.json"
productos_base = ROOT / "productos-base"
modelos_path = ROOT / "modelos.json"

skus = json.loads(catalogo_path.read_text())
modelos = {m["codigo"]: m["nombre"] for m in json.loads(modelos_path.read_text())}

productos = []
for sku in skus:
    path = productos_base / sku / "producto.json"
    if path.exists():
        productos.append(json.loads(path.read_text()))

console = Console()
table = Table(title="Catálogo de productos", show_lines=True)

table.add_column("SKU", style="cyan", no_wrap=True)
table.add_column("Nombre")
table.add_column("Tipo")
table.add_column("Modelo")
table.add_column("Color")
table.add_column("Talle")
table.add_column("Proveedor", style="magenta")
table.add_column("Precio Costo", justify="right", style="green")

for p in productos:
    v = p.get("variante", {})
    modelo_raw = v.get("modelo", "")
    modelo = modelos.get(modelo_raw.upper(), modelo_raw) if modelo_raw else "-"
    table.add_row(
        p.get("sku", "-"),
        p.get("nombre", "-"),
        p.get("tipo", "-"),
        modelo,
        v.get("color", "-"),
        v.get("talle", "-") or "-",
        p.get("proveedor", "-"),
        f"${p['precio_costo']:,.2f}" if "precio_costo" in p else "-",
    )

console.print(table)
