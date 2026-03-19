"""Capa de datos para bundles (combos de productos)."""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from app.config import BUNDLES_DIR, KB_ROOT, MARGEN
from app.utils.file_helpers import load_json, save_json, slugify

logger = logging.getLogger(__name__)


@dataclass
class BundleItem:
    """Un producto dentro de un bundle con su cantidad."""
    sku: str
    cantidad: int = 1


@dataclass
class Bundle:
    """Representación de un bundle/combo de productos."""

    nombre: str
    slug: str
    productos: list[BundleItem] = field(default_factory=list)
    precio_costo_total: float = 0.0
    precio_venta_sugerido: int = 0
    precio_venta_final: int = 0
    fotos: dict[str, Any] = field(default_factory=lambda: {"portada": "", "apoyo": []})
    creado_en: str = ""

    @property
    def json_path(self) -> Path:
        return BUNDLES_DIR / f"{self.slug}.json"

    @classmethod
    def from_json(cls, data: dict) -> "Bundle":
        items = [
            BundleItem(sku=p["sku"], cantidad=p.get("cantidad", 1))
            for p in data.get("productos", [])
        ]
        return cls(
            nombre=data.get("nombre", ""),
            slug=data.get("slug", ""),
            productos=items,
            precio_costo_total=data.get("precio_costo_total", 0.0),
            precio_venta_sugerido=data.get("precio_venta_sugerido", 0),
            precio_venta_final=data.get("precio_venta_final", 0),
            fotos=data.get("fotos", {"portada": "", "apoyo": []}),
            creado_en=data.get("creado_en", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "nombre": self.nombre,
            "slug": self.slug,
            "productos": [
                {"sku": item.sku, "cantidad": item.cantidad}
                for item in self.productos
            ],
            "precio_costo_total": self.precio_costo_total,
            "precio_venta_sugerido": self.precio_venta_sugerido,
            "precio_venta_final": self.precio_venta_final,
            "fotos": self.fotos,
            "creado_en": self.creado_en,
        }

    def save(self) -> None:
        BUNDLES_DIR.mkdir(parents=True, exist_ok=True)
        save_json(self.json_path, self.to_dict())
        logger.info("Bundle guardado: %s", self.slug)

    @classmethod
    def load(cls, slug: str) -> "Bundle | None":
        path = BUNDLES_DIR / f"{slug}.json"
        if not path.exists():
            return None
        try:
            return cls.from_json(load_json(path))
        except (json.JSONDecodeError, KeyError) as e:
            logger.error("Error cargando bundle %s: %s", slug, e)
            return None


class BundleManager:
    """Gestiona la colección de bundles."""

    def __init__(self) -> None:
        self._bundles: dict[str, Bundle] = {}
        self.reload()

    def reload(self) -> None:
        self._bundles.clear()
        if not BUNDLES_DIR.exists():
            return
        for path in sorted(BUNDLES_DIR.glob("*.json")):
            try:
                data = load_json(path)
                bundle = Bundle.from_json(data)
                self._bundles[bundle.slug] = bundle
            except Exception as e:
                logger.error("Error cargando %s: %s", path.name, e)

    @property
    def bundles(self) -> list[Bundle]:
        return list(self._bundles.values())

    def get(self, slug: str) -> Bundle | None:
        return self._bundles.get(slug)

    def count(self) -> int:
        return len(self._bundles)

    def crear_bundle(
        self,
        nombre: str,
        items: list[tuple[str, int, float]],
        precio_final: int,
        portada: str = "",
        apoyo: list[str] | None = None,
    ) -> Bundle:
        """Crea un bundle nuevo. items = [(sku, cantidad, precio_costo_unitario), ...]"""
        slug = slugify(nombre)
        costo_total = sum(precio * cant for _, cant, precio in items)
        sugerido = round(costo_total * MARGEN)

        bundle = Bundle(
            nombre=nombre,
            slug=slug,
            productos=[BundleItem(sku=sku, cantidad=cant) for sku, cant, _ in items],
            precio_costo_total=costo_total,
            precio_venta_sugerido=sugerido,
            precio_venta_final=precio_final,
            fotos={"portada": portada, "apoyo": apoyo or []},
            creado_en=datetime.now().isoformat(),
        )
        bundle.save()
        self._bundles[slug] = bundle
        return bundle
