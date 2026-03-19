"""Utilidades para manejo de archivos y rutas."""

import json
import re
import unicodedata
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    """Carga un archivo JSON y retorna su contenido."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Any) -> None:
    """Guarda datos como JSON con indentación y sin escapar unicode."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def slugify(texto: str) -> str:
    """Convierte texto a slug URL-safe (lowercase, sin acentos, hyphens)."""
    texto = texto.lower().strip()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"[^\w\s-]", "", texto)
    texto = re.sub(r"[\s_]+", "-", texto)
    return texto


def contar_fotos(carpeta: Path) -> int:
    """Cuenta archivos de imagen en una carpeta."""
    from app.config import IMG_EXTENSIONS
    if not carpeta.exists():
        return 0
    return sum(1 for f in carpeta.iterdir() if f.suffix.lower() in IMG_EXTENSIONS)
