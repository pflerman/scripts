"""Capa de datos para listings/drafts de publicación."""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from app.config import DRAFTS_DIR, KB_ROOT
from app.utils.file_helpers import load_json, save_json

logger = logging.getLogger(__name__)


@dataclass
class Listing:
    """Representación de un draft de listing para MercadoLibre."""

    slug: str
    bundle: str = ""
    titulo: str = ""
    descripcion: str = ""
    precio: int = 0
    stock: int = 0
    fotos: dict[str, Any] = field(default_factory=lambda: {"portada": "", "apoyo": []})
    estado: str = "draft"
    creado_en: str = ""

    @property
    def json_path(self) -> Path:
        return DRAFTS_DIR / f"{self.slug}.json"

    @classmethod
    def from_json(cls, data: dict) -> "Listing":
        return cls(
            slug=data.get("slug", ""),
            bundle=data.get("bundle", ""),
            titulo=data.get("titulo", ""),
            descripcion=data.get("descripcion", ""),
            precio=data.get("precio", 0),
            stock=data.get("stock", 0),
            fotos=data.get("fotos", {"portada": "", "apoyo": []}),
            estado=data.get("estado", "draft"),
            creado_en=data.get("creado_en", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "slug": self.slug,
            "bundle": self.bundle,
            "titulo": self.titulo,
            "descripcion": self.descripcion,
            "precio": self.precio,
            "stock": self.stock,
            "fotos": self.fotos,
            "estado": self.estado,
            "creado_en": self.creado_en,
        }

    def save(self) -> None:
        DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
        save_json(self.json_path, self.to_dict())
        logger.info("Listing guardado: %s", self.slug)

    @classmethod
    def load(cls, slug: str) -> "Listing | None":
        path = DRAFTS_DIR / f"{slug}.json"
        if not path.exists():
            return None
        try:
            return cls.from_json(load_json(path))
        except (json.JSONDecodeError, KeyError) as e:
            logger.error("Error cargando listing %s: %s", slug, e)
            return None


class ListingManager:
    """Gestiona la colección de listing drafts."""

    def __init__(self) -> None:
        self._listings: dict[str, Listing] = {}
        self.reload()

    def reload(self) -> None:
        self._listings.clear()
        if not DRAFTS_DIR.exists():
            return
        for path in sorted(DRAFTS_DIR.glob("*.json")):
            try:
                data = load_json(path)
                listing = Listing.from_json(data)
                self._listings[listing.slug] = listing
            except Exception as e:
                logger.error("Error cargando %s: %s", path.name, e)

    @property
    def listings(self) -> list[Listing]:
        return list(self._listings.values())

    def get(self, slug: str) -> Listing | None:
        return self._listings.get(slug)

    def count(self) -> int:
        return len(self._listings)

    def slugs_con_listing(self) -> set[str]:
        """Retorna set de bundle slugs que ya tienen listing."""
        return {listing.slug for listing in self._listings.values()}
