# palishopping-kb — Base de Conocimiento de Palishopping

Este directorio es la fuente de verdad del negocio Palishopping para agentes de Claude Code.
Contiene toda la información sobre productos, bundles, publicaciones y proveedores,
organizada de forma estructurada para que los agentes puedan razonar y tomar decisiones
sobre qué publicar, a qué precio y cómo combinar productos.

---

## Estructura

```
palishopping-kb/
├── README.md                        # Este archivo
├── catalogo.json                    # Lista completa de productos base disponibles
├── productos-base/                  # Fichas detalladas por producto (una por archivo)
├── bundles/                         # Definiciones de combos/paquetes armados
├── listings/                        # Publicaciones activas en MercadoLibre (por MLA ID)
├── inteligencia-global/
│   ├── bundles-sugeridos.md         # Ideas de combos generadas por análisis o agentes
│   ├── tendencias-reviews.md        # Tendencias de mercado y análisis de reseñas
│   └── oportunidades.md             # Oportunidades detectadas: nichos, precios, brechas
└── proveedores/
    ├── andres.json                  # Proveedor Andrés: productos y condiciones
    └── sao-bernardo.json            # Proveedor São Bernardo: productos y condiciones
```

---

## Cómo se usa

### `catalogo.json`
Array de todos los productos individuales disponibles para armar publicaciones.
Cada entrada tiene como mínimo: `id`, `nombre`, `proveedor`, `costo`, `stock`.

### `productos-base/`
Un archivo JSON por producto con ficha completa: dimensiones, peso, materiales,
atributos para MercadoLibre, fotos de referencia y notas de venta.

### `bundles/`
Un archivo JSON por combo/paquete. Define qué productos lo componen, el precio
sugerido, la imagen a generar y la familia de publicación en ML.

### `listings/`
Un archivo JSON por publicación activa en MercadoLibre. Nombrado por MLA ID.
Contiene el estado actual: precio, stock, métricas, última actualización.

### `inteligencia-global/`
Archivos Markdown con análisis estratégico del negocio:
- **bundles-sugeridos.md**: combos que conviene armar según demanda y costos.
- **tendencias-reviews.md**: qué dicen los compradores en reseñas propias y de competidores.
- **oportunidades.md**: categorías o nichos donde hay margen para crecer.

### `proveedores/`
Un JSON por proveedor con sus productos, precios de costo, condiciones de compra
y datos de contacto. Fuente de verdad para calcular márgenes.

---

## Flujo típico de un agente

1. Leer `catalogo.json` para ver qué productos hay disponibles.
2. Consultar `inteligencia-global/bundles-sugeridos.md` para ideas de combos.
3. Armar o seleccionar un bundle desde `bundles/`.
4. Publicar en MercadoLibre via `agente/agente.py` o el MCP server.
5. Guardar el resultado en `listings/{MLA_ID}.json`.
6. Actualizar `inteligencia-global/oportunidades.md` si se detecta algo relevante.

---

## Notas para agentes

- Este directorio **no** contiene código de ejecución. Es solo datos y conocimiento.
- El código de publicación vive en `~/Proyectos/palishopping-agent/`.
- Las credenciales y tokens **nunca** se guardan aquí.
- Ante duda sobre estructura de payload ML, consultar el `CLAUDE.md` del agente.
