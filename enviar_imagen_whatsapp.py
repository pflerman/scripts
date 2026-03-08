#!/usr/bin/env python3
"""
Genera una imagen con Nano Banana 2 y la envía por WhatsApp.

Uso:
    python3 enviar_imagen_whatsapp.py "pato2" "un gato andando en bicicleta"
    python3 enviar_imagen_whatsapp.py "Juan" "un perro en la playa" --output /tmp/mi_imagen.png
"""
import argparse
import asyncio
import os
import subprocess
import sys
from pathlib import Path

from playwright.async_api import async_playwright

sys.path.insert(0, "/home/pepe/Proyectos")
from gemini_images import generar_imagen  # noqa: E402

DEFAULT_OUTPUT = Path("/home/pepe/Downloads/imagen_generada.png")


async def enviar_whatsapp(contacto: str, imagen_path: Path) -> None:
    print(f"Enviando imagen a '{contacto}' por WhatsApp...")
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]

        # Buscar tab de WhatsApp
        wa_page = None
        for page in context.pages:
            if "web.whatsapp.com" in page.url:
                wa_page = page
                break
        if wa_page is None:
            wa_page = await context.new_page()
            await wa_page.goto("https://web.whatsapp.com", wait_until="networkidle")
            await asyncio.sleep(5)

        await wa_page.bring_to_front()
        await asyncio.sleep(1)

        # ── Buscar contacto ──────────────────────────────────────────────────
        search = wa_page.locator('div[contenteditable="true"][data-tab="3"]')
        await search.click()
        await asyncio.sleep(0.3)
        await search.fill(contacto)
        await asyncio.sleep(2)

        # Buscar fila del chat directo (no grupos) con el nombre del contacto
        coords = await wa_page.evaluate(f"""
            () => {{
                const rows = Array.from(document.querySelectorAll('[role="row"]'));
                for (const row of rows) {{
                    const text = row.textContent.trim();
                    const r = row.getBoundingClientRect();
                    if (
                        text.toLowerCase().includes('{contacto.lower()}') &&
                        r.y > 150 && r.height > 40 && r.height < 120 &&
                        !text.includes('también está') &&
                        !text.includes('Grupos en común')
                    ) {{
                        return {{x: r.x + r.width / 2, y: r.y + r.height / 2}};
                    }}
                }}
                return null;
            }}
        """)
        if not coords:
            raise RuntimeError(f"No se encontró el contacto '{contacto}' en WhatsApp")

        print(f"  → Contacto encontrado, clickeando en {coords}")
        await wa_page.mouse.click(coords['x'], coords['y'])
        await asyncio.sleep(2)

        # Verificar que el chat abrió (botón Adjuntar en panel derecho, x > 400)
        chat_ok = await wa_page.evaluate("""
            () => Array.from(document.querySelectorAll('button[aria-label="Adjuntar"]'))
                       .some(b => b.getBoundingClientRect().x > 400)
        """)
        if not chat_ok:
            raise RuntimeError("El chat no se abrió correctamente")

        # ── Abrir menú adjuntar ──────────────────────────────────────────────
        await wa_page.evaluate("""
            Array.from(document.querySelectorAll('button')).find(
                b => ['Adjuntar', 'Attach', 'Attach file'].includes(b.getAttribute('aria-label'))
                     && b.getBoundingClientRect().x > 400
            )?.click()
        """)
        await asyncio.sleep(1.5)

        # ── Interceptar file chooser antes de que abra el GTK nativo ───────────
        # IMPORTANTE: NO usar set_input_files directo ni cerrar el dialog después.
        # El file picker de WhatsApp es nativo del OS (GTK) y no se puede cerrar
        # desde Playwright una vez abierto. expect_file_chooser() lo intercepta
        # ANTES de que aparezca en pantalla y lo maneja internamente.
        coords_fotos = await wa_page.evaluate("""
            () => {
                const textos = ['Fotos y videos', 'Photos & videos', 'Fotos e vídeos'];
                for (const texto of textos) {
                    const sp = Array.from(document.querySelectorAll('span,li,div'))
                                   .find(s => s.textContent.trim() === texto);
                    if (sp) {
                        const r = sp.getBoundingClientRect();
                        if (r.width > 0) return {x: r.x + r.width/2, y: r.y + r.height/2};
                    }
                }
                return null;
            }
        """)
        if not coords_fotos:
            raise RuntimeError("No se encontró el botón 'Fotos y videos'")

        async with wa_page.expect_file_chooser() as fc_info:
            await wa_page.mouse.click(coords_fotos['x'], coords_fotos['y'])
        file_chooser = await fc_info.value
        await file_chooser.set_files(str(imagen_path))
        await asyncio.sleep(3)

        # ── Enviar ────────────────────────────────────────────────────────────
        await wa_page.evaluate("""
            Array.from(document.querySelectorAll('button,[role="button"]'))
                .find(b => b.getAttribute('aria-label') === 'Enviar'
                           && b.getBoundingClientRect().width > 0)
                ?.click()
        """)
        await asyncio.sleep(2)
        print("Imagen enviada correctamente.")


async def main(contacto: str, prompt: str, output_path: Path, solo_enviar: bool = False) -> None:
    if not solo_enviar:
        print(f"Generando imagen con Nano Banana 2: '{prompt}'...")
        generar_imagen(prompt, output_path)
        print(f"Imagen guardada en {output_path} ({output_path.stat().st_size:,} bytes)")
    await enviar_whatsapp(contacto, output_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Genera imagen con Nano Banana 2 y la envía por WhatsApp")
    parser.add_argument("contacto", help="Nombre del contacto en WhatsApp (ej: 'pato2')")
    parser.add_argument("prompt", nargs="?", default="", help="Descripción de la imagen a generar")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Ruta donde guardar la imagen")
    parser.add_argument("--solo-enviar", action="store_true", help="No generar imagen, enviar --output directamente")
    args = parser.parse_args()

    asyncio.run(main(args.contacto, args.prompt, args.output, solo_enviar=args.solo_enviar))
