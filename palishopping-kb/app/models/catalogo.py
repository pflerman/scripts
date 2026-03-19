"""Capa de datos para catálogo y productos."""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from app.config import (
    CATALOGO_PATH,
    MODELOS_PATH,
    PRODUCT_SUBDIRS,
    PRODUCTOS_BASE,
    KB_ROOT,
)
from app.utils.file_helpers import load_json, save_json

logger = logging.getLogger(__name__)


@dataclass
class Producto:
    """Representación de un producto base con todos sus campos."""

    sku: str
    nombre: str
    tipo: str
    variante: dict[str, str] = field(default_factory=dict)
    dimensiones: dict[str, float] | None = None
    proveedor: str = ""
    precio_fob_usd: float | None = None
    factor_nacionalizacion: float | None = None
    tipo_cambio_usado: float | None = None
    precio_costo: float = 0.0
    stock: int = 0
    descripcion: str = ""
    titulo_ml: str = ""
    titulo_web: str = ""
    palabras_clave: list[str] = field(default_factory=list)
    ml_categoria_id: str = ""
    listings: list[str] = field(default_factory=list)
    notas: str = ""
    fecha_creacion: str = ""
    ultima_actualizacion: str = ""
    fotos_originales_ref: list[dict] | None = None

    @property
    def directorio(self) -> Path:
        """Ruta al directorio del producto."""
        return PRODUCTOS_BASE / self.sku

    @property
    def json_path(self) -> Path:
        """Ruta al producto.json."""
        return self.directorio / "producto.json"

    @property
    def color(self) -> str:
        return self.variante.get("color", "")

    @property
    def talle(self) -> str:
        return self.variante.get("talle", "")

    @property
    def modelo(self) -> str:
        return self.variante.get("modelo", "")

    @property
    def tiene_fotos(self) -> bool:
        """Verifica si tiene al menos una foto en originales/."""
        orig = self.directorio / "fotos" / "originales"
        if not orig.exists():
            return False
        from app.config import IMG_EXTENSIONS
        return any(f.suffix.lower() in IMG_EXTENSIONS for f in orig.iterdir())

    @classmethod
    def from_json(cls, data: dict) -> "Producto":
        """Crea un Producto desde un dict (producto.json)."""
        return cls(
            sku=data.get("sku", ""),
            nombre=data.get("nombre", ""),
            tipo=data.get("tipo", ""),
            variante=data.get("variante", {}),
            dimensiones=data.get("dimensiones"),
            proveedor=data.get("proveedor", ""),
            precio_fob_usd=data.get("precio_fob_usd"),
            factor_nacionalizacion=data.get("factor_nacionalizacion"),
            tipo_cambio_usado=data.get("tipo_cambio_usado"),
            precio_costo=data.get("precio_costo", 0.0),
            stock=data.get("stock", 0),
            descripcion=data.get("descripcion", ""),
            titulo_ml=data.get("titulo_ml", ""),
            titulo_web=data.get("titulo_web", ""),
            palabras_clave=data.get("palabras_clave", []),
            ml_categoria_id=data.get("ml_categoria_id", ""),
            listings=data.get("listings", []),
            notas=data.get("notas", ""),
            fecha_creacion=data.get("fecha_creacion", ""),
            ultima_actualizacion=data.get("ultima_actualizacion", ""),
            fotos_originales_ref=data.get("fotos_originales_ref"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serializa a dict compatible con el formato JSON existente."""
        data: dict[str, Any] = {
            "sku": self.sku,
            "nombre": self.nombre,
            "tipo": self.tipo,
            "variante": self.variante,
        }
        if self.dimensiones:
            data["dimensiones"] = self.dimensiones
        data["proveedor"] = self.proveedor
        if self.proveedor == "andres" and self.precio_fob_usd is not None:
            data["precio_fob_usd"] = self.precio_fob_usd
            data["factor_nacionalizacion"] = self.factor_nacionalizacion
            data["tipo_cambio_usado"] = self.tipo_cambio_usado
        data["precio_costo"] = self.precio_costo
        data["stock"] = self.stock
        data["descripcion"] = self.descripcion
        data["titulo_ml"] = self.titulo_ml
        data["titulo_web"] = self.titulo_web
        data["palabras_clave"] = self.palabras_clave
        data["ml_categoria_id"] = self.ml_categoria_id
        data["listings"] = self.listings
        data["notas"] = self.notas
        data["fecha_creacion"] = self.fecha_creacion
        data["ultima_actualizacion"] = self.ultima_actualizacion
        if self.fotos_originales_ref:
            data["fotos_originales_ref"] = self.fotos_originales_ref
        return data

    def save(self) -> None:
        """Guarda el producto a disco actualizando el timestamp."""
        self.ultima_actualizacion = datetime.now().isoformat(timespec="seconds")
        save_json(self.json_path, self.to_dict())
        logger.info("Producto %s guardado", self.sku)

    @classmethod
    def load(cls, sku: str) -> "Producto | None":
        """Carga un producto desde disco por SKU."""
        path = PRODUCTOS_BASE / sku / "producto.json"
        if not path.exists():
            logger.warning("producto.json no encontrado para SKU %s", sku)
            return None
        try:
            data = load_json(path)
            return cls.from_json(data)
        except (json.JSONDecodeError, KeyError) as e:
            logger.error("Error cargando %s: %s", sku, e)
            return None


class Catalogo:
    """Gestiona el catálogo de productos (catalogo.json + producto.json individuales)."""

    def __init__(self) -> None:
        self._skus: list[str] = []
        self._productos: dict[str, Producto] = {}
        self._modelos: dict[str, str] = {}
        self.reload()

    def reload(self) -> None:
        """Recarga catálogo y modelos desde disco."""
        self._skus = self._load_skus()
        self._productos.clear()
        for sku in self._skus:
            prod = Producto.load(sku)
            if prod:
                self._productos[sku] = prod
        self._modelos = self._load_modelos()
        logger.info("Catálogo cargado: %d SKUs, %d productos válidos",
                     len(self._skus), len(self._productos))

    @staticmethod
    def _load_skus() -> list[str]:
        if CATALOGO_PATH.exists():
            try:
                return load_json(CATALOGO_PATH)
            except (json.JSONDecodeError, TypeError):
                return []
        return []

    @staticmethod
    def _load_modelos() -> dict[str, str]:
        if MODELOS_PATH.exists():
            try:
                items = load_json(MODELOS_PATH)
                return {m["codigo"]: m["nombre"] for m in items}
            except (json.JSONDecodeError, KeyError):
                return {}
        return {}

    @property
    def skus(self) -> list[str]:
        return list(self._skus)

    @property
    def productos(self) -> list[Producto]:
        """Retorna todos los productos válidos en orden del catálogo."""
        return [self._productos[s] for s in self._skus if s in self._productos]

    @property
    def modelos(self) -> dict[str, str]:
        """Mapeo codigo → nombre de modelos."""
        return dict(self._modelos)

    def get(self, sku: str) -> Producto | None:
        """Obtiene un producto por SKU."""
        return self._productos.get(sku)

    def existe(self, sku: str) -> bool:
        """Verifica si un SKU ya existe."""
        return (PRODUCTOS_BASE / sku).exists()

    def crear_producto(
        self,
        sku: str,
        nombre: str,
        tipo: str,
        modelo: str,
        color: str,
        talle: str,
        proveedor: str,
        precio_costo: float,
        stock: int = 0,
        notas: str = "",
        dimensiones: dict[str, float] | None = None,
        precio_fob_usd: float | None = None,
        factor_nacionalizacion: float | None = None,
        tipo_cambio_usado: float | None = None,
    ) -> Producto:
        """Crea un producto nuevo: estructura de carpetas, JSON, y registro en catálogo."""
        now = datetime.now().isoformat(timespec="seconds")
        producto_dir = PRODUCTOS_BASE / sku

        # Crear estructura de carpetas
        for subdir in PRODUCT_SUBDIRS:
            (producto_dir / subdir).mkdir(parents=True, exist_ok=True)

        producto = Producto(
            sku=sku,
            nombre=nombre,
            tipo=tipo,
            variante={"modelo": modelo, "color": color, "talle": talle},
            dimensiones=dimensiones,
            proveedor=proveedor,
            precio_fob_usd=precio_fob_usd,
            factor_nacionalizacion=factor_nacionalizacion,
            tipo_cambio_usado=tipo_cambio_usado,
            precio_costo=precio_costo,
            stock=stock,
            notas=notas,
            fecha_creacion=now,
            ultima_actualizacion=now,
        )
        producto.save()

        # Crear archivos de inteligencia vacíos
        intel_dir = producto_dir / "inteligencia"
        for fname in ("reviews.json", "preguntas.json"):
            fpath = intel_dir / fname
            if not fpath.exists():
                save_json(fpath, [])

        # Registrar en catálogo
        self._skus.append(sku)
        self._productos[sku] = producto
        self._save_skus()

        logger.info("Producto creado: %s", sku)
        return producto

    def actualizar_producto(self, sku: str, **campos: Any) -> bool:
        """Actualiza campos arbitrarios de un producto y guarda a disco."""
        prod = self.get(sku)
        if not prod:
            return False
        for key, value in campos.items():
            if key == "variante" and isinstance(value, dict):
                prod.variante.update(value)
            elif hasattr(prod, key):
                setattr(prod, key, value)
        prod.save()
        logger.info("Producto %s actualizado: %s", sku, list(campos.keys()))
        return True

    def actualizar_precio(self, sku: str, nuevo_precio: float) -> bool:
        """Actualiza el precio de costo de un producto."""
        prod = self.get(sku)
        if not prod:
            return False
        prod.precio_costo = nuevo_precio
        prod.save()
        return True

    def actualizar_stock(self, sku: str, nuevo_stock: int) -> bool:
        """Actualiza el stock de un producto."""
        prod = self.get(sku)
        if not prod:
            return False
        prod.stock = nuevo_stock
        prod.save()
        return True

    def _save_skus(self) -> None:
        """Persiste la lista de SKUs."""
        save_json(CATALOGO_PATH, self._skus)

    def count(self) -> int:
        return len(self._productos)

    def productos_sin_fotos(self) -> list[Producto]:
        """Retorna productos que no tienen fotos en originales/."""
        return [p for p in self.productos if not p.tiene_fotos]

    def ultimos_productos(self, n: int = 5) -> list[Producto]:
        """Retorna los últimos N productos agregados (por fecha_creacion)."""
        ordenados = sorted(
            self.productos,
            key=lambda p: p.fecha_creacion or "",
            reverse=True,
        )
        return ordenados[:n]
