#!/usr/bin/env python3
"""
_test_pipeline.py — Prueba el pipeline completo de gestionar_fotos.py
sin interacción: llama los helpers directamente para todos los productos
del catálogo que tengan fotos en originales/.
"""

import json
import sys
import time
import traceback
from pathlib import Path

# Agregar scripts/ al path para importar gestionar_fotos
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

import gestionar_fotos as gf   # noqa: E402 — importa con side-effects mínimos

KB_ROOT        = SCRIPTS.parent
PRODUCTOS_BASE = KB_ROOT / "productos-base"
CATALOGO       = KB_ROOT / "catalogo.json"

# ── Helpers de resultado ───────────────────────────────────────────────────────

def contar(directorio: Path) -> int:
    """Retorna cantidad de imágenes en directorio (0 si no existe)."""
    if not directorio.exists():
        return 0
    return len(gf.listar_fotos(directorio))


# ── Pipeline por producto ──────────────────────────────────────────────────────

def run_pipeline(sku: str, precio: str, specs: str) -> dict:
    """
    Ejecuta las 6 etapas para un SKU. Retorna dict con conteos y errores.
    """
    dir_fotos      = PRODUCTOS_BASE / sku / "fotos"
    dir_originales = dir_fotos / "originales"
    dir_procesadas = dir_fotos / "procesadas"
    dir_con_fondo  = dir_fotos / "con_fondo"
    dir_listas     = dir_fotos / "listas_gemini"
    dir_con_texto  = dir_fotos / "con_texto"

    result = {
        "sku":         sku,
        "originales":  contar(dir_originales),
        "con_fondo":   0,
        "confondo_txt": 0,
        "procesadas":  0,
        "listas":      0,
        "sinfondo_txt": 0,
        "errores":     [],
    }

    if result["originales"] == 0:
        result["errores"].append("sin fotos en originales/")
        return result

    usar_cv2 = gf._cv2_disponible()
    usar_rembg = gf._rembg_disponible()

    fotos_orig = gf.listar_fotos(dir_originales)

    # ── 6A: Optimizar originales/ → con_fondo/ ────────────────────────────────
    print(f"  [6A] Optimizando {len(fotos_orig)} fotos → con_fondo/ ...")
    dir_con_fondo.mkdir(parents=True, exist_ok=True)
    for foto in fotos_orig:
        dest = dir_con_fondo / foto.name
        try:
            if usar_cv2:
                gf._optimizar_con_cv2(foto, dest)
            else:
                gf._optimizar_solo_pillow(foto, dest)
        except Exception as e:
            result["errores"].append(f"6A {foto.name}: {e}")
    result["con_fondo"] = contar(dir_con_fondo)

    # ── 7A: Texto en con_fondo/ → con_texto/ (*_confondo.jpg) ────────────────
    print(f"  [7A] Agregando texto → con_texto/ (*_confondo.jpg) ...")
    dir_con_texto.mkdir(parents=True, exist_ok=True)
    for foto in gf.listar_fotos(dir_con_fondo):
        dest = dir_con_texto / f"{foto.stem}_confondo.jpg"
        try:
            gf._agregar_texto_a_foto(foto, dest, precio, specs)
        except Exception as e:
            result["errores"].append(f"7A {foto.name}: {e}")
    result["confondo_txt"] = contar(dir_con_texto)

    # ── 4: rembg originales/ → procesadas/ ────────────────────────────────────
    print(f"  [4]  rembg {len(fotos_orig)} fotos → procesadas/ ...")
    dir_procesadas.mkdir(parents=True, exist_ok=True)
    for foto in fotos_orig:
        dest = dir_procesadas / foto.name
        try:
            t0 = time.time()
            if usar_rembg:
                img_rgba = gf._remover_fondo_rembg(foto)
            else:
                img_rgba = gf._remover_fondo_pillow(foto)
            img_rgb = gf._componer_fondo_blanco(img_rgba)
            img_rgb.save(dest, "JPEG", quality=93)
            elapsed = time.time() - t0
            print(f"    {foto.name} → procesadas/{dest.name}  ({elapsed:.1f}s)")
        except Exception as e:
            result["errores"].append(f"4 {foto.name}: {e}")
    result["procesadas"] = contar(dir_procesadas)

    # ── 9: Centrar y normalizar procesadas/ (in-place) ────────────────────────
    print(f"  [9]  Centrando {result['procesadas']} fotos en procesadas/ ...")
    for foto in gf.listar_fotos(dir_procesadas):
        tmp = foto.with_suffix(".tmp.jpg")
        try:
            gf._centrar_producto(foto, tmp)
            tmp.replace(foto)
        except Exception as e:
            if tmp.exists():
                tmp.unlink()
            result["errores"].append(f"9 {foto.name}: {e}")

    # ── 6B: Optimizar procesadas/ → listas_gemini/ ────────────────────────────
    print(f"  [6B] Optimizando procesadas/ → listas_gemini/ ...")
    dir_listas.mkdir(parents=True, exist_ok=True)
    for foto in gf.listar_fotos(dir_procesadas):
        dest = dir_listas / foto.name
        try:
            if usar_cv2:
                gf._optimizar_con_cv2(foto, dest)
            else:
                gf._optimizar_solo_pillow(foto, dest)
        except Exception as e:
            result["errores"].append(f"6B {foto.name}: {e}")
    result["listas"] = contar(dir_listas)

    # ── 7B: Texto en listas_gemini/ → con_texto/ (*_sinfondo.jpg) ────────────
    print(f"  [7B] Agregando texto → con_texto/ (*_sinfondo.jpg) ...")
    for foto in gf.listar_fotos(dir_listas):
        dest = dir_con_texto / f"{foto.stem}_sinfondo.jpg"
        try:
            gf._agregar_texto_a_foto(foto, dest, precio, specs)
        except Exception as e:
            result["errores"].append(f"7B {foto.name}: {e}")
    result["sinfondo_txt"] = contar(dir_con_texto)

    return result


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    skus = json.loads(CATALOGO.read_text())
    catalogo = []
    for sku in skus:
        path = PRODUCTOS_BASE / sku / "producto.json"
        if path.exists():
            catalogo.append(json.loads(path.read_text()))
        else:
            catalogo.append({"sku": sku})

    print("\n" + "═"*60)
    print("  TEST PIPELINE gestionar_fotos.py")
    print("═"*60)
    print(f"  CV2 disponible:   {gf._cv2_disponible()}")
    print(f"  rembg disponible: {gf._rembg_disponible()}")
    print("═"*60 + "\n")

    resultados = []
    t_total = time.time()

    for entrada in catalogo:
        sku = entrada["sku"]
        dir_prod = PRODUCTOS_BASE / sku
        dir_orig = dir_prod / "fotos" / "originales"

        if not dir_orig.exists() or not gf.listar_fotos(dir_orig):
            print(f"[SKIP] {sku} — sin fotos en originales/\n")
            resultados.append({
                "sku": sku, "originales": 0, "con_fondo": 0,
                "confondo_txt": 0, "procesadas": 0, "listas": 0,
                "sinfondo_txt": 0, "errores": ["sin fotos"],
            })
            continue

        # Leer precio y specs del producto.json
        prod_json_path = dir_prod / "producto.json"
        precio = "$0"
        specs  = ""
        if prod_json_path.exists():
            with open(prod_json_path) as f:
                pj = json.load(f)
            precio_num = pj.get("precio_costo", 0)
            precio = f"${precio_num:,.0f}".replace(",", ".")
            variante = pj.get("variante", {})
            partes = [v for v in [variante.get("color"), variante.get("talle")] if v]
            specs = " · ".join(partes)

        print(f"{'─'*60}")
        print(f"  SKU: {sku}  |  Precio: {precio}  |  Specs: {specs or '—'}")
        print(f"{'─'*60}")

        t0 = time.time()
        try:
            res = run_pipeline(sku, precio, specs)
        except Exception as e:
            print(f"  [ERROR FATAL] {e}")
            traceback.print_exc()
            res = {"sku": sku, "originales": contar(dir_orig), "con_fondo": 0,
                   "confondo_txt": 0, "procesadas": 0, "listas": 0,
                   "sinfondo_txt": 0, "errores": [f"fatal: {e}"]}
        elapsed = time.time() - t0
        res["tiempo"] = elapsed
        resultados.append(res)
        print(f"\n  Tiempo: {elapsed:.1f}s\n")

    # ── Tabla resumen ──────────────────────────────────────────────────────────
    print("\n" + "═"*80)
    print("  RESUMEN FINAL")
    print("═"*80)
    hdr = f"{'SKU':<20} {'orig':>5} {'conf':>5} {'7A':>5} {'proc':>5} {'list':>5} {'7B':>5} {'t(s)':>6}  Errores"
    print(hdr)
    print("─"*80)
    for r in resultados:
        errores_str = ", ".join(r["errores"]) if r["errores"] else "—"
        t = r.get("tiempo", 0)
        print(
            f"{r['sku']:<20} "
            f"{r['originales']:>5} "
            f"{r['con_fondo']:>5} "
            f"{r['confondo_txt']:>5} "
            f"{r['procesadas']:>5} "
            f"{r['listas']:>5} "
            f"{r['sinfondo_txt']:>5} "
            f"{t:>6.1f}  "
            f"{errores_str}"
        )
    print("─"*80)
    print(f"\n  Tiempo total: {time.time() - t_total:.1f}s")
    print()

    # Código de salida no-cero si hubo errores
    total_errores = sum(len(r["errores"]) for r in resultados)
    if total_errores:
        print(f"  ⚠  {total_errores} error(es) encontrado(s).")
        sys.exit(1)
    else:
        print("  ✓ Sin errores.")
        sys.exit(0)


if __name__ == "__main__":
    main()
