#!/usr/bin/env python3
"""Genera prompts Gemini para fotos lifestyle usando Claude API."""

import json
import os
import sys
import base64
from datetime import datetime
from pathlib import Path

import anthropic
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt
from rich import print as rprint

console = Console()

BASE_DIR = Path(__file__).parent.parent
CATALOGO_PATH = BASE_DIR / "catalogo.json"

SYSTEM_PROMPT = """Sos un experto en fotografía de producto para e-commerce en Argentina.
Generás prompts en inglés para Gemini Image Generation (AI Studio)
optimizados para productos de organización del hogar vendidos en MercadoLibre.
Cada prompt debe ser detallado, creativo y realista."""

USER_PROMPT = """Analizá esta foto de producto y generá 5 prompts variados para generar fotos lifestyle en AI Studio.
Cada prompt debe especificar: ambiente, iluminación, estilo fotográfico y detalles de escena.
Variá los ambientes: placard, habitación, entrada de casa, living, fondo de estudio.
Respondé SOLO con JSON válido, sin texto extra, sin markdown, sin backticks:
{"prompts": [{"id": 1, "ambiente": "...", "prompt": "..."}, ...]}"""


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
        eleccion = Prompt.ask("\nElegí un producto [bold](número o SKU)[/bold]")
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


def listar_fotos(sku):
    fotos_dir = BASE_DIR / "productos-base" / sku / "fotos" / "listas_gemini"
    if not fotos_dir.exists():
        console.print(f"[red]No existe el directorio {fotos_dir}[/red]")
        sys.exit(1)
    fotos = sorted(fotos_dir.glob("*.jpg")) + sorted(fotos_dir.glob("*.png"))
    if not fotos:
        console.print(f"[red]No hay fotos en {fotos_dir}[/red]")
        sys.exit(1)
    return fotos


def mostrar_fotos(fotos):
    table = Table(title="Fotos disponibles", show_header=True, header_style="bold cyan")
    table.add_column("#", style="dim", width=4)
    table.add_column("Archivo")

    for i, f in enumerate(fotos, 1):
        table.add_row(str(i), f.name)

    console.print(table)


def elegir_foto(fotos):
    mostrar_fotos(fotos)
    while True:
        eleccion = Prompt.ask("\nElegí una foto [bold](número)[/bold]")
        if eleccion.isdigit():
            idx = int(eleccion) - 1
            if 0 <= idx < len(fotos):
                return fotos[idx]
        console.print(f"[red]Número inválido. Ingresá entre 1 y {len(fotos)}.[/red]")


def llamar_claude(foto_path, api_key):
    client = anthropic.Anthropic(api_key=api_key)

    with open(foto_path, "rb") as f:
        imagen_bytes = f.read()
    imagen_b64 = base64.standard_b64encode(imagen_bytes).decode("utf-8")

    # Detectar media type
    ext = foto_path.suffix.lower()
    media_type = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png"

    console.print("[dim]Enviando foto a Claude...[/dim]")

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": imagen_b64,
                        },
                    },
                    {"type": "text", "text": USER_PROMPT},
                ],
            }
        ],
    )

    return response.content[0].text


def mostrar_prompts(prompts_data):
    console.print()
    for p in prompts_data["prompts"]:
        panel = Panel(
            p["prompt"],
            title=f"[bold cyan]#{p['id']} — {p['ambiente']}[/bold cyan]",
            border_style="cyan",
        )
        console.print(panel)


def guardar_prompts(sku, prompts_data, foto_nombre):
    json_path = BASE_DIR / "productos-base" / sku / f"{sku}.json"

    if json_path.exists():
        with open(json_path) as f:
            datos = json.load(f)
    else:
        datos = {}

    entrada = {
        "timestamp": datetime.now().isoformat(),
        "foto_origen": foto_nombre,
        "prompts": prompts_data["prompts"],
    }

    if "prompts_gemini" not in datos:
        datos["prompts_gemini"] = []

    datos["prompts_gemini"].append(entrada)

    with open(json_path, "w") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)

    console.print(f"\n[green]✓ Prompts guardados en {json_path.relative_to(BASE_DIR)}[/green]")


def main():
    # Verificar API key
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        console.print(
            Panel(
                "[red bold]ANTHROPIC_API_KEY no está definida.[/red bold]\n"
                "Exportá la variable antes de ejecutar:\n"
                "[yellow]export ANTHROPIC_API_KEY=sk-ant-...[/yellow]",
                title="Error de configuración",
                border_style="red",
            )
        )
        sys.exit(1)

    console.print(Panel("[bold cyan]Generador de prompts Gemini para fotos lifestyle[/bold cyan]", border_style="cyan"))

    # 1. Elegir producto
    productos = cargar_catalogo()
    producto = elegir_producto(productos)
    sku = producto["sku"]
    console.print(f"\n[green]Producto seleccionado:[/green] [bold]{sku}[/bold] — {producto['nombre']}\n")

    # 2. Elegir foto
    fotos = listar_fotos(sku)
    foto = elegir_foto(fotos)
    console.print(f"\n[green]Foto seleccionada:[/green] [bold]{foto.name}[/bold]\n")

    # 3. Llamar a Claude
    respuesta_raw = llamar_claude(foto, api_key)

    # 4. Parsear JSON
    try:
        prompts_data = json.loads(respuesta_raw)
    except json.JSONDecodeError as e:
        console.print(f"[red]Error al parsear JSON de Claude:[/red] {e}")
        console.print(f"[dim]Respuesta cruda:[/dim]\n{respuesta_raw}")
        sys.exit(1)

    # 5. Mostrar prompts
    mostrar_prompts(prompts_data)

    # 6. Guardar
    guardar_prompts(sku, prompts_data, foto.name)


if __name__ == "__main__":
    main()
