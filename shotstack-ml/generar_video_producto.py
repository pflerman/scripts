#!/usr/bin/env python3
"""
Pipeline reutilizable: D-ID avatar + Shotstack video de producto + compresión + WhatsApp.

Uso CLI:
    python3 generar_video_producto.py \
        --fotos https://0x0.st/A.jpg,https://0x0.st/B.jpg \
        --titulo "Mi Producto" \
        --contacto pato2 \
        --script-avatar "Hola, te presento este producto increíble."

Uso como módulo:
    from generar_video_producto import pipeline_completo
    url = pipeline_completo(fotos_urls, titulo, contacto, script_avatar)
"""

import argparse
import asyncio
import base64
import subprocess
import sys
import time
from pathlib import Path

import requests

# ── Configuración ─────────────────────────────────────────────────────────────

SHOTSTACK_APIKEY   = "7h6x5BAOBm8sqJFcOUESQsCACZaoheM35lYe5MXH"
SHOTSTACK_ENDPOINT = "https://api.shotstack.io/stage/render"

# D-ID: auth es "Basic <base64_email_literal>:<api_key_literal>" (formato propio)
DID_AUTH    = "Basic cGZsZXJtYW5AZ21haWwuY29t:Y3nwPoy9RQ4u0yS8sOGI-"
DID_BASE    = "https://api.d-id.com"

MUSIC_URL  = "https://shotstack-assets.s3-ap-southeast-2.amazonaws.com/music/unminus/palmtrees.mp3"

KB_BASE    = Path("/home/pepe/Proyectos/palishopping-kb/productos-base")
TMP_DIR    = Path("/tmp")

# Ken Burns effects que se ciclan por foto
EFFECTS    = ["zoomIn", "zoomOut", "slideLeft", "zoomIn", "zoomOut",
              "slideRight", "zoomIn", "zoomOut", "slideLeft", "slideRight"]

# ── Helpers internos ──────────────────────────────────────────────────────────

def _shotstack_headers() -> dict:
    return {"Content-Type": "application/json", "x-api-key": SHOTSTACK_APIKEY}


def _did_headers() -> dict:
    return {"Authorization": DID_AUTH, "Accept": "application/json",
            "Content-Type": "application/json"}


def _html_bar(text: str, bg: str, color: str, font_size: int,
               width: int = 720, height: int = 130) -> str:
    return (
        f"<div style='width:{width}px;height:{height}px;"
        f"display:flex;align-items:center;justify-content:center;"
        f"background:{bg};padding:15px 25px;box-sizing:border-box;'>"
        f"<span style='font-family:Arial,sans-serif;font-size:{font_size}px;"
        f"font-weight:bold;color:{color};text-align:center;"
        f"text-shadow:1px 1px 3px rgba(0,0,0,0.5);'>{text}</span></div>"
    )


# ── Paso 1: subir fotos a 0x0.st ─────────────────────────────────────────────

def subir_foto(path: Path) -> str:
    """Sube una imagen a 0x0.st y devuelve la URL pública."""
    with open(path, "rb") as f:
        r = requests.post("https://0x0.st", files={"file": (path.name, f, "image/jpeg")},
                          timeout=30)
    r.raise_for_status()
    url = r.text.strip()
    if not url.startswith("http"):
        raise RuntimeError(f"0x0.st rechazó la imagen: {url}")
    return url


def subir_fotos_sku(sku: str, max_fotos: int = 5) -> list[str]:
    """Sube las fotos listas_gemini de un SKU a 0x0.st y devuelve las URLs."""
    carpeta = KB_BASE / sku / "fotos" / "listas_gemini"
    if not carpeta.exists():
        raise FileNotFoundError(f"No se encontró carpeta de fotos: {carpeta}")
    fotos = sorted(carpeta.glob("*.jpg"))[:max_fotos]
    if not fotos:
        raise FileNotFoundError(f"No hay fotos JPG en {carpeta}")
    print(f"Subiendo {len(fotos)} fotos a 0x0.st…")
    urls = []
    for foto in fotos:
        url = subir_foto(foto)
        print(f"  {foto.name} → {url}")
        urls.append(url)
    return urls


# ── Paso 2: generar avatar D-ID ──────────────────────────────────────────────

def generar_avatar_did(script: str, voz: str = "es-ES-ElviraNeural") -> str:
    """
    Crea un D-ID talk y espera hasta que esté listo.
    Devuelve la URL del video del avatar.

    Auth D-ID: formato propio → Basic <base64(email)>:<api_key_raw>
    NO es Basic base64(email:key), es Basic b64_email:key_literal.
    """
    payload = {
        "source_url": "https://d-id-public-bucket.s3.amazonaws.com/alice.jpg",
        "script": {
            "type": "text",
            "input": script,
            "subtitles": False,
            "provider": {"type": "microsoft", "voice_id": voz},
        },
        "config": {"fluent": True, "pad_audio": 0.5},
    }
    print("Creando D-ID talk…")
    r = requests.post(f"{DID_BASE}/talks", headers=_did_headers(), json=payload, timeout=30)
    r.raise_for_status()
    talk_id = r.json()["id"]
    print(f"  Talk ID: {talk_id} — polling…")

    for _ in range(40):
        time.sleep(5)
        r = requests.get(f"{DID_BASE}/talks/{talk_id}", headers=_did_headers(), timeout=15)
        d = r.json()
        status = d.get("status", "")
        print(f"  D-ID status: {status}")
        if status == "done":
            url = d["result_url"]
            print(f"  Avatar listo: {url[:80]}…")
            return url
        if status in ("error", "failed"):
            raise RuntimeError(f"D-ID falló: {d.get('error', '')}")

    raise TimeoutError("D-ID no terminó en tiempo esperado")


# ── Paso 3: renderizar video en Shotstack ─────────────────────────────────────

def renderizar_shotstack(
    fotos_urls: list[str],
    titulo: str,
    avatar_url: str | None = None,
    dur_foto: int = 4,
) -> str:
    """
    Genera el video en Shotstack con técnica de fondo difuminado (9:16).
    - Capa fondo: fit cover + opacity 0.40 + filter muted
    - Capa frente: fit contain nítido
    - Primer clip sin fade-in para que WhatsApp use el frame 0 como thumbnail
    - Avatar D-ID en esquina inferior derecha (opcional)
    Devuelve la URL del video renderizado.
    """
    total    = len(fotos_urls) * dur_foto
    W, H     = 720, 1280
    BAR_H    = 130

    clips_fondo  = []
    clips_frente = []

    for i, (url, fx) in enumerate(zip(fotos_urls, EFFECTS)):
        s         = i * dur_foto
        trans_in  = "none" if i == 0 else "fade"   # frame 0 visible → thumbnail WhatsApp

        clips_fondo.append({
            "asset": {"type": "image", "src": url},
            "start": s, "length": dur_foto,
            "fit": "cover", "opacity": 0.40, "filter": "muted", "effect": fx,
            "transition": {"in": trans_in, "out": "fade"},
        })
        clips_frente.append({
            "asset": {"type": "image", "src": url},
            "start": s, "length": dur_foto,
            "fit": "contain", "opacity": 1.0, "effect": fx,
            "transition": {"in": trans_in, "out": "fade"},
        })

    track_nombre = {"clips": [{
        "asset": {"type": "html",
                  "html": _html_bar(titulo, "rgba(0,0,0,0.70)", "#ffffff", 46, W, BAR_H),
                  "width": W, "height": BAR_H},
        "start": 0, "length": total, "position": "top",
        "transition": {"in": "none"},
    }]}

    track_cta = {"clips": [{
        "asset": {"type": "html",
                  "html": _html_bar("Compralo en MercadoLibre 🛒",
                                    "rgba(255,214,0,0.90)", "#222222", 34, W, BAR_H),
                  "width": W, "height": BAR_H},
        "start": 0, "length": total, "position": "bottom",
        "transition": {"in": "none"},
    }]}

    tracks = [track_nombre, track_cta]

    if avatar_url:
        tracks.append({"clips": [{
            "asset": {"type": "video", "src": avatar_url, "volume": 1.0},
            "start": 0, "length": total,
            "position": "bottomRight",
            "offset": {"x": -0.03, "y": 0.08},
            "scale": 0.30,
            "transition": {"in": "fade"},
        }]})

    tracks += [{"clips": clips_frente}, {"clips": clips_fondo}]

    payload = {
        "timeline": {
            "background": "#000000",
            "tracks": tracks,
            "soundtrack": {"src": MUSIC_URL, "effect": "fadeOut", "volume": 0.25},
        },
        "output": {"format": "mp4", "resolution": "hd", "aspectRatio": "9:16", "fps": 25},
    }

    print("Enviando render a Shotstack…")
    r = requests.post(SHOTSTACK_ENDPOINT, headers=_shotstack_headers(), json=payload, timeout=30)
    r.raise_for_status()
    render_id = r.json()["response"]["id"]
    print(f"  Render ID: {render_id} — polling…")

    poll = f"{SHOTSTACK_ENDPOINT.replace('/render','')}/render/{render_id}"
    while True:
        r = requests.get(poll, headers={"x-api-key": SHOTSTACK_APIKEY}, timeout=15)
        d = r.json()["response"]
        status = d["status"]
        print(f"  Shotstack: {status}")
        if status == "done":
            url = d["url"]
            print(f"  Video listo: {url}")
            return url
        if status in ("failed", "error"):
            raise RuntimeError(f"Shotstack falló: {d.get('error','sin detalle')}")
        time.sleep(5)


# ── Paso 4: comprimir con ffmpeg ──────────────────────────────────────────────

def comprimir_video(url_input: str, output_path: Path) -> Path:
    """
    Descarga el video de url_input y lo comprime con libopenh264 a 600k.
    (libx264 NO disponible en este sistema — ffmpeg compilado sin él)
    El primer frame ya tiene contenido visible → WhatsApp lo usa como thumbnail.
    """
    output_path = Path(output_path)
    tmp_input   = TMP_DIR / "video_sin_comprimir.mp4"

    print(f"Descargando {url_input[:60]}…")
    r = requests.get(url_input, stream=True, timeout=120)
    r.raise_for_status()
    with open(tmp_input, "wb") as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)

    size_orig = tmp_input.stat().st_size / 1024**2
    print(f"  Descargado: {size_orig:.2f} MB")

    print("Comprimiendo con ffmpeg (libopenh264 600k)…")
    subprocess.run([
        "ffmpeg", "-i", str(tmp_input),
        "-c:v", "libopenh264", "-b:v", "600k",
        "-c:a", "aac", "-b:a", "96k",
        str(output_path), "-y",
    ], check=True, capture_output=True)

    size_comp = output_path.stat().st_size / 1024**2
    print(f"  Comprimido: {size_comp:.2f} MB ({(1-size_comp/size_orig)*100:.1f}% reducción)")
    return output_path


# ── Paso 5: enviar por WhatsApp ───────────────────────────────────────────────

def enviar_whatsapp(contacto: str, video_path: Path) -> None:
    """Envía el video al contacto de WhatsApp via Playwright CDP (Brave)."""
    sys.path.insert(0, "/home/pepe/Proyectos")
    from enviar_imagen_whatsapp import enviar_whatsapp as _enviar

    print(f"Enviando a {contacto} por WhatsApp…")
    asyncio.run(_enviar(contacto, Path(video_path)))
    print("  Enviado correctamente.")


# ── Pipeline completo ─────────────────────────────────────────────────────────

def pipeline_completo(
    fotos_urls: list[str],
    titulo: str,
    contacto: str | None = None,
    script_avatar: str | None = None,
    voz_avatar: str = "es-ES-ElviraNeural",
    output_path: Path | None = None,
) -> str:
    """
    Pipeline completo:
      1. (Opcional) Generar avatar D-ID
      2. Renderizar video en Shotstack (9:16, fondo difuminado, primer frame visible)
      3. Comprimir con ffmpeg
      4. (Opcional) Enviar por WhatsApp

    Devuelve la URL del video Shotstack original.
    """
    # 1. Avatar D-ID (opcional)
    avatar_url = None
    if script_avatar:
        avatar_url = generar_avatar_did(script_avatar, voz_avatar)

    # 2. Render Shotstack
    video_url = renderizar_shotstack(fotos_urls, titulo, avatar_url)

    # 3. Comprimir
    out = output_path or TMP_DIR / "video_producto_final.mp4"
    comprimir_video(video_url, out)

    # 4. WhatsApp (opcional)
    if contacto:
        enviar_whatsapp(contacto, out)

    return video_url


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Genera video de producto ML con D-ID + Shotstack"
    )
    parser.add_argument("--fotos", required=True,
                        help="URLs de fotos separadas por coma")
    parser.add_argument("--titulo", required=True,
                        help="Nombre del producto para el texto superior")
    parser.add_argument("--contacto", default=None,
                        help="Contacto WhatsApp (opcional)")
    parser.add_argument("--script-avatar", default=None,
                        help="Script de voz para D-ID (opcional)")
    parser.add_argument("--voz", default="es-ES-ElviraNeural",
                        help="Voz D-ID Microsoft (default: es-ES-ElviraNeural)")
    parser.add_argument("--output", default="/tmp/video_producto_final.mp4",
                        help="Ruta de salida del MP4 comprimido")
    args = parser.parse_args()

    fotos_urls = [u.strip() for u in args.fotos.split(",") if u.strip()]
    video_url  = pipeline_completo(
        fotos_urls    = fotos_urls,
        titulo        = args.titulo,
        contacto      = args.contacto,
        script_avatar = args.script_avatar,
        voz_avatar    = args.voz,
        output_path   = Path(args.output),
    )
    print(f"\nURL Shotstack: {video_url}")
    print(f"Comprimido en: {args.output}")


if __name__ == "__main__":
    main()
