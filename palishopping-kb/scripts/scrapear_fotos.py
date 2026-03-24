#!/usr/bin/env python3
"""
scrapear_fotos.py — Scrapea fotos de una publicación de MercadoLibre y las guarda en la KB.

Uso: python3 scrapear_fotos.py
Requiere: playwright instalado y ~/.ml_cookies.json con cookies de sesión ML.
"""

import asyncio
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich import box

KB_ROOT = Path(__file__).resolve().parent.parent
PRODUCTOS_BASE = KB_ROOT / "productos-base"
CATALOGO = KB_ROOT / "catalogo.json"
ML_COOKIES_PATH = Path.home() / ".ml_cookies.json"

console = Console()


# ── Helpers de datos ─────────────────────────────────────────────────────────

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


def cargar_cookies_ml() -> list[dict] | None:
    """Convierte ~/.ml_cookies.json (Cookie-Editor) al formato Playwright."""
    if not ML_COOKIES_PATH.exists():
        console.print(f"[yellow]No se encontró {ML_COOKIES_PATH}. Se navegará sin cookies.[/yellow]")
        return None

    try:
        raw = json.loads(ML_COOKIES_PATH.read_text())
    except Exception as e:
        console.print(f"[yellow]No se pudo leer cookies: {e}[/yellow]")
        return None

    samesite_map = {
        "no_restriction": "None",
        "lax":            "Lax",
        "strict":         "Strict",
        "unspecified":    "Lax",
    }

    cookies = []
    for c in raw:
        domain = c.get("domain", "")
        if "mercadolibre" not in domain and "mlstatic" not in domain:
            continue
        if c.get("session", False) or "expirationDate" not in c:
            continue

        cookies.append({
            "name":     c["name"],
            "value":    c["value"],
            "domain":   domain,
            "path":     c.get("path", "/"),
            "secure":   c.get("secure", False),
            "httpOnly": c.get("httpOnly", False),
            "sameSite": samesite_map.get(c.get("sameSite", "lax").lower(), "Lax"),
            "expires":  int(c["expirationDate"]),
        })

    console.print(f"  [green]Cookies ML: {len(cookies)} persistentes cargadas.[/green]")
    return cookies if cookies else None


# ── Lógica de extracción de URLs ──────────────────────────────────────────────

def es_url_alta_resolucion(url: str) -> bool:
    """Retorna True si la URL parece ser de alta resolución."""
    # Patrón -O.jpg (original) de mlstatic
    if re.search(r"-O\.jpg", url):
        return True
    # Patrón con dimensiones: 800x800, 1200x1200, etc.
    if re.search(r"[_-](\d{3,4})x(\d{3,4})", url):
        m = re.search(r"[_-](\d{3,4})x(\d{3,4})", url)
        if m and int(m.group(1)) >= 800:
            return True
    return False


def normalizar_a_alta_res(url: str) -> str:
    """
    Convierte una URL de mlstatic a su versión -O (original/máxima resolución).
    Ej: https://http2.mlstatic.com/D_NQ_NP_123456-MLA1234-F.jpg
     → https://http2.mlstatic.com/D_NQ_NP_123456-MLA1234-O.jpg
    """
    # Reemplazar sufijo de tamaño por -O
    url = re.sub(r"-[A-Z]\.jpg", "-O.jpg", url)
    # Quitar parámetros de query
    url = url.split("?")[0]
    return url


async def extraer_urls_fotos(url_pagina: str, cookies: list[dict] | None) -> list[str]:
    """Navega con Playwright y extrae URLs de imágenes de alta resolución."""
    from playwright.async_api import async_playwright, TimeoutError as PWTimeout

    urls_encontradas: set[str] = set()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )

        if cookies:
            try:
                await context.add_cookies(cookies)
            except Exception as e:
                console.print(f"  [yellow]WARN: Error al cargar cookies: {e}[/yellow]")

        page = await context.new_page()

        try:
            console.print(f"  [dim]Navegando a {url_pagina}[/dim]")
            await page.goto(url_pagina, wait_until="domcontentloaded", timeout=30_000)

            # Esperar a que carguen las miniaturas de la galería
            try:
                await page.wait_for_selector(
                    "figure.ui-pdp-gallery__figure img, "
                    ".ui-pdp-image img, "
                    "img[src*='mlstatic']",
                    timeout=10_000,
                )
            except PWTimeout:
                console.print("  [yellow]Timeout esperando galería, intentando con lo que hay...[/yellow]")

            # Extraer URLs de todas las imágenes presentes en la página
            img_srcs = await page.evaluate("""() => {
                const imgs = document.querySelectorAll('img');
                return Array.from(imgs).map(img => img.src || img.getAttribute('data-src') || '').filter(Boolean);
            }""")

            # También buscar en atributos srcset y data-zoom
            extras = await page.evaluate("""() => {
                const results = [];
                document.querySelectorAll('[data-zoom], [data-src], [srcset]').forEach(el => {
                    if (el.dataset.zoom) results.push(el.dataset.zoom);
                    if (el.dataset.src) results.push(el.dataset.src);
                    if (el.srcset) {
                        el.srcset.split(',').forEach(s => {
                            const u = s.trim().split(' ')[0];
                            if (u) results.push(u);
                        });
                    }
                });
                return results;
            }""")

            todas = img_srcs + extras

            for url in todas:
                if not url or "mlstatic" not in url:
                    continue
                # Normalizar a alta res y agregar
                url_hi = normalizar_a_alta_res(url)
                if url_hi:
                    urls_encontradas.add(url_hi)

        except PWTimeout:
            console.print("  [red]Timeout al cargar la página.[/red]")
        except Exception as e:
            console.print(f"  [red]Error navegando: {e}[/red]")
        finally:
            await browser.close()

    # Filtrar solo las que parecen ser de producto (no logos, iconos, etc.)
    urls_filtradas = [
        u for u in urls_encontradas
        if "mlstatic.com" in u and re.search(r"D_NQ_NP|D_NQ_PH|D_NQ_NQ", u)
    ]

    # Si no hay con ese patrón estricto, caer en cualquier mlstatic con -O
    if not urls_filtradas:
        urls_filtradas = [u for u in urls_encontradas if "-O.jpg" in u]

    # Deduplicar por ID de imagen: preferir _2X_ sobre versión sin _2X_.
    # El ID se extrae como la parte entre el prefijo (D_NQ_NP_ etc.) y el número de MLA.
    # Ej: "D_NQ_NP_123456-MLA78901234-O.jpg" → ID "123456"
    #     "D_NQ_NP_2X_123456-MLA78901234-O.jpg" → mismo ID, pero con _2X_
    por_id: dict[str, str] = {}  # id_imagen → mejor url
    sin_id: list[str] = []

    for u in urls_filtradas:
        m = re.search(r"D_NQ_(?:NP|PH|NQ)_(?:2X_)?(\d+)", u)
        if not m:
            sin_id.append(u)
            continue
        img_id = m.group(1)
        es_2x = bool(re.search(r"D_NQ_(?:NP|PH|NQ)_2X_", u))
        if img_id not in por_id or es_2x:
            por_id[img_id] = u

    return sorted(por_id.values()) + sin_id


# ── Descarga ──────────────────────────────────────────────────────────────────

async def descargar_fotos(
    urls: list[str],
    destino: Path,
    offset: int = 0,
) -> list[tuple[Path, int]]:
    """
    Descarga las URLs y guarda como 01.jpg, 02.jpg... (o desde offset+1).
    Retorna lista de (path, tamaño_bytes).
    """
    resultados = []

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        for i, url in enumerate(urls, start=offset + 1):
            nombre = f"{i:02d}.jpg"
            path = destino / nombre

            try:
                with console.status(f"  Descargando {nombre}...", spinner="dots"):
                    resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                    resp.raise_for_status()
                    path.write_bytes(resp.content)
                    resultados.append((path, len(resp.content)))
                    console.print(f"  [green]✓[/green] {nombre}  [dim]({len(resp.content) // 1024} KB)[/dim]")
            except Exception as e:
                console.print(f"  [red]✗[/red] {nombre}: {e}")

    return resultados


# ── Interfaz ──────────────────────────────────────────────────────────────────

def mostrar_bienvenida():
    console.print()
    console.print(Panel(
        "[bold cyan]Scrapear Fotos de MercadoLibre — Palishopping KB[/bold cyan]\n"
        "[dim]Descarga fotos en alta resolución de una publicación ML a la KB.[/dim]",
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
            f"[bold]Elegí un producto destino[/bold] [dim](número 1-{len(catalogo)} o SKU, Enter para cancelar)[/dim]",
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


def mostrar_resumen_fotos(resultados: list[tuple[Path, int]], kb_root: Path):
    console.print()
    console.rule("[bold green]Fotos descargadas")
    console.print()

    table = Table(box=box.ROUNDED, padding=(0, 1))
    table.add_column("Archivo", style="bold yellow", min_width=10)
    table.add_column("Path",    min_width=50)
    table.add_column("Tamaño",  style="bold white", width=10, justify="right")

    total_bytes = 0
    for path, size in resultados:
        try:
            rel = path.relative_to(kb_root)
        except ValueError:
            rel = path
        table.add_row(path.name, str(rel), f"{size // 1024} KB")
        total_bytes += size

    console.print(table)
    console.print()
    console.print(
        f"  [bold green]{len(resultados)} foto(s)[/bold green] descargadas  •  "
        f"Total: [bold]{total_bytes // 1024} KB[/bold]"
    )
    console.print()


# ── Main ──────────────────────────────────────────────────────────────────────

async def main_async():
    mostrar_bienvenida()

    catalogo = cargar_catalogo()
    entrada = elegir_producto(catalogo)
    if entrada is None:
        console.print("[yellow]Cancelado.[/yellow]\n")
        return

    sku = entrada["sku"]
    producto_json = cargar_producto_json(sku)
    if producto_json is None:
        console.print(f"[yellow]producto.json no encontrado para {sku}. Se usarán datos del catálogo.[/yellow]")
        producto_json = {
            "sku": sku,
            "nombre": entrada.get("nombre", ""),
            "fotos_originales_ref": [],
            "ultima_actualizacion": "",
        }

    console.print()
    url_ref = Prompt.ask("[bold]URL de la publicación ML de referencia[/bold]")
    url_ref = url_ref.strip()
    if not url_ref.startswith("http"):
        console.print("[red]URL inválida.[/red]")
        return

    destino = PRODUCTOS_BASE / sku / "fotos" / "originales"
    destino.mkdir(parents=True, exist_ok=True)

    # Chequear fotos existentes
    existentes = sorted(destino.glob("*.jpg"))
    offset = 0

    if existentes:
        console.print(f"\n  [yellow]Ya hay {len(existentes)} foto(s) en originales/[/yellow]")
        modo = Prompt.ask(
            "  [bold]¿Qué hacemos?[/bold]",
            choices=["agregar", "sobreescribir", "cancelar"],
            default="agregar",
        )
        if modo == "cancelar":
            console.print("[yellow]Cancelado.[/yellow]\n")
            return
        if modo == "sobreescribir":
            for f in existentes:
                f.unlink()
            console.print(f"  [dim]Eliminadas {len(existentes)} fotos anteriores.[/dim]")
            offset = 0
        else:
            # agregar: continuar numeración
            nums = []
            for f in existentes:
                try:
                    nums.append(int(f.stem))
                except ValueError:
                    pass
            offset = max(nums) if nums else len(existentes)

    # Cargar cookies y extraer URLs
    console.print()
    console.rule("[bold cyan]Extrayendo URLs")
    console.print()

    cookies = cargar_cookies_ml()

    with console.status("[bold cyan]Analizando página con Playwright...[/bold cyan]", spinner="dots"):
        urls = await extraer_urls_fotos(url_ref, cookies)

    if not urls:
        console.print("[red]No se encontraron fotos en alta resolución en esa página.[/red]")
        console.print("[dim]Verificá que la URL sea de una publicación ML válida y que las cookies estén vigentes.[/dim]")
        return

    console.print()
    console.print(f"  [bold green]{len(urls)} foto(s)[/bold green] encontradas en alta resolución.")
    console.print()

    # Mostrar URLs encontradas
    table_urls = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    table_urls.add_column("N°",  style="bold cyan", width=4, justify="right")
    table_urls.add_column("URL", style="dim")
    for i, u in enumerate(urls, 1):
        table_urls.add_row(str(i), u[:90] + ("..." if len(u) > 90 else ""))
    console.print(table_urls)
    console.print()

    if not Confirm.ask(f"[bold]¿Descargar estas {len(urls)} foto(s)?[/bold]", default=True):
        console.print("[yellow]Cancelado.[/yellow]\n")
        return

    # Descargar
    console.print()
    console.rule("[bold cyan]Descargando")
    console.print()

    resultados = await descargar_fotos(urls, destino, offset=offset)

    if not resultados:
        console.print("[red]No se pudo descargar ninguna foto.[/red]")
        return

    # Actualizar producto.json
    now = datetime.now().isoformat(timespec="seconds")
    refs = producto_json.get("fotos_originales_ref", [])
    refs.append({
        "url_fuente": url_ref,
        "fecha_scrapeo": now,
        "fotos_descargadas": len(resultados),
    })
    producto_json["fotos_originales_ref"] = refs
    producto_json["ultima_actualizacion"] = now
    guardar_producto_json(sku, producto_json)

    mostrar_resumen_fotos(resultados, KB_ROOT)

    console.print(Panel(
        f"[bold green]Listo.[/bold green] "
        f"[bold]{len(resultados)}[/bold] foto(s) guardadas en:\n"
        f"[dim]{destino}[/dim]",
        box=box.ROUNDED,
        padding=(0, 2),
    ))
    console.print()


def main():
    try:
        asyncio.run(main_async())
    except (KeyboardInterrupt, EOFError):
        console.print("\n[yellow]Cancelado.[/yellow]\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
