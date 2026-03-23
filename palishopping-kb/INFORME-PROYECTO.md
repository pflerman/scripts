# PALISHOPPING-KB — Informe completo del proyecto

## Qué es

Sistema de **Knowledge Base y gestión** para Palishopping, un emprendimiento argentino de e-commerce que vende productos de organización del hogar (organizadores de zapatos, perchas, bolsas de vacío, armarios modulares) en **MercadoLibre**.

Este repo es la **fuente única de verdad** para: productos, bundles, listings, proveedores e inteligencia de mercado.

**No es un sistema de ventas** — toda la publicación y gestión de transacciones se hace desde `~/Proyectos/palishopping-agent/`. Este repo maneja solo **datos y herramientas de gestión**.

---

## Cómo ejecutar

```bash
cd /home/pepe/Proyectos/palishopping-kb
./run.sh
# o directamente:
python3 -m app.main
```

Los scripts CLI se ejecutan desde la raíz:
```bash
python3 scripts/nuevo_producto.py
python3 scripts/gestionar_fotos.py
python3 scripts/generar_titulo.py
```

---

## Estructura del proyecto

```
palishopping-kb/
├── run.sh                    # Lanza la app: python3 -m app.main
├── SISTEMA.md                # Documentación completa del sistema (271 líneas)
├── README.md                 # Guía para agentes
├── catalogo.json             # Array de 9 SKUs — índice maestro
├── modelos.json              # 9 modelos (COM, TAP, CAJ, ACR, SNK, CHI, MED, GRA, MAG)
│
├── app/                      # Aplicación GUI (Tkinter puro + ttk)
│   ├── main.py               # Punto de entrada: lanza AppWindow
│   ├── config.py             # Paths, constantes, settings de negocio
│   ├── models/
│   │   ├── catalogo.py       # Clase Producto + Catalogo manager (CRUD completo)
│   │   ├── bundle.py         # Bundle, BundleItem, BundleManager
│   │   └── listing.py        # Listing, ListingManager (borradores ML)
│   ├── ui/
│   │   ├── theme.py          # Paleta Material Design + estilos ttk
│   │   ├── app_window.py     # Ventana principal: sidebar + navegación + statusbar
│   │   └── views/
│   │       ├── dashboard_view.py   # Contadores, advertencias, productos recientes
│   │       ├── productos_view.py   # 630 líneas: Treeview + filtro dual + formulario CRUD
│   │       ├── bundles_view.py     # Lista simple (placeholder interactivo)
│   │       ├── listings_view.py    # Lista simple (placeholder interactivo)
│   │       ├── fotos_view.py       # Placeholder (Fase 2)
│   │       └── ia_view.py          # Placeholder (Fase 2)
│   ├── ui/components/        # Componentes reutilizables (creados pero no usados aún)
│   │   ├── product_card.py
│   │   ├── photo_grid.py
│   │   ├── log_panel.py
│   │   └── dialogs.py
│   └── utils/
│       ├── validators.py     # Generación SKU, abreviaturas, parsing precios
│       └── file_helpers.py   # JSON I/O, slugify, conteo de fotos
│
├── scripts/                  # Utilidades CLI (con Rich para output)
│   ├── nuevo_producto.py     # Crear producto (con API dólar blue)
│   ├── listar_productos.py   # Listar productos en tabla
│   ├── actualizar_precio.py  # Actualizar precio de costo
│   ├── actualizar_stock.py   # Actualizar stock
│   ├── crear_bundle.py       # Crear producto compuesto
│   ├── crear_listing.py      # Crear borrador ML desde bundle
│   ├── generar_titulo.py     # Claude AI: títulos optimizados ML
│   ├── generar_descripcion.py # Claude AI: descripciones ML
│   ├── generar_prompts_gemini.py # Claude: prompts para fotos lifestyle
│   ├── gestionar_fotos.py    # 70KB: Pipeline completo de fotos (menú interactivo)
│   ├── scrapear_fotos.py     # Scraper de fotos de ML
│   ├── importar_fotos_gemini.py # Mover fotos generadas por Gemini
│   └── ver_*.py (6 archivos) # Abrir carpetas de fotos en Nautilus
│
├── productos-base/           # 9 productos, cada uno con:
│   └── {SKU}/
│       ├── producto.json     # Spec completa del producto
│       ├── fotos/
│       │   ├── originales/       # Fotos crudas (punto de entrada)
│       │   ├── procesadas/       # Sin fondo (rembg) + centradas
│       │   ├── con_fondo/        # Optimizadas con fondo original
│       │   ├── listas_gemini/    # 1024px cuadradas, sin fondo → para Gemini
│       │   ├── con_texto/        # Con overlay de marca Palishopping
│       │   ├── gemini/           # Fotos lifestyle generadas por IA
│       │   └── generadas/        # Placeholder
│       ├── inteligencia/
│       │   ├── reviews.json
│       │   └── preguntas.json
│       └── media/
│
├── bundles/                  # Combos (vacío — Fase 2)
├── listings/drafts/          # Borradores ML (Fase 2)
├── inteligencia-global/      # Análisis de mercado (stubs)
│   ├── bundles-sugeridos.md
│   ├── tendencias-reviews.md
│   └── oportunidades.md
└── proveedores/              # Datos de proveedores
    ├── andres.json
    └── sao-bernardo.json
```

---

## Catálogo actual (9 productos)

| SKU | Tipo | Modelo | Proveedor |
|-----|------|--------|-----------|
| ORG-ZAP-COM-BLA-40 | Organizador zapatos | Común | andres |
| ORG-ZAP-TAP-BLA-40 | Organizador zapatos | Tapa rígida | andres |
| ORG-ZAP-COM-BLA-44 | Organizador zapatos | Común | andres |
| ORG-ZAP-TAP-BLA-44 | Organizador zapatos | Tapa rígida | andres |
| PER-ROP-MAG-BLA | Perchero ropa | Mágico | sao-bernardo |
| PER-ROP-GRA-BLA | Perchero ropa | Grande | sao-bernardo |
| ARM-MOD-CHI-BLA | Armario modular | Chico | sao-bernardo |
| ARM-MOD-MED-BLA | Armario modular | Mediano | sao-bernardo |
| ARM-MOD-GRA-BLA | Armario modular | Grande | sao-bernardo |

---

## Formato de SKU

`TIPO-MODELO-COLOR[-TALLE]`

**Tipos**: ORG-ZAP, ORG-BOT, ORG-COL, BOL-VAC, PER-ROP, CAJ-DEC, MISC, ARM-MOD
**Modelos**: COM, TAP, CAJ, ACR, SNK, CHI, MED, GRA, MAG
**Colores**: BLA, NEG, GRI, BEI, ROS, ROJ, AZU, VER, AMA, MAR, TRA, MUL

---

## Configuración de negocio (app/config.py)

- `FACTOR_NACIONALIZACION = 1.9` (FOB → ARS)
- `MARGEN = 2.5` (markup sugerido)
- `BLUE_DOLLAR_API = "https://api.bluelytics.com.ar/v2/latest"`
- `CLAUDE_MODEL = "claude-sonnet-4-20250514"`

---

## Pipeline de fotos

### Pipeline A (con fondo):
```
originales/ → con_fondo/ (1024px cuadrada, autocrop + pad, fondo original)
           → con_texto/*_confondo.jpg (overlay marca Palishopping)
```

### Pipeline B (sin fondo):
```
originales/ → procesadas/ (rembg, PNG transparente sobre blanco)
           → listas_gemini/ (1024px cuadrada, sin fondo)
           → con_texto/*_sinfondo.jpg (overlay marca)
```

El script `gestionar_fotos.py` (70KB) tiene un menú interactivo con todas las opciones numeradas.

---

## Lo que está HECHO (Fase 1 — Completa)

### App GUI
- [x] Ventana principal con sidebar y navegación entre 6 secciones
- [x] Dashboard con contadores, advertencias y productos recientes
- [x] Vista Productos: Treeview con columnas SKU/Nombre/Tipo/Costo/Stock
- [x] Filtro dual (Buscar + Excluir): insensible a acentos/mayúsculas, multi-palabra AND
- [x] Formulario crear/editar producto (modal): todos los campos, preview SKU, validación
- [x] Eliminar producto: borra de catalogo.json + carpeta completa de disco
- [x] Conversión dólar blue vía API para proveedor Andrés
- [x] Tema Material Design (paleta colores, estilos ttk)
- [x] Statusbar con contadores

### Modelos de datos
- [x] Clase Producto con todos los campos (sku, nombre, variante, dimensiones, precios, etc.)
- [x] Catalogo manager: cargar, crear, actualizar, eliminar, buscar
- [x] Bundle model y BundleManager
- [x] Listing model y ListingManager

### Scripts CLI (todos funcionales)
- [x] Crear productos interactivamente
- [x] Actualizar precio y stock
- [x] Pipeline completo de fotos (70KB, menú con ~11 opciones)
- [x] Scraper de fotos de MercadoLibre
- [x] Generación de títulos y descripciones con Claude AI
- [x] Generación de prompts para fotos Gemini
- [x] Importar fotos generadas por Gemini
- [x] Crear bundles y listings desde CLI

---

## Lo que está HECHO (Fase 2 — Completa)

### Vista Fotos (fotos_view.py)
- [x] Selector de producto (combobox con SKUs)
- [x] Grilla de thumbnails por subcarpeta (tabs: originales, procesadas, con_fondo, listas_gemini, con_texto, gemini)
- [x] Contadores de fotos por subcarpeta
- [x] Botón importar fotos (file dialog)
- [x] Pipeline A: Optimizar → con_fondo, + Texto → con_texto (_confondo)
- [x] Pipeline B: Quitar fondo → procesadas, Optimizar → listas_gemini, + Texto → con_texto (_sinfondo)
- [x] Diálogo para precio/specs antes de agregar texto
- [x] Ejecución en thread separado con log de progreso
- [x] Botón abrir carpeta en file manager
- [x] Servicio `app/services/foto_processing.py` con funciones reutilizables extraídas de gestionar_fotos.py

### Vista IA (ia_view.py)
- [x] Selector de producto
- [x] Botón "Generar Títulos ML" → llama Claude API en thread separado
- [x] Botón "Generar Descripciones ML" → llama Claude API en thread separado
- [x] Botón "Generar Prompts Gemini" → Claude Vision analiza foto y genera 5 prompts
- [x] Área de texto con resultados formateados
- [x] Botón copiar al portapapeles
- [x] Elegir N° + "Aplicar título" / "Aplicar descripción" → guarda en producto.json
- [x] Historial de generaciones guardado en inteligencia/
- [x] Indicador de estado de API key
- [x] Servicio `app/services/ia_generation.py` con funciones reutilizables

### Vista Bundles interactiva (bundles_view.py)
- [x] Treeview con columnas: Nombre, Productos, Costo, Sugerido, Precio Final
- [x] Formulario crear bundle: seleccionar productos del catálogo + cantidades
- [x] Cálculo automático de costo total y precio sugerido (MARGEN = 2.5)
- [x] Editar bundle (doble-click o Enter)
- [x] Eliminar bundle con confirmación

### Vista Listings interactiva (listings_view.py)
- [x] Treeview con columnas: Título, Bundle, Precio, Stock, Estado
- [x] Crear listing desde bundle seleccionado (auto-fill precio, título, descripción)
- [x] Campos editables: título, descripción, precio, stock, estado
- [x] Estados: draft / ready / published (visual, sin API real)
- [x] Editar y eliminar listings

### Componentes UI (conectados en Fase 2)
- [x] `photo_grid.py` — grilla de thumbnails (usado en FotosView)
- [x] `log_panel.py` — panel de logs (usado en FotosView y IAView)
- [x] `dialogs.py` — diálogos reutilizables (InputDialog, ConfirmDialog)
- [x] `product_card.py` — tarjeta visual de producto (disponible)

---

## Lo que FALTA hacer (Fase 3 — Futuro)

### Datos pendientes
- [ ] Cargar datos reales en proveedores/ (actualmente vacíos)
- [ ] Completar inteligencia-global/ (bundles sugeridos, tendencias, oportunidades)
- [ ] Agregar más productos al catálogo

### Mejoras futuras
- [ ] Selección de fotos portada + apoyo en bundles
- [ ] Thumbnails de fotos en el Treeview de productos
- [ ] Métricas en dashboard (velocidad de venta, márgenes por proveedor)
- [ ] Export/import de datos
- [ ] Integración directa con API de MercadoLibre (publicar real)
- [ ] Drag & drop para importar fotos

---

## Dependencias

- **Python 3.10+**
- **tkinter** (viene con Python en la mayoría de distros)
- **Rich** (para los scripts CLI)
- **rembg** (para quitar fondos en pipeline de fotos)
- **Pillow** (procesamiento de imágenes)
- **anthropic** (SDK para Claude AI — generación de títulos/descripciones)

---

## Historial de Git (commits relevantes)

```
8c9740a Enter en Treeview abre formulario de edición
c779653 Fix: eliminar producto borra carpeta de disco + existe() chequea solo memoria
1d0eeac Limpiar SKUs duplicados en catalogo.json + botón Eliminar producto
7696c8e Buscador: dos campos Buscar/Excluir, insensible a acentos y mayúsculas
deb25d6 Fix grab_set, eliminar detalle read-only, click simple solo selecciona
44129d5 Migración a Tkinter puro + ttk, fix SKU duplicado, layout statusbar y dashboard refresh
3b5e0d4 Fase 1: app GUI con CustomTkinter - estructura base
```

---

## Notas técnicas importantes

1. **Se migró de CustomTkinter a Tkinter puro + ttk** — CustomTkinter se descartó a favor de ttk por estabilidad
2. **catalogo.json** es solo un array de strings (SKUs) — los datos completos están en cada `producto.json`
3. **El método `existe()` del Catalogo** chequea solo memoria (no disco) — diseño intencional
4. **Los scripts CLI y la app GUI comparten los mismos datos** — ambos leen/escriben los mismos JSONs
5. **gestionar_fotos.py** (70KB CLI) y la GUI comparten la misma lógica vía `app/services/foto_processing.py`
6. **La GUI ejecuta operaciones pesadas** (fotos, API calls) en threads separados para no bloquear la interfaz
7. **Nuevos servicios**: `app/services/foto_processing.py` (pipeline fotos) y `app/services/ia_generation.py` (Claude API)
