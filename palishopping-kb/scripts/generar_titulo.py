#!/usr/bin/env python3
"""
generar_titulo.py — Genera títulos ML para un producto base usando Claude AI.

Uso: python3 generar_titulo.py
Requiere: ANTHROPIC_API_KEY en el entorno.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

import anthropic
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich import box

KB_ROOT = Path(__file__).resolve().parent.parent
PRODUCTOS_BASE = KB_ROOT / "productos-base"
CATALOGO = KB_ROOT / "catalogo.json"

MODEL = "claude-sonnet-4-20250514"

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


def cargar_titulos_generados(sku: str) -> dict:
    path = PRODUCTOS_BASE / sku / "inteligencia" / "titulos_generados.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {"historial": []}


def guardar_titulos_generados(sku: str, data: dict):
    path = PRODUCTOS_BASE / sku / "inteligencia" / "titulos_generados.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── Interfaz ──────────────────────────────────────────────────────────────────

def mostrar_bienvenida():
    console.print()
    console.print(Panel(
        "[bold cyan]Generador de Títulos ML — Palishopping KB[/bold cyan]\n"
        "[dim]Genera títulos optimizados para MercadoLibre Argentina usando Claude AI.[/dim]",
        box=box.ROUNDED,
        padding=(0, 2),
    ))
    console.print()


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
        console.print("[yellow]El catálogo está vacío. Primero creá un producto con nuevo_producto.py[/yellow]")
        return None

    console.rule("[bold cyan]Productos disponibles")
    console.print()
    indice = mostrar_tabla_catalogo(catalogo)

    skus = {e["sku"].upper(): e for e in catalogo}

    while True:
        respuesta = Prompt.ask(
            f"[bold]Elegí un producto[/bold] [dim](número 1-{len(catalogo)} o SKU, Enter para cancelar)[/dim]",
            default="",
        )
        if not respuesta.strip():
            return None
        if respuesta.strip() in indice:
            return indice[respuesta.strip()]
        clave = respuesta.strip().upper()
        if clave in skus:
            return skus[clave]
        console.print("[red]No encontrado. Ingresá un número de la lista o el SKU exacto.[/red]")


def pedir_palabras_clave(producto_json: dict) -> list[str]:
    existentes = producto_json.get("palabras_clave", [])

    console.print()
    if existentes:
        console.print(f"  [dim]Palabras clave existentes:[/dim] [yellow]{', '.join(existentes)}[/yellow]")

    raw = Prompt.ask(
        "[bold]Palabras clave[/bold] [dim](separadas por coma, Enter para usar solo las existentes)[/dim]",
        default="",
    )

    nuevas = [p.strip() for p in raw.split(",") if p.strip()]
    combinadas = list(dict.fromkeys(existentes + nuevas))  # sin duplicados, orden preservado
    return combinadas, nuevas


def generar_titulos_con_claude(cliente: anthropic.Anthropic, producto_json: dict, palabras_clave: list[str]) -> list[str]:
    nombre = producto_json.get("nombre", "")
    tipo = producto_json.get("tipo", "")
    color = producto_json.get("variante", {}).get("color", "")
    talle = producto_json.get("variante", {}).get("talle", "")

    prompt = f"""Generá exactamente 10 títulos para una publicación en MercadoLibre Argentina.

Producto:
- Nombre: {nombre}
- Tipo: {tipo}
- Color: {color}
- Talle/Tamaño: {talle if talle else "no aplica"}
- Palabras clave: {", ".join(palabras_clave) if palabras_clave else "ninguna especificada"}

Reglas estrictas:
- Cada título debe tener MÁXIMO 60 caracteres (contarlos con cuidado)
- Usar la mayor cantidad de caracteres posible dentro del límite
- Optimizados para búsqueda en MercadoLibre Argentina
- Sin signos de puntuación, sin caracteres especiales, sin emojis, sin comas
- No usar mayúsculas innecesarias (solo primera letra de sustantivos propios)
- Mezclar palabras clave con variaciones creativas y términos de búsqueda populares
- Variar el orden y estructura entre títulos para cubrir distintas búsquedas

Respondé ÚNICAMENTE con los 10 títulos, uno por línea, sin numeración ni prefijos."""

    console.print()
    with console.status("[bold cyan]Consultando Claude AI...[/bold cyan]", spinner="dots"):
        response = cliente.messages.create(
            model=MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )

    raw = response.content[0].text.strip()
    titulos = [linea.strip() for linea in raw.splitlines() if linea.strip()]
    # Sanear: quitar numeración si Claude la agrega igual
    titulos_limpios = []
    for t in titulos:
        if t and t[0].isdigit() and len(t) > 2 and t[1] in ".)-":
            t = t[2:].strip()
        titulos_limpios.append(t)

    return titulos_limpios[:10]


def mostrar_tabla_titulos(titulos: list[str], tanda: int = 1):
    console.print()
    console.rule(f"[bold cyan]Títulos generados — Tanda {tanda}")
    console.print()

    table = Table(box=box.ROUNDED, padding=(0, 1))
    table.add_column("N°",    style="bold cyan",  width=4,  justify="right")
    table.add_column("Título",                    min_width=40)
    table.add_column("Chars", style="bold white", width=7,  justify="right")

    for i, titulo in enumerate(titulos, 1):
        chars = len(titulo)
        color = "green" if chars <= 60 else "red"
        table.add_row(str(i), titulo, f"[{color}]{chars}[/{color}]")

    console.print(table)
    console.print()


def elegir_titulo(titulos_sesion: list[str]) -> str | None | str:
    """
    Retorna:
    - Un string con el título elegido
    - None para cancelar
    - "NUEVO" para generar otra tanda
    """
    while True:
        respuesta = Prompt.ask(
            "[bold]¿Qué hacemos?[/bold] [dim](número, 'propio', 'nuevo' para generar más, Enter para cancelar)[/dim]",
            default="",
        )

        raw = respuesta.strip()

        if not raw:
            return None

        if raw.lower() == "nuevo":
            return "NUEVO"

        if raw.lower() == "propio":
            titulo = Prompt.ask("[bold]Escribí el título[/bold]")
            titulo = titulo.strip()
            if not titulo:
                console.print("[red]Título vacío, intenta de nuevo.[/red]")
                continue
            chars = len(titulo)
            color = "green" if chars <= 60 else "red"
            console.print(f"  Caracteres: [{color}]{chars}[/{color}]")
            if chars > 60:
                console.print("[yellow]El título supera los 60 caracteres.[/yellow]")
                if not Confirm.ask("¿Guardarlo igual?", default=False):
                    continue
            return titulo

        try:
            idx = int(raw) - 1
            if 0 <= idx < len(titulos_sesion):
                return titulos_sesion[idx]
            console.print(f"[red]Ingresá un número entre 1 y {len(titulos_sesion)}.[/red]")
        except ValueError:
            console.print("[red]Opción no reconocida. Ingresá un número, 'propio', 'nuevo' o Enter.[/red]")


def guardar_historial(sku: str, palabras_clave_sesion: list[str], titulos: list[str], elegido: str | None):
    data = cargar_titulos_generados(sku)

    entrada = {
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "palabras_clave_sesion": palabras_clave_sesion,
        "titulos": [
            {
                "titulo": t,
                "caracteres": len(t),
                "elegido": (t == elegido),
            }
            for t in titulos
        ],
    }
    data["historial"].append(entrada)
    guardar_titulos_generados(sku, data)


def mostrar_resultado(sku: str, titulo: str):
    console.print()
    console.print(Panel(
        f"[bold green]Título guardado.[/bold green]\n"
        f"[bold yellow]{sku}[/bold yellow]: [bold]{titulo}[/bold]\n"
        f"[dim]{len(titulo)} caracteres[/dim]",
        box=box.ROUNDED,
        padding=(0, 2),
    ))
    console.print()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    mostrar_bienvenida()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        console.print("[red]Error:[/red] Variable de entorno ANTHROPIC_API_KEY no encontrada.")
        console.print("[dim]Exportala con: export ANTHROPIC_API_KEY=sk-...[/dim]")
        sys.exit(1)

    cliente = anthropic.Anthropic(api_key=api_key)

    try:
        catalogo = cargar_catalogo()
        entrada = elegir_producto(catalogo)
        if entrada is None:
            console.print("[yellow]Cancelado.[/yellow]\n")
            sys.exit(0)

        sku = entrada["sku"]
        producto_json = cargar_producto_json(sku)
        if producto_json is None:
            # El producto existe en catálogo pero no tiene carpeta: crear estructura mínima
            console.print(f"[yellow]producto.json no encontrado para {sku}. Usando datos del catálogo.[/yellow]")
            producto_json = {
                "sku": sku,
                "nombre": entrada.get("nombre", ""),
                "tipo": entrada.get("tipo", ""),
                "variante": {"color": "", "talle": ""},
                "palabras_clave": [],
                "titulo_ml": "",
                "ultima_actualizacion": "",
            }

        console.rule("[bold cyan]Palabras clave")
        palabras_clave, nuevas = pedir_palabras_clave(producto_json)

        # Actualizar palabras_clave en producto.json si hubo nuevas
        if nuevas:
            producto_json["palabras_clave"] = palabras_clave

        # Bucle de generación
        todos_los_titulos: list[str] = []  # acumula todas las tandas
        palabras_clave_sesion = list(palabras_clave)
        tanda = 1
        titulo_elegido: str | None = None

        while True:
            titulos_tanda = generar_titulos_con_claude(cliente, producto_json, palabras_clave)
            todos_los_titulos.extend(titulos_tanda)
            mostrar_tabla_titulos(titulos_tanda, tanda)

            decision = elegir_titulo(titulos_tanda)

            if decision is None:
                # Guardar historial de esta tanda sin elección
                guardar_historial(sku, palabras_clave_sesion, titulos_tanda, None)
                console.print("\n[yellow]Cancelado. No se guardó ningún título.[/yellow]\n")
                # Igual actualizar palabras_clave si hubo nuevas
                if nuevas:
                    now = datetime.now().isoformat(timespec="seconds")
                    producto_json["ultima_actualizacion"] = now
                    guardar_producto_json(sku, producto_json)
                    console.print("[dim]Palabras clave actualizadas.[/dim]\n")
                sys.exit(0)

            if decision == "NUEVO":
                guardar_historial(sku, palabras_clave_sesion, titulos_tanda, None)
                tanda += 1
                continue

            # Título elegido
            titulo_elegido = decision
            guardar_historial(sku, palabras_clave_sesion, titulos_tanda, titulo_elegido)
            break

        # Guardar en producto.json
        now = datetime.now().isoformat(timespec="seconds")
        producto_json["titulo_ml"] = titulo_elegido
        producto_json["ultima_actualizacion"] = now
        guardar_producto_json(sku, producto_json)

        mostrar_resultado(sku, titulo_elegido)

        # Info de historial
        historial = cargar_titulos_generados(sku)
        total = sum(len(h["titulos"]) for h in historial["historial"])
        console.print(f"[dim]Historial: {len(historial['historial'])} tanda(s), {total} títulos acumulados → inteligencia/titulos_generados.json[/dim]\n")

    except (KeyboardInterrupt, EOFError):
        console.print("\n[yellow]Cancelado.[/yellow]\n")
        sys.exit(0)
    except anthropic.AuthenticationError:
        console.print("\n[red]Error de autenticación:[/red] API key inválida.")
        sys.exit(1)
    except anthropic.APIConnectionError:
        console.print("\n[red]Error de conexión:[/red] No se pudo contactar la API de Anthropic.")
        sys.exit(1)
    except anthropic.APIStatusError as e:
        console.print(f"\n[red]Error de API ({e.status_code}):[/red] {e.message}")
        sys.exit(1)


if __name__ == "__main__":
    main()
