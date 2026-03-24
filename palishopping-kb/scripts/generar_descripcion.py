#!/usr/bin/env python3
"""
generar_descripcion.py — Genera descripciones ML para un producto base usando Claude AI.

Uso: python3 generar_descripcion.py
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
from rich.text import Text

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


def cargar_descripciones(sku: str) -> dict:
    path = PRODUCTOS_BASE / sku / "inteligencia" / "descripciones_generadas.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {"historial": []}


def guardar_descripciones(sku: str, data: dict):
    path = PRODUCTOS_BASE / sku / "inteligencia" / "descripciones_generadas.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── Interfaz ──────────────────────────────────────────────────────────────────

def mostrar_bienvenida():
    console.print()
    console.print(Panel(
        "[bold cyan]Generador de Descripciones ML — Palishopping KB[/bold cyan]\n"
        "[dim]Genera descripciones para MercadoLibre Argentina usando Claude AI.[/dim]",
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


def mostrar_datos_producto(producto_json: dict):
    console.print()
    console.rule("[bold cyan]Datos del producto")
    console.print()

    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table.add_column("Campo", style="bold cyan", min_width=18)
    table.add_column("Valor")

    campos = [
        ("Nombre",        producto_json.get("nombre", "—")),
        ("Tipo",          producto_json.get("tipo", "—")),
        ("Color",         producto_json.get("variante", {}).get("color", "—")),
        ("Talle",         producto_json.get("variante", {}).get("talle") or "—"),
        ("Título ML",     producto_json.get("titulo_ml") or "[dim]sin título aún[/dim]"),
        ("Palabras clave",", ".join(producto_json.get("palabras_clave", [])) or "[dim]ninguna[/dim]"),
        ("Notas",         producto_json.get("notas") or "[dim]ninguna[/dim]"),
        ("Descripción",   ("[green]ya tiene[/green]" if producto_json.get("descripcion") else "[dim]sin descripción aún[/dim]")),
    ]
    for campo, valor in campos:
        table.add_row(campo, valor)

    console.print(table)
    console.print()


def pedir_info_adicional() -> dict:
    console.rule("[bold cyan]Información adicional")
    console.print("[dim]Todo es opcional — presioná Enter para saltear.[/dim]\n")

    medidas   = Prompt.ask("[bold]Medidas[/bold] [dim](ej: 30x20x15cm)[/dim]", default="")
    material  = Prompt.ask("[bold]Material[/bold] [dim](ej: plástico transparente ABS)[/dim]", default="")
    cantidad  = Prompt.ask("[bold]Cantidad de unidades en el pack[/bold] [dim](ej: 2, 6, combo de 3)[/dim]", default="")
    destacar  = Prompt.ask("[bold]¿Algo especial que destacar?[/bold] [dim](ej: apto lavadora, sin BPA)[/dim]", default="")

    return {
        k: v for k, v in {
            "medidas":  medidas.strip(),
            "material": material.strip(),
            "cantidad": cantidad.strip(),
            "destacar": destacar.strip(),
        }.items() if v
    }


def generar_descripciones_con_claude(
    cliente: anthropic.Anthropic,
    producto_json: dict,
    info_adicional: dict,
) -> list[str]:

    nombre  = producto_json.get("nombre", "")
    tipo    = producto_json.get("tipo", "")
    color   = producto_json.get("variante", {}).get("color", "")
    talle   = producto_json.get("variante", {}).get("talle", "")
    titulo  = producto_json.get("titulo_ml", "")
    kws     = producto_json.get("palabras_clave", [])
    notas   = producto_json.get("notas", "")

    extras = []
    if info_adicional.get("medidas"):
        extras.append(f"- Medidas: {info_adicional['medidas']}")
    if info_adicional.get("material"):
        extras.append(f"- Material: {info_adicional['material']}")
    if info_adicional.get("cantidad"):
        extras.append(f"- Contenido del pack: {info_adicional['cantidad']}")
    if info_adicional.get("destacar"):
        extras.append(f"- Característica especial: {info_adicional['destacar']}")

    extras_str = "\n".join(extras) if extras else "No se especificaron datos adicionales."

    prompt = f"""Generá exactamente 3 descripciones diferentes para una publicación en MercadoLibre Argentina.

Datos del producto:
- Nombre: {nombre}
- Tipo: {tipo}
- Color: {color}
- Talle/Tamaño: {talle if talle else "no especificado"}
- Título ML: {titulo if titulo else "no definido aún"}
- Palabras clave: {", ".join(kws) if kws else "ninguna"}
- Notas internas: {notas if notas else "ninguna"}

Información adicional:
{extras_str}

Criterios de escritura:
- Estilo de vendedor argentino: cálido, directo, confiable, sin exagerar
- Estructura: párrafo de apertura (qué es y por qué comprarlo) + lista de puntos destacados + cierre con llamado a la acción breve
- Máximo 1500 caracteres por descripción
- Incluir las palabras clave de forma natural, sin forzar
- Sin emojis, sin mayúsculas raras, sin signos de exclamación excesivos
- Sin bullets ni guiones al inicio de línea
- Sin HTML ni markdown, sin asteriscos ni símbolos especiales de ningún tipo
- Solo párrafos de texto plano separados por líneas en blanco
- Nada de listas: todo redactado en prosa continua
- Pensar en compradores argentinos reales buscando soluciones cotidianas
- Cada versión debe tener un enfoque diferente: una más funcional, una más emocional, una más informativa

Respondé ÚNICAMENTE con las 3 descripciones separadas por esta línea exacta:
---DESCRIPCION---

No pongas numeración, títulos ni nada antes de cada descripción."""

    console.print()
    with console.status("[bold cyan]Consultando Claude AI...[/bold cyan]", spinner="dots"):
        response = cliente.messages.create(
            model=MODEL,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )

    raw = response.content[0].text.strip()
    partes = [p.strip() for p in raw.split("---DESCRIPCION---") if p.strip()]
    return partes[:3]


def mostrar_descripciones(descripciones: list[str], tanda: int = 1):
    console.print()
    console.rule(f"[bold cyan]Descripciones generadas — Tanda {tanda}")

    for i, desc in enumerate(descripciones, 1):
        chars = len(desc)
        color = "green" if chars <= 1500 else "red"
        console.print()
        console.print(
            Panel(
                desc,
                title=f"[bold cyan]Versión {i}[/bold cyan]  [{color}]{chars} chars[/{color}]",
                box=box.ROUNDED,
                padding=(1, 2),
            )
        )

    console.print()


def elegir_descripcion(descripciones: list[str]) -> str | None:
    """
    Retorna:
    - string con la descripción elegida
    - None para cancelar
    - "NUEVO" para generar otra tanda
    """
    while True:
        respuesta = Prompt.ask(
            "[bold]¿Qué hacemos?[/bold] [dim](1/2/3, 'propia', 'nueva' para generar más, Enter para cancelar)[/dim]",
            default="",
        )
        raw = respuesta.strip()

        if not raw:
            return None

        if raw.lower() in ("nueva", "nuevo"):
            return "NUEVO"

        if raw.lower() == "propia":
            console.print("[dim]Escribí la descripción. Terminá con una línea que contenga solo 'FIN'.[/dim]")
            lineas = []
            while True:
                linea = input()
                if linea.strip().upper() == "FIN":
                    break
                lineas.append(linea)
            descripcion = "\n".join(lineas).strip()
            if not descripcion:
                console.print("[red]Descripción vacía, intenta de nuevo.[/red]")
                continue
            chars = len(descripcion)
            color = "green" if chars <= 1500 else "red"
            console.print(f"  Caracteres: [{color}]{chars}[/{color}]")
            if chars > 1500:
                console.print("[yellow]La descripción supera los 1500 caracteres.[/yellow]")
                if not Confirm.ask("¿Guardarla igual?", default=False):
                    continue
            return descripcion

        try:
            idx = int(raw) - 1
            if 0 <= idx < len(descripciones):
                return descripciones[idx]
            console.print(f"[red]Ingresá un número entre 1 y {len(descripciones)}.[/red]")
        except ValueError:
            console.print("[red]Opción no reconocida. Ingresá 1, 2, 3, 'propia', 'nueva' o Enter.[/red]")


def guardar_historial(sku: str, info_adicional: dict, descripciones: list[str], elegida: str | None):
    data = cargar_descripciones(sku)
    entrada = {
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "info_adicional": info_adicional,
        "descripciones": [
            {
                "descripcion": d,
                "caracteres": len(d),
                "elegida": (d == elegida),
            }
            for d in descripciones
        ],
    }
    data["historial"].append(entrada)
    guardar_descripciones(sku, data)


def mostrar_resultado(sku: str, descripcion: str):
    chars = len(descripcion)
    color = "green" if chars <= 1500 else "yellow"
    console.print()
    console.print(Panel(
        f"[bold green]Descripción guardada.[/bold green]\n"
        f"[bold yellow]{sku}[/bold yellow]  [{color}]{chars} caracteres[/{color}]\n\n"
        f"[dim]{descripcion[:120]}{'...' if len(descripcion) > 120 else ''}[/dim]",
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
        entrada_catalogo = elegir_producto(catalogo)
        if entrada_catalogo is None:
            console.print("[yellow]Cancelado.[/yellow]\n")
            sys.exit(0)

        sku = entrada_catalogo["sku"]
        producto_json = cargar_producto_json(sku)
        if producto_json is None:
            console.print(f"[yellow]producto.json no encontrado para {sku}. Usando datos del catálogo.[/yellow]")
            producto_json = {
                "sku": sku,
                "nombre": entrada_catalogo.get("nombre", ""),
                "tipo": entrada_catalogo.get("tipo", ""),
                "variante": {"color": "", "talle": ""},
                "palabras_clave": [],
                "titulo_ml": "",
                "descripcion": "",
                "notas": "",
                "ultima_actualizacion": "",
            }

        mostrar_datos_producto(producto_json)

        if producto_json.get("descripcion"):
            if not Confirm.ask("[yellow]Este producto ya tiene descripción. ¿Generar una nueva igual?[/yellow]", default=True):
                console.print("[yellow]Cancelado.[/yellow]\n")
                sys.exit(0)

        info_adicional = pedir_info_adicional()

        # Bucle de generación
        tanda = 1
        descripcion_elegida: str | None = None

        while True:
            descripciones_tanda = generar_descripciones_con_claude(cliente, producto_json, info_adicional)

            if not descripciones_tanda:
                console.print("[red]Claude no devolvió descripciones válidas. Intentá de nuevo.[/red]")
                if not Confirm.ask("¿Intentar otra vez?", default=True):
                    sys.exit(1)
                continue

            mostrar_descripciones(descripciones_tanda, tanda)
            decision = elegir_descripcion(descripciones_tanda)

            if decision is None:
                guardar_historial(sku, info_adicional, descripciones_tanda, None)
                console.print("\n[yellow]Cancelado. No se guardó ninguna descripción.[/yellow]\n")
                sys.exit(0)

            if decision == "NUEVO":
                guardar_historial(sku, info_adicional, descripciones_tanda, None)
                tanda += 1
                continue

            descripcion_elegida = decision
            guardar_historial(sku, info_adicional, descripciones_tanda, descripcion_elegida)
            break

        # Guardar en producto.json
        now = datetime.now().isoformat(timespec="seconds")
        producto_json["descripcion"] = descripcion_elegida
        producto_json["ultima_actualizacion"] = now
        guardar_producto_json(sku, producto_json)

        mostrar_resultado(sku, descripcion_elegida)

        historial = cargar_descripciones(sku)
        total = sum(len(h["descripciones"]) for h in historial["historial"])
        console.print(f"[dim]Historial: {len(historial['historial'])} tanda(s), {total} descripciones acumuladas → inteligencia/descripciones_generadas.json[/dim]\n")

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
