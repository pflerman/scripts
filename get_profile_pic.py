#!/usr/bin/env python3
"""Obtiene la foto de perfil de un contacto de WhatsApp Web."""
import asyncio
import sys
from pathlib import Path
from playwright.async_api import async_playwright

async def get_profile_pic(contacto: str, output_path: Path) -> Path:
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]

        wa_page = None
        for page in context.pages:
            if "web.whatsapp.com" in page.url:
                wa_page = page
                break
        if not wa_page:
            raise RuntimeError("No hay tab de WhatsApp")

        await wa_page.bring_to_front()
        await asyncio.sleep(1)

        # Abrir chat de pato2
        search = wa_page.locator('div[contenteditable="true"][data-tab="3"]')
        await search.click()
        await asyncio.sleep(0.3)
        await search.fill(contacto)
        await asyncio.sleep(2)

        # Click en el chat directo
        coords = await wa_page.evaluate(f"""
            () => {{
                const rows = Array.from(document.querySelectorAll('[role="row"]'));
                for (const row of rows) {{
                    const text = row.textContent.trim();
                    const r = row.getBoundingClientRect();
                    if (text.toLowerCase().includes('{contacto.lower()}') &&
                        r.y > 150 && r.height > 40 && r.height < 120 &&
                        !text.includes('también está') && !text.includes('Grupos en común')) {{
                        return {{x: r.x + r.width/2, y: r.y + r.height/2}};
                    }}
                }}
                return null;
            }}
        """)
        if not coords:
            raise RuntimeError(f"No se encontró el contacto '{contacto}'")
        await wa_page.mouse.click(coords['x'], coords['y'])
        await asyncio.sleep(2)

        # Click en el header del chat para abrir el perfil
        header_coords = await wa_page.evaluate("""
            () => {
                const headers = Array.from(document.querySelectorAll('header'));
                for (const h of headers) {
                    const r = h.getBoundingClientRect();
                    if (r.x > 400 && r.width > 400) {
                        return {x: r.x + r.width/2, y: r.y + r.height/2};
                    }
                }
                return null;
            }
        """)
        if not header_coords:
            raise RuntimeError("No se encontró el header del chat")
        await wa_page.mouse.click(header_coords['x'], header_coords['y'])
        await asyncio.sleep(2)

        # Obtener URL del avatar del header del chat (CDN de WhatsApp)
        result = await wa_page.evaluate("""
            async () => {
                // Buscar el img del avatar en el header del chat (panel derecho x>400)
                const headers = Array.from(document.querySelectorAll('header'));
                let imgSrc = null;
                for (const h of headers) {
                    const r = h.getBoundingClientRect();
                    if (r.x > 400 && r.width > 400) {
                        const img = h.querySelector('img');
                        if (img && img.src) { imgSrc = img.src; break; }
                    }
                }
                if (!imgSrc) return null;
                const resp = await fetch(imgSrc);
                const buf = await resp.arrayBuffer();
                return {bytes: Array.from(new Uint8Array(buf)), src: imgSrc};
            }
        """)
        if not result or len(result['bytes']) < 1000:
            raise RuntimeError("No se encontró la foto de perfil")

        img_src = result['src']
        img_bytes = result['bytes']
        print(f"Foto de perfil encontrada: {img_src[:80]}...")
        output_path.write_bytes(bytes(img_bytes if isinstance(img_bytes, (bytes, bytearray)) else bytes(img_bytes)))
        print(f"Foto guardada en {output_path} ({len(img_bytes):,} bytes)")

        # Cerrar el panel de perfil con Escape
        await wa_page.keyboard.press("Escape")
        await asyncio.sleep(0.5)

        return output_path

if __name__ == "__main__":
    contacto = sys.argv[1] if len(sys.argv) > 1 else "pato2"
    out = Path(f"/home/pepe/Downloads/perfil_{contacto}.jpg")
    asyncio.run(get_profile_pic(contacto, out))
    print(f"Listo: {out}")
