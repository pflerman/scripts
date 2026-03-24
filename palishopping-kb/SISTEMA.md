# SISTEMA.md — Guía completa de palishopping-kb

> **Para agentes de Claude Code**: este archivo describe el sistema completo. Léelo antes de operar sobre el repo.

---

## Qué es Palishopping

Palishopping es un negocio de e-commerce que vende productos de organización del hogar (organizadores de zapatos, botas, ropa, bolsas al vacío, etc.) en **MercadoLibre Argentina**.

Los productos se compran a proveedores locales (Andrés, São Bernardo) y se publican individualmente o en combos (bundles). La estrategia incluye generar fotos de producto de alta calidad —con y sin fondo— y textos optimizados para ML usando IA.

Este repositorio es la **fuente de verdad del negocio**: datos de productos, fotos, bundles, publicaciones activas y análisis estratégico. El código de publicación vive en `~/Proyectos/palishopping-agent/`.

---

## Estructura de carpetas

```
palishopping-kb/
├── SISTEMA.md                        # Esta guía
├── README.md                         # Descripción general para agentes
├── catalogo.json                     # Índice de todos los productos base (array JSON)
│
├── productos-base/                   # Un directorio por producto (nombrado por SKU)
│   └── <SKU>/
│       ├── <SKU>.json                # Ficha completa del producto
│       └── fotos/
│           ├── originales/           # Fotos crudas de entrada (fuente de todo)
│           ├── procesadas/           # Sin fondo (rembg), centradas y normalizadas
│           ├── con_fondo/            # Optimizadas manteniendo fondo original
│           ├── listas_gemini/        # Sin fondo, crop + padding 1024px, listas para Gemini
│           └── con_texto/            # Con texto de marca superpuesto
│               # *_confondo.jpg  → viene de Pipeline A
│               # *_sinfondo.jpg  → viene de Pipeline B
│
├── bundles/                          # Un JSON por combo armado de productos base
├── listings/                         # Un JSON por publicación activa en ML (nombre = MLA ID)
│
├── inteligencia-global/
│   ├── bundles-sugeridos.md          # Ideas de combos generadas por análisis
│   ├── tendencias-reviews.md         # Análisis de reseñas propias y de competidores
│   └── oportunidades.md              # Nichos, precios, brechas detectadas
│
├── proveedores/
│   ├── andres.json                   # Productos, precios de costo y condiciones de Andrés
│   └── sao-bernardo.json             # Ídem São Bernardo
│
└── scripts/                          # Herramientas de gestión (ver sección Scripts)
```

---

## Los 3 niveles

### 1. Producto Base
Ítem individual comprado a un proveedor. Tiene SKU único, ficha JSON con atributos, precio de costo, stock y carpeta de fotos propia.

Archivo: `productos-base/<SKU>/<SKU>.json`
Índice: `catalogo.json`

### 2. Bundle
Combinación de uno o más productos base armada para publicar. Define qué productos lo componen, precio sugerido e imagen a generar.

Archivo: `bundles/<nombre>.json`
Estado: **pendiente implementación** (`crear_bundle.py` no existe aún)

### 3. Listing
Publicación activa en MercadoLibre. Referencia a un bundle o producto base, con el MLA ID asignado por ML, precio actual, stock y métricas.

Archivo: `listings/<MLA_ID>.json`
Estado: **pendiente implementación** (`crear_listing.py` no existe aún)

---

## Convención de SKUs

Formato: `TIPO-MODELO-COLOR-TALLE`
Ejemplo: `ORG-ZAP-TAP-BLA-40`

### Tipos de producto

| Código    | Tipo                    |
|-----------|-------------------------|
| `ORG-ZAP` | Organizador de zapatos  |
| `ORG-BOT` | Organizador de botas    |
| `ORG-COL` | Organizador colgante    |
| `BOL-VAC` | Bolsa al vacío          |
| `PER-ROP` | Percha ropa             |
| `CAJ-DEC` | Caja decorada           |
| `MISC`    | Otro / Misceláneo       |
| `ARM-MOD` | Armario modular         |

### Modelos

| Código | Modelo                  |
|--------|-------------------------|
| `COM`  | Común                   |
| `TAP`  | Tapa rígida             |
| `CAJ`  | Cajoncito               |
| `ACR`  | Acrílico                |
| `SNK`  | Snkrs acrílico con imán |
| `CHI`  | Chico                   |
| `MED`  | Mediano                 |
| `GRA`  | Grande                  |

### Colores

| Código | Color        |
|--------|--------------|
| `BLA`  | Blanco       |
| `NEG`  | Negro        |
| `GRI`  | Gris         |
| `BEI`  | Beige        |
| `ROS`  | Rosa         |
| `ROJ`  | Rojo         |
| `AZU`  | Azul         |
| `VER`  | Verde        |
| `AMA`  | Amarillo     |
| `MAR`  | Marrón       |
| `TRA`  | Transparente |
| `MUL`  | Multicolor   |

**Talle**: número (ej: `40`) o talle textil (`S`, `M`, `L`, `XL`).
Si el color es libre, `nuevo_producto.py` toma las primeras 3 letras en mayúscula.

---

## Scripts disponibles

Todos los scripts se ejecutan desde `scripts/` con `python3 <script>.py`. Usan Rich para la UI y leen `catalogo.json` para listar productos.

### Gestión de productos

| Script                | Qué hace |
|-----------------------|----------|
| `nuevo_producto.py`   | Agrega un producto al catálogo: pide tipo, color, talle, proveedor, precio y stock. Genera el SKU, crea `productos-base/<SKU>/<SKU>.json` y la estructura de carpetas de fotos. |
| `actualizar_precio.py`| Actualiza `precio_costo` de un producto existente en la KB. |
| `actualizar_stock.py` | Actualiza `stock` de un producto existente en la KB. |
| `crear_bundle.py`     | Arma un bundle: elige uno o más productos del catálogo, define cantidades, calcula precio sugerido (margen 2.5x configurable), permite ajustar precio final y elegir fotos de portada/apoyo. Guarda en `bundles/<slug>.json`. |
| `crear_listing.py`    | Prepara un draft de listing desde un bundle: verifica que tenga título, descripción y portada, permite ajustar precio y stock, genera `listings/drafts/<slug>.json` listo para publicar con el agente. |

### Fotos

| Script                  | Qué hace |
|-------------------------|----------|
| `scrapear_fotos.py`     | Scrapea fotos de una publicación ML existente y las guarda en `originales/`. Requiere `~/.ml_cookies.json`. |
| `gestionar_fotos.py`    | Menú interactivo completo de procesamiento de fotos. Cubre todo el Pipeline A y B (ver sección siguiente). |
| `ver_originales.py`     | Abre `fotos/originales/` del producto elegido en Nautilus. |
| `ver_con_fondo.py`      | Abre `fotos/con_fondo/` en Nautilus. |
| `ver_procesadas.py`     | Abre `fotos/procesadas/` en Nautilus. |
| `ver_listas_gemini.py`  | Abre `fotos/listas_gemini/` en Nautilus. |
| `ver_con_texto.py`      | Abre `fotos/con_texto/` en Nautilus. |
| `ver_gemini.py`         | Abre `fotos/gemini/` en Nautilus. |

### Fotos generadas con IA (requieren `ANTHROPIC_API_KEY` o Gemini AI Studio)

| Script                       | Qué hace |
|------------------------------|----------|
| `generar_prompts_gemini.py`  | Analiza una foto de `listas_gemini/` con Claude API y genera 5 prompts lifestyle listos para copiar en AI Studio. Guarda los prompts en la ficha JSON del producto. |
| `importar_fotos_gemini.py`   | Busca archivos `Generated Image*.png` en `~/Downloads`, los mueve a `fotos/gemini/` del producto elegido y los renombra con formato SEO. |

### Contenido ML (requieren `ANTHROPIC_API_KEY`)

| Script                   | Qué hace |
|--------------------------|----------|
| `generar_titulo.py`      | Genera títulos optimizados para MercadoLibre usando Claude AI. Guarda resultados en la ficha JSON del producto. |
| `generar_descripcion.py` | Genera descripción completa para ML usando Claude AI. Guarda en la ficha JSON. |

---

## Pipeline de fotos

El punto de entrada siempre es `fotos/originales/`. Hay dos pipelines paralelos según el tratamiento de fondo.

```
originales/
    │
    ├─── PIPELINE A: con fondo ────────────────────────────────────────────────
    │
    │   [Opción 6A] Optimizar con fondo
    │   - Autocrop + pad a cuadrado 1024px conservando fondo original
    │   → con_fondo/
    │
    │   [Opción 7A] Agregar texto con fondo
    │   - Superpone texto de marca (precio, nombre) con paleta de colores Palishopping
    │   → con_texto/*_confondo.jpg
    │
    └─── PIPELINE B: sin fondo ────────────────────────────────────────────────

        [Opción 4] Remover fondo (rembg / fallback Pillow)
        → procesadas/  (PNG transparente sobre blanco)

        [Opción 5] Revisar procesadas
        - Visualización y descarte manual de fotos con mal resultado

        [Opción 9] Centrar y normalizar
        - Centra el producto en canvas 1200px con margen 10%
        → procesadas/  (reemplaza in-place)

        [Opción 6B] Optimizar para Gemini
        - Autocrop + pad a cuadrado 1024px, sin fondo
        → listas_gemini/

        [Opción 7B] Agregar texto sin fondo
        - Superpone texto de marca
        → con_texto/*_sinfondo.jpg
```

### Utilidades adicionales en `gestionar_fotos.py`

| Opción | Qué hace |
|--------|----------|
| 1      | Ver y eliminar fotos en `originales/` |
| 2      | Agregar fotos propias a `originales/` (soporta jpg/png/webp, carpetas) |
| 3      | Limpiar carpetas de salida (procesadas, con_fondo, listas_gemini, con_texto) |
| 8      | Detectar y descartar fotos malas en `originales/` (análisis de calidad automático) |
| 10     | Generar collage multi-ángulo desde `procesadas/` |
| 11     | Ver fotos en `con_fondo/` |

### Carpetas de entrada y salida por paso

| Paso | Entrada         | Salida           |
|------|-----------------|------------------|
| 4    | `originales/`   | `procesadas/`    |
| 5    | `procesadas/`   | `procesadas/`    |
| 6A   | `originales/`   | `con_fondo/`     |
| 6B   | `procesadas/`   | `listas_gemini/` |
| 7A   | `con_fondo/`    | `con_texto/`     |
| 7B   | `listas_gemini/`| `con_texto/`     |
| 9    | `procesadas/`   | `procesadas/`    |
| 10   | `procesadas/`   | `procesadas/`    |

---

## Próximos pasos

### Scripts pendientes de implementar

| Script                  | Descripción |
|-------------------------|-------------|

### Datos pendientes de cargar

- El catálogo tiene actualmente **1 producto** (`ORG-ZAP-BLA-40`, proveedor Andrés).
- Cargar el catálogo completo de ambos proveedores con todos los productos reales.
- Completar fichas JSON de productos con dimensiones, peso, materiales y atributos ML.
- Poblar `inteligencia-global/` con análisis inicial del mercado.

---

## Flujo típico de un agente

1. Leer `catalogo.json` → ver qué productos hay disponibles.
2. Leer `inteligencia-global/bundles-sugeridos.md` → ideas de combos.
3. Armar o seleccionar un bundle desde `bundles/`.
4. Verificar que las fotos del producto estén listas en `con_texto/`.
5. Publicar en MercadoLibre via `palishopping-agent/`.
6. Guardar resultado en `listings/<MLA_ID>.json`.
7. Actualizar `inteligencia-global/` si se detecta algo relevante.

---

## Notas para agentes

- Este repo **no contiene código de publicación**. Solo datos y conocimiento. El agente publicador vive en `~/Proyectos/palishopping-agent/`.
- Las credenciales y tokens **nunca** se guardan aquí.
- Para operar sobre un producto, siempre leer primero `catalogo.json` para obtener el SKU correcto.
- La estructura de carpetas de fotos se crea automáticamente con `nuevo_producto.py` o `gestionar_fotos.py`. No crear carpetas manualmente.
- `rembg` es opcional: si no está instalado, `gestionar_fotos.py` ofrece instalar o usar el fallback de Pillow.
