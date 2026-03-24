"""Scraper de publicaciones de MercadoLibre.

Resolución de URLs, obtención de datos de ítems vía API (con fallback a
scraping web), descarga de fotos en máxima resolución.

Tokens: usa palishopping como principal, cajasordenadoras como fallback
para leer ítems de competidores cuando ML devuelve 403 (PolicyAgent).
"""

import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from app.services.ml_auth import get_palishopping_token, get_reader_token

logger = logging.getLogger(__name__)

ML_BASE_URL = "https://api.mercadolibre.com"
ML_COOKIES_PATH = Path.home() / ".ml_cookies.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-AR,es;q=0.9",
}

# Mapeo domain_id → category_id para catalog products
DOMAIN_TO_CATEGORY = {
    "MLA-HANGING_CLOSET_ORGANIZERS": "MLA414192",
    "MLA-AIRTIGHT_AND_VACUUM_BAGS":  "MLA377242",
    "MLA-CLOTHES_HANGERS":           "MLA388187",
    "MLA-SHOE_RACKS_AND_CABINETS":   "MLA74590",
    "MLA-CLEANING_MOPS":             "MLA127692",
    "MLA-MAKEUP_TRAIN_CASES":        "MLA389336",
    "MLA-FIRST_AID_KITS":            "MLA9475",
}


# ── Helpers HTTP ──────────────────────────────────────────────────────────────

def _ml_get(path: str, token: str | None = None) -> dict:
    """GET a la API de ML con token de autorización."""
    if token is None:
        token = get_palishopping_token()
    req = urllib.request.Request(
        f"{ML_BASE_URL}{path}",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def _extract_mla_from_string(text: str) -> str | None:
    """Extrae el primer MLA\\d+ de un string y lo normaliza (sin guion)."""
    m = re.search(r"(MLA-?\d+)", text.upper())
    if m:
        return m.group(1).replace("-", "")
    return None


def _url_to_hd(url: str) -> str:
    """Convierte una URL de foto ML a resolución 1200px (-F.jpg)."""
    return re.sub(r"-[A-Z]\.(?:jpg|jpeg|png|webp)", "-F.jpg", url)


# ── Cookies Playwright ────────────────────────────────────────────────────────

def _load_ml_cookies() -> list[dict] | None:
    """Lee ~/.ml_cookies.json (formato Cookie-Editor) y lo convierte a Playwright."""
    if not ML_COOKIES_PATH.exists():
        return None

    try:
        raw = json.loads(ML_COOKIES_PATH.read_text())
    except Exception as e:
        logger.warning("No se pudo leer %s: %s", ML_COOKIES_PATH, e)
        return None

    samesite_map = {
        "no_restriction": "None",
        "lax": "Lax",
        "strict": "Strict",
        "unspecified": "Lax",
    }

    cookies: list[dict] = []
    for c in raw:
        domain = c.get("domain", "")
        if "mercadolibre" not in domain and "mlstatic" not in domain:
            continue
        if c.get("session", False) or "expirationDate" not in c:
            continue

        cookies.append({
            "name": c["name"],
            "value": c["value"],
            "domain": domain,
            "path": c.get("path", "/"),
            "secure": c.get("secure", False),
            "httpOnly": c.get("httpOnly", False),
            "sameSite": samesite_map.get(c.get("sameSite", "lax").lower(), "Lax"),
            "expires": int(c["expirationDate"]),
        })

    logger.info("Cookies ML: %d persistentes cargadas", len(cookies))
    return cookies if cookies else None


# ── Resolución de URLs ────────────────────────────────────────────────────────

def _resolve_mlau_playwright(url: str) -> str | None:
    """Resuelve una URL /up/MLAU... con Playwright + cookies."""
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

    cookies = _load_ml_cookies()
    if not cookies:
        logger.warning("Sin cookies ML, Playwright no podrá resolver la URL")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-first-run"],
        )
        context = browser.new_context(
            locale="es-AR",
            timezone_id="America/Argentina/Buenos_Aires",
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1366, "height": 768},
        )
        context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        if cookies:
            try:
                context.add_cookies(cookies)
            except Exception as e:
                logger.warning("Error al cargar cookies: %s", e)

        page = context.new_page()

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(4000)

            current_url = page.url

            if "account-verification" in current_url or "login" in current_url:
                logger.warning("Cookies ML expiradas o inválidas")
                return None

            mla = _extract_mla_from_string(current_url)

            if not mla:
                html = page.content()
                all_mlas = re.findall(r"MLA\d+", html.upper())
                item_mlas = [m for m in dict.fromkeys(all_mlas) if 7 <= len(m) - 3 <= 10]
                mla = item_mlas[0] if item_mlas else None

            if mla:
                logger.info("Playwright resolvió: %s", mla)
            return mla

        except PWTimeout:
            logger.warning("Playwright timeout")
        except Exception as e:
            logger.warning("Playwright error: %s", e)
        finally:
            browser.close()

    return None


def _resolve_mlau_api(url: str) -> str | None:
    """Fallback: busca catalog product via /products/search."""
    m = re.search(r"mercadolibre\.com\.ar/([^/?#]+)/up/", url)
    if not m:
        return None

    keywords = m.group(1).replace("-", " ")
    logger.info("API fallback: buscando '%s'...", keywords[:55])

    try:
        data = _ml_get(
            f"/products/search?site_id=MLA&q={urllib.parse.quote(keywords)}&limit=10"
        )
        for r in data.get("results", []):
            if r.get("status") == "active":
                logger.info("Catalog product: %s - %s", r["id"], r.get("name", "")[:60])
                return r["id"]
    except Exception as e:
        logger.warning("API catalog search falló: %s", e)

    return None


def resolve_url(url: str) -> str | None:
    """Resuelve una URL de ML a un item_id o catalog_product_id.

    Flujo:
      1. Regex directo (MLA visible en URL)
      2. requests + redirect
      3. Playwright + cookies
      4. API /products/search (fallback)

    Args:
        url: URL de MercadoLibre (cualquier formato).

    Returns:
        MLA ID normalizado (sin guion) o None.
    """
    # Caso 1: MLA visible
    mla = _extract_mla_from_string(url)
    if mla:
        return mla

    # Caso 2: URL /up/MLAU...
    if "/up/" in url or "MLAU" in url.upper():
        logger.info("URL universal detectada, resolviendo...")

        # Intento A: requests + redirects
        session = requests.Session()
        session.headers.update(HEADERS)
        try:
            resp = session.get(url, allow_redirects=True, timeout=15)
            mla = _extract_mla_from_string(resp.url)
            if mla:
                logger.info("Resuelto via requests: %s", mla)
                return mla
        except Exception:
            pass

        # Intento B: Playwright
        mla = _resolve_mlau_playwright(url)
        if mla:
            return mla

        # Intento C: API fallback
        return _resolve_mlau_api(url)

    return None


# ── Obtener datos del ítem ────────────────────────────────────────────────────

def _fotos_desde_catalog_product(prod: dict) -> list[str]:
    """Extrae URLs de fotos en max resolución desde GET /products/{id}."""
    foto_urls: list[str] = []
    seen: set[str] = set()

    def _add(url: str) -> None:
        if url and url not in seen:
            seen.add(url)
            foto_urls.append(_url_to_hd(url))

    for pic in prod.get("pictures", []):
        _add(pic.get("secure_url") or pic.get("url", ""))

    for picker in prod.get("pickers", []):
        for p in picker.get("products", []):
            _add(p.get("thumbnail", ""))
            pid = p.get("picture_id", "")
            if pid:
                _add(f"https://http2.mlstatic.com/D_NQ_NP_{pid}-F.jpg")

    return foto_urls


def _get_catalog_product_data(catalog_id: str) -> dict:
    """Datos de un catalog product via GET /products/{id}."""
    prod = _ml_get(f"/products/{catalog_id}")

    titulo = prod.get("name", "") or prod.get("family_name", "")
    domain_id = prod.get("domain_id", "")
    category_id = DOMAIN_TO_CATEGORY.get(domain_id, "MLA414192")
    foto_urls = _fotos_desde_catalog_product(prod)

    logger.warning("Fuente: catalog product %s. Precio no disponible.", catalog_id)
    return {
        "titulo": titulo,
        "precio": 0,
        "category_id": category_id,
        "foto_urls": foto_urls,
        "descripcion": "",
        "permalink": prod.get("permalink", ""),
        "_es_catalog_product": True,
    }


def _scrape_item_web(url: str) -> dict:
    """Scraping completo del ítem desde la página web de ML (fallback)."""
    session = requests.Session()
    session.headers.update(HEADERS)
    logger.info("Fallback: scraping web de %s...", url[:80])

    resp = session.get(url, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    # Título
    titulo = ""
    h1 = soup.select_one("h1.ui-pdp-title")
    if h1:
        titulo = h1.get_text(strip=True)

    # Precio
    precio = 0.0
    price_el = soup.select_one("span.andes-money-amount__fraction")
    if price_el:
        precio_str = price_el.get_text(strip=True).replace(".", "").replace(",", ".")
        try:
            precio = float(precio_str)
        except ValueError:
            pass

    # Fotos
    foto_urls: list[str] = []
    seen: set[str] = set()
    for img in soup.select(
        "figure.ui-pdp-gallery__figure img, "
        ".ui-pdp-image.ui-pdp-gallery__figure__image"
    ):
        for attr in ("data-zoom", "src"):
            src = img.get(attr, "")
            if src and src.startswith("http") and src not in seen:
                seen.add(src)
                foto_urls.append(_url_to_hd(src))
                break

    if not foto_urls:
        for img in soup.select("img.ui-pdp-image"):
            for attr in ("data-zoom", "data-src", "src"):
                src = img.get(attr, "")
                if src and src.startswith("http") and "mercadolibre" in src and src not in seen:
                    seen.add(src)
                    foto_urls.append(_url_to_hd(src))
                    break

    if not foto_urls:
        for script in soup.find_all("script", {"type": "application/json"}):
            try:
                data = json.loads(script.string or "")
                urls = re.findall(r'https://[^"\']+?-O\.jpg', str(data))
                for u in urls:
                    if u not in seen:
                        seen.add(u)
                        foto_urls.append(u)
            except Exception:
                pass

    # Category ID
    category_id = "MLA414192"
    m = re.search(r'"category_id"\s*:\s*"(MLA\d+)"', resp.text)
    if m:
        category_id = m.group(1)

    return {
        "titulo": titulo,
        "precio": precio,
        "category_id": category_id,
        "foto_urls": foto_urls,
        "descripcion": "",
        "permalink": url,
    }


def scrape_listing(url: str) -> dict:
    """Obtiene todos los datos de una publicación de ML.

    Flujo:
      1. Resolver URL → item_id
      2. GET /items/{id} con token palishopping
      3. Fallback: reader token (cajasordenadoras) si 403
      4. Fallback: scraping web si ambos tokens fallan
      5. Fallback: GET /products/{id} si es catalog product (404 en /items)

    Args:
        url: URL de MercadoLibre (cualquier formato).

    Returns:
        Dict con: titulo, precio, category_id, foto_urls, descripcion, permalink,
        y opcionalmente _es_catalog_product.

    Raises:
        RuntimeError: Si no se pudo resolver la URL.
    """
    item_id = resolve_url(url)
    if not item_id:
        raise RuntimeError(f"No se pudo extraer item_id de: {url}")

    logger.info("Item ID: %s", item_id)

    read_token = None
    try:
        item = _ml_get(f"/items/{item_id}")
        if item.get("error") == "not_found":
            raise urllib.error.HTTPError(None, 404, "not found", {}, None)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            logger.info("Item no encontrado, intentando como catalog product...")
            return _get_catalog_product_data(item_id)
        if e.code == 403:
            reader_token = get_reader_token()
            if reader_token:
                logger.info("403 con principal, reintentando con reader...")
                try:
                    item = _ml_get(f"/items/{item_id}", token=reader_token)
                    if item.get("error") == "not_found":
                        return _get_catalog_product_data(item_id)
                    read_token = reader_token
                except urllib.error.HTTPError as e2:
                    if e2.code == 404:
                        return _get_catalog_product_data(item_id)
                    logger.warning("Ambos tokens fallaron, scraping web...")
                    fallback_url = url or f"https://articulo.mercadolibre.com.ar/{item_id.replace('MLA', 'MLA-')}"
                    return _scrape_item_web(fallback_url)
            else:
                logger.warning("Sin reader token, scraping web...")
                fallback_url = url or f"https://articulo.mercadolibre.com.ar/{item_id.replace('MLA', 'MLA-')}"
                return _scrape_item_web(fallback_url)
        else:
            raise

    # Datos del ítem
    titulo = item.get("title", "")
    precio = item.get("price", 0)
    category_id = item.get("category_id", "MLA414192")
    permalink = item.get("permalink", "")

    foto_urls = []
    for pic in item.get("pictures", []):
        pic_url = pic.get("secure_url") or pic.get("url", "")
        if pic_url:
            foto_urls.append(_url_to_hd(pic_url))

    # Descripción
    descripcion = ""
    try:
        desc_data = _ml_get(f"/items/{item_id}/description", token=read_token)
        descripcion = desc_data.get("plain_text", "") or desc_data.get("text", "")
    except Exception:
        pass

    # Fallback: scraping si no hay fotos via API
    if not foto_urls and permalink:
        foto_urls = _scrape_photos(permalink)

    return {
        "titulo": titulo,
        "precio": precio,
        "category_id": category_id,
        "foto_urls": foto_urls,
        "descripcion": descripcion,
        "permalink": permalink,
    }


def _scrape_photos(url: str) -> list[str]:
    """Fallback: scrapea fotos desde la página web."""
    session = requests.Session()
    session.headers.update(HEADERS)
    try:
        resp = session.get(url, timeout=15)
        resp.raise_for_status()
    except requests.RequestException:
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    photo_urls: list[str] = []
    seen: set[str] = set()

    for img in soup.select(
        "figure.ui-pdp-gallery__figure img, "
        ".ui-pdp-image.ui-pdp-gallery__figure__image"
    ):
        for attr in ("data-zoom", "src"):
            src = img.get(attr, "")
            if src and src.startswith("http") and src not in seen:
                seen.add(src)
                photo_urls.append(_url_to_hd(src))
                break

    return photo_urls


def download_photos(foto_urls: list[str], dest_dir: Path,
                    callback=None) -> list[Path]:
    """Descarga fotos a dest_dir en máxima resolución.

    Args:
        foto_urls: Lista de URLs de fotos.
        dest_dir: Carpeta destino.
        callback: Función callback(msg) para reportar progreso.

    Returns:
        Lista de paths a fotos descargadas.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update(HEADERS)
    downloaded: list[Path] = []

    for i, url in enumerate(foto_urls, start=1):
        dest = dest_dir / f"foto_{i}.jpg"
        msg = f"Descargando foto {i}/{len(foto_urls)}..."
        if callback:
            callback(msg)
        try:
            resp = session.get(url, timeout=20, stream=True)
            resp.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            downloaded.append(dest)
            logger.info("Foto %d descargada: %s", i, dest)
        except Exception as e:
            logger.warning("No se pudo descargar foto %d: %s", i, e)

    return downloaded
