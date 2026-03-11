#!/usr/bin/env python3
"""
Genera clips de video 9:16 para publicaciones de MercadoLibre usando Shotstack.
"""

import argparse
import json
import os
import sys
import time

import requests

SHOTSTACK_ENDPOINT = "https://api.shotstack.io/edit/stage"
ML_CREDENTIALS_PATH = "/home/pepe/Proyectos/ml-scripts/config/ml_credentials_palishopping.json"
DEFAULT_APIKEY = "BAOBm8sqJFcOUESQsCACZaoheM35lYe5MX"
MUSIC_URL = "https://shotstack-assets.s3-ap-southeast-2.amazonaws.com/music/unminus/palmtrees.mp3"

KEN_BURNS_EFFECTS = ["zoomIn", "zoomOut", "slideLeft", "slideRight"]


def load_ml_token():
    with open(ML_CREDENTIALS_PATH) as f:
        creds = json.load(f)
    return creds["access_token"]


def fetch_ml_item(item_id, token):
    url = f"https://api.mercadolibre.com/items/{item_id}"
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(url, headers=headers, timeout=15)
    r.raise_for_status()
    data = r.json()

    fotos = []
    for pic in data.get("pictures", []):
        url_foto = pic.get("secure_url") or pic.get("url", "")
        if url_foto:
            fotos.append(url_foto)

    titulo = data.get("title", "")
    return fotos, titulo


def build_payload(fotos, titulo, fps=25, duration_per_photo=3):
    clips = []
    start = 0.0

    for i, foto_url in enumerate(fotos):
        effect = KEN_BURNS_EFFECTS[i % len(KEN_BURNS_EFFECTS)]
        clip = {
            "asset": {
                "type": "image",
                "src": foto_url,
            },
            "start": start,
            "length": duration_per_photo,
            "effect": effect,
            "fit": "cover",
        }
        clips.append(clip)
        start += duration_per_photo

    total_duration = start
    title_start = max(0.0, total_duration - 3)
    title_duration = min(3.0, total_duration)

    # Clip de texto con el título al final
    title_clip = {
        "asset": {
            "type": "title",
            "text": titulo,
            "style": "minimal",
            "size": "small",
        },
        "start": title_start,
        "length": title_duration,
        "position": "bottom",
        "transition": {
            "in": "fade",
            "out": "fade",
        },
    }

    track_fotos = {"clips": clips}
    track_titulo = {"clips": [title_clip]}

    track_musica = {
        "clips": [
            {
                "asset": {
                    "type": "audio",
                    "src": MUSIC_URL,
                    "volume": 0.5,
                },
                "start": 0,
                "length": total_duration,
            }
        ]
    }

    payload = {
        "timeline": {
            "tracks": [track_titulo, track_fotos],
            "soundtrack": {
                "src": MUSIC_URL,
                "effect": "fadeOut",
                "volume": 0.5,
            },
        },
        "output": {
            "format": "mp4",
            "resolution": "sd",
            "fps": fps,
            "aspectRatio": "9:16",
        },
    }

    return payload


def submit_render(payload, apikey):
    url = f"{SHOTSTACK_ENDPOINT}/render"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": apikey,
    }
    r = requests.post(url, json=payload, headers=headers, timeout=30)
    if not r.ok:
        print(f"Error al enviar render: {r.status_code} {r.text}")
        sys.exit(1)
    data = r.json()
    render_id = data["response"]["id"]
    print(f"Render enviado. ID: {render_id}")
    return render_id


def poll_render(render_id, apikey, interval=5):
    url = f"{SHOTSTACK_ENDPOINT}/render/{render_id}"
    headers = {"x-api-key": apikey}

    while True:
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        data = r.json()["response"]
        status = data["status"]
        print(f"  Status: {status} ...")

        if status == "done":
            return data["url"]
        elif status == "failed":
            print(f"Render fallido: {data.get('error', 'sin detalle')}")
            sys.exit(1)

        time.sleep(interval)


def download_video(video_url, output_path):
    print(f"Descargando video desde {video_url} ...")
    r = requests.get(video_url, stream=True, timeout=120)
    r.raise_for_status()
    with open(output_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)
    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"Guardado en: {output_path} ({size_mb:.2f} MB)")


def main():
    parser = argparse.ArgumentParser(description="Genera clip de video para publicación ML")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--item", help="ID de publicación ML (ej: MLA1234567890)")
    group.add_argument("--fotos", help="URLs de fotos separadas por coma (para testeo sin token)")
    parser.add_argument("--titulo", help="Título manual (usar con --fotos)")
    parser.add_argument(
        "--apikey",
        default=os.environ.get("SHOTSTACK_KEY", DEFAULT_APIKEY),
        help="API key de Shotstack",
    )
    parser.add_argument("--output", default="clip_ml.mp4", help="Archivo de salida")
    args = parser.parse_args()

    if not args.item and not args.fotos:
        parser.error("Debe especificar --item o --fotos")

    # Obtener fotos y título
    if args.item:
        print(f"Obteniendo datos de ML para {args.item} ...")
        token = load_ml_token()
        fotos, titulo = fetch_ml_item(args.item, token)
        if not fotos:
            print("No se encontraron fotos en la publicación.")
            sys.exit(1)
        print(f"Título: {titulo}")
        print(f"Fotos encontradas: {len(fotos)}")
    else:
        fotos = [u.strip() for u in args.fotos.split(",") if u.strip()]
        titulo = args.titulo or "Producto"
        print(f"Usando {len(fotos)} foto(s) manuales. Título: {titulo}")

    # Limitar a 10 fotos para no exceder duración razonable
    if len(fotos) > 10:
        print(f"Usando las primeras 10 de {len(fotos)} fotos.")
        fotos = fotos[:10]

    print("Armando payload para Shotstack ...")
    payload = build_payload(fotos, titulo)

    print("Enviando render a Shotstack ...")
    render_id = submit_render(payload, args.apikey)

    print("Esperando resultado del render ...")
    video_url = poll_render(render_id, args.apikey)

    print(f"\nVideo listo: {video_url}")
    download_video(video_url, args.output)
    print("\nListo.")


if __name__ == "__main__":
    main()
