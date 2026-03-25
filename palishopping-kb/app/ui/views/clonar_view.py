"""Vista "Clonar Publicación" — Clonar un ítem de ML a palishopping."""

import io
import logging
import threading
import tkinter as tk
from tkinter import ttk
from pathlib import Path

from app.ui import theme
from app.ui.components.log_panel import LogPanel

logger = logging.getLogger(__name__)


# Colores disponibles en ML para modelo UP
COLORES_ML = {
    "Blanco": "52055",
    "Negro": "52049",
    "Rosa": "51994",
    "Turquesa": "283160",
    "Gris": "283165",
    "Verde": "52014",
    "Azul": "52028",
    "Rojo": "51993",
    "Transparente": "52055",
    "Combinado Blanco Negro": "63068037",
}


class ClonarView(tk.Frame):
    """Vista para clonar publicaciones de MercadoLibre a palishopping."""

    def __init__(self, master: tk.Widget, **kwargs):
        super().__init__(master, bg=theme.BG_PRIMARY, **kwargs)
        self._processing = False
        self._datos_item: dict | None = None
        self._fotos_descargadas: list[Path] = []
        self._color_vars: dict[str, tk.BooleanVar] = {}
        self._photo_refs: list = []  # prevent GC
        self._build()

    # ══════════════════════════════════════════════════════════════════════════
    # BUILD UI
    # ══════════════════════════════════════════════════════════════════════════

    def _build(self) -> None:
        # ── Header ────────────────────────────────────────────────────────────
        header = tk.Frame(self, bg=theme.BG_PRIMARY)
        header.pack(fill="x", padx=20, pady=(20, 8))

        tk.Label(header, text="Clonar Publicación", font=theme.FONT_TITLE,
                 bg=theme.BG_PRIMARY, fg=theme.TEXT_PRIMARY).pack(side="left")

        self._status_label = tk.Label(
            header, text="", font=theme.FONT_SMALL,
            bg=theme.BG_PRIMARY, fg=theme.TEXT_MUTED)
        self._status_label.pack(side="right")

        # ── URL Input ─────────────────────────────────────────────────────────
        url_frame = tk.Frame(self, bg=theme.BG_SECONDARY, bd=1, relief="solid",
                             highlightbackground=theme.BORDER, highlightthickness=1)
        url_frame.pack(fill="x", padx=20, pady=(0, 8))

        tk.Label(url_frame, text="URL:", font=theme.FONT_BOLD,
                 bg=theme.BG_SECONDARY, fg=theme.TEXT_SECONDARY
                 ).pack(side="left", padx=(10, 4), pady=8)

        self._url_entry = tk.Entry(
            url_frame, font=theme.FONT_NORMAL, bg=theme.BG_INPUT,
            fg=theme.TEXT_PRIMARY, relief="flat", bd=1,
            highlightbackground=theme.BORDER, highlightthickness=1)
        self._url_entry.pack(side="left", fill="x", expand=True, padx=(0, 6), pady=8)
        self._url_entry.bind("<Return>", lambda e: self._analizar())

        self._btn_analizar = tk.Button(
            url_frame, text="Analizar", font=theme.FONT_BOLD,
            bg=theme.BTN_INFO, fg="white", relief="flat", bd=0,
            padx=14, pady=4, cursor="hand2", command=self._analizar)
        self._btn_analizar.pack(side="left", padx=(0, 8), pady=8)

        # ── Área principal: scrollable ────────────────────────────────────────
        main_canvas = tk.Canvas(self, bg=theme.BG_PRIMARY, highlightthickness=0)
        scrollbar = tk.Scrollbar(self, orient="vertical", command=main_canvas.yview)
        self._scroll_frame = tk.Frame(main_canvas, bg=theme.BG_PRIMARY)

        self._scroll_frame.bind(
            "<Configure>",
            lambda e: main_canvas.configure(scrollregion=main_canvas.bbox("all")))
        main_canvas.create_window((0, 0), window=self._scroll_frame, anchor="nw")
        main_canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        main_canvas.pack(side="left", fill="both", expand=True, padx=(20, 0), pady=(0, 4))
        self._main_canvas = main_canvas

        # Bind mousewheel
        def _on_mousewheel(event):
            main_canvas.yview_scroll(int(-1 * (event.delta or event.num == 4 and -1 or 1) // 1), "units")

        main_canvas.bind_all("<Button-4>", lambda e: main_canvas.yview_scroll(-3, "units"))
        main_canvas.bind_all("<Button-5>", lambda e: main_canvas.yview_scroll(3, "units"))

        # Resize inner to canvas width
        def _on_canvas_configure(event):
            main_canvas.itemconfigure("all", width=event.width)
        main_canvas.bind("<Configure>", _on_canvas_configure)

        # ── Preview (initially hidden) ────────────────────────────────────────
        self._preview_frame = tk.Frame(self._scroll_frame, bg=theme.BG_PRIMARY)

        # ── Config panel (initially hidden) ───────────────────────────────────
        self._config_frame = tk.Frame(self._scroll_frame, bg=theme.BG_PRIMARY)

        # ── Log panel ─────────────────────────────────────────────────────────
        self._log = LogPanel(self._scroll_frame, height=10)

    # ══════════════════════════════════════════════════════════════════════════
    # ANALIZAR
    # ══════════════════════════════════════════════════════════════════════════

    def _analizar(self) -> None:
        url = self._url_entry.get().strip()
        if not url:
            self._status_label.configure(text="Pegá una URL de MercadoLibre", fg=theme.WARNING)
            return
        if self._processing:
            return

        self._set_processing(True, "Analizando publicación...")
        self._log.pack(fill="x", padx=0, pady=(8, 0))
        self._log.clear()
        self._log.log(f"Resolviendo URL: {url[:80]}...")

        # Limpiar preview anterior
        self._preview_frame.pack_forget()
        self._config_frame.pack_forget()
        for w in self._preview_frame.winfo_children():
            w.destroy()
        for w in self._config_frame.winfo_children():
            w.destroy()

        def _worker():
            try:
                from app.services.ml_scraper import scrape_listing, download_photos

                self._log_safe("Obteniendo datos del ítem...")
                datos = scrape_listing(url)
                self._datos_item = datos

                titulo = datos.get("titulo", "")
                precio = datos.get("precio", 0)
                category = datos.get("category_id", "")
                fotos = datos.get("foto_urls", [])

                self._log_safe(f"Título: {titulo[:70]}")
                self._log_safe(f"Precio: ${precio:,.0f} ARS")
                self._log_safe(f"Categoría: {category}")
                self._log_safe(f"Fotos: {len(fotos)}")

                # Descargar fotos a /tmp
                if fotos:
                    import re
                    item_id = "unknown"
                    m = re.search(r"MLA-?\d+", url.upper())
                    if m:
                        item_id = m.group().replace("-", "")
                    tmp_dir = Path(f"/tmp/clonar_{item_id}")
                    self._log_safe(f"Descargando {len(fotos)} fotos a {tmp_dir}...")
                    self._fotos_descargadas = download_photos(
                        fotos, tmp_dir,
                        callback=lambda msg: self._log_safe(msg))
                    self._log_safe(f"{len(self._fotos_descargadas)} fotos descargadas")
                else:
                    self._fotos_descargadas = []

                self.after(0, self._mostrar_preview)

            except Exception as e:
                self._log_safe(f"ERROR: {e}")
                self.after(0, lambda: self._set_processing(False, f"Error: {e}"))

        threading.Thread(target=_worker, daemon=True).start()

    def _log_safe(self, msg: str) -> None:
        """Log desde cualquier thread."""
        self.after(0, lambda m=msg: self._log.log(m))

    # ══════════════════════════════════════════════════════════════════════════
    # PREVIEW
    # ══════════════════════════════════════════════════════════════════════════

    def _mostrar_preview(self) -> None:
        datos = self._datos_item
        if not datos:
            return

        self._set_processing(False, "Análisis completado")

        # ── Preview card ──────────────────────────────────────────────────────
        self._preview_frame.pack(fill="x", padx=0, pady=(10, 0))

        card = tk.Frame(self._preview_frame, bg=theme.BG_CARD, bd=1, relief="solid",
                        highlightbackground=theme.BORDER, highlightthickness=1)
        card.pack(fill="x", pady=(0, 6))

        # Top row: foto + info
        top = tk.Frame(card, bg=theme.BG_CARD)
        top.pack(fill="x", padx=12, pady=10)

        # Thumbnail de la primera foto
        if self._fotos_descargadas:
            self._show_thumbnail(top, self._fotos_descargadas[0])

        # Info a la derecha
        info = tk.Frame(top, bg=theme.BG_CARD)
        info.pack(side="left", fill="both", expand=True, padx=(10, 0))

        titulo = datos.get("titulo", "Sin título")
        tk.Label(info, text=titulo, font=theme.FONT_BOLD, bg=theme.BG_CARD,
                 fg=theme.TEXT_PRIMARY, wraplength=500, anchor="w", justify="left"
                 ).pack(fill="x", anchor="w")

        precio = datos.get("precio", 0)
        precio_text = f"${precio:,.0f} ARS" if precio else "Sin precio (catalog product)"
        tk.Label(info, text=precio_text, font=theme.FONT_SUBTITLE, bg=theme.BG_CARD,
                 fg=theme.ACCENT).pack(anchor="w", pady=(4, 0))

        details = (
            f"Categoría: {datos.get('category_id', 'N/A')}  |  "
            f"Fotos: {len(datos.get('foto_urls', []))}  |  "
            f"Descargadas: {len(self._fotos_descargadas)}"
        )
        tk.Label(info, text=details, font=theme.FONT_SMALL, bg=theme.BG_CARD,
                 fg=theme.TEXT_MUTED).pack(anchor="w", pady=(2, 0))

        if datos.get("_es_catalog_product"):
            tk.Label(info, text="Fuente: Catalog Product (sin precio)", font=theme.FONT_SMALL,
                     bg=theme.BG_CARD, fg=theme.WARNING).pack(anchor="w", pady=(2, 0))

        # ── Config panel ──────────────────────────────────────────────────────
        self._config_frame.pack(fill="x", padx=0, pady=(6, 0))
        self._build_config_panel()

    def _show_thumbnail(self, parent: tk.Frame, photo_path: Path) -> None:
        """Muestra un thumbnail de la foto en el parent."""
        try:
            from PIL import Image, ImageTk
            img = Image.open(photo_path)
            img.thumbnail((120, 120))
            photo = ImageTk.PhotoImage(img)
            label = tk.Label(parent, image=photo, bg=theme.BG_CARD)
            label.image = photo  # prevent GC
            self._photo_refs.append(photo)
            label.pack(side="left")
        except Exception:
            tk.Label(parent, text="[sin preview]", font=theme.FONT_SMALL,
                     bg=theme.BG_CARD, fg=theme.TEXT_MUTED).pack(side="left")

    # ══════════════════════════════════════════════════════════════════════════
    # CONFIG PANEL
    # ══════════════════════════════════════════════════════════════════════════

    def _build_config_panel(self) -> None:
        datos = self._datos_item
        if not datos:
            return

        parent = self._config_frame

        # ── Colores ───────────────────────────────────────────────────────────
        color_card = tk.Frame(parent, bg=theme.BG_CARD, bd=1, relief="solid",
                              highlightbackground=theme.BORDER, highlightthickness=1)
        color_card.pack(fill="x", pady=(0, 6))

        tk.Label(color_card, text="Colores a publicar", font=theme.FONT_BOLD,
                 bg=theme.BG_CARD, fg=theme.TEXT_PRIMARY).pack(anchor="w", padx=12, pady=(8, 4))

        self._color_vars.clear()
        color_grid = tk.Frame(color_card, bg=theme.BG_CARD)
        color_grid.pack(fill="x", padx=12, pady=(0, 8))

        for i, (color_name, value_id) in enumerate(COLORES_ML.items()):
            var = tk.BooleanVar(value=(color_name == "Blanco"))
            self._color_vars[color_name] = var
            cb = tk.Checkbutton(
                color_grid, text=f"{color_name}", font=theme.FONT_NORMAL,
                bg=theme.BG_CARD, activebackground=theme.BG_CARD,
                variable=var, onvalue=True, offvalue=False)
            cb.grid(row=i // 3, column=i % 3, sticky="w", padx=(0, 20), pady=2)

        # ── Precio y Stock ────────────────────────────────────────────────────
        price_card = tk.Frame(parent, bg=theme.BG_CARD, bd=1, relief="solid",
                              highlightbackground=theme.BORDER, highlightthickness=1)
        price_card.pack(fill="x", pady=(0, 6))

        fields = tk.Frame(price_card, bg=theme.BG_CARD)
        fields.pack(fill="x", padx=12, pady=8)

        tk.Label(fields, text="Precio ($ARS):", font=theme.FONT_BOLD,
                 bg=theme.BG_CARD, fg=theme.TEXT_PRIMARY).grid(row=0, column=0, sticky="w", pady=2)
        self._precio_entry = tk.Entry(fields, font=theme.FONT_NORMAL, width=12,
                                       bg=theme.BG_INPUT, fg=theme.TEXT_PRIMARY,
                                       relief="flat", bd=1,
                                       highlightbackground=theme.BORDER, highlightthickness=1)
        self._precio_entry.grid(row=0, column=1, sticky="w", padx=(6, 20), pady=2)
        precio_val = datos.get("precio", 0)
        if precio_val:
            self._precio_entry.insert(0, str(int(precio_val)))

        tk.Label(fields, text="Stock:", font=theme.FONT_BOLD,
                 bg=theme.BG_CARD, fg=theme.TEXT_PRIMARY).grid(row=0, column=2, sticky="w", pady=2)
        self._stock_entry = tk.Entry(fields, font=theme.FONT_NORMAL, width=8,
                                      bg=theme.BG_INPUT, fg=theme.TEXT_PRIMARY,
                                      relief="flat", bd=1,
                                      highlightbackground=theme.BORDER, highlightthickness=1)
        self._stock_entry.grid(row=0, column=3, sticky="w", padx=(6, 20), pady=2)
        self._stock_entry.insert(0, "10")

        tk.Label(fields, text="Categoría:", font=theme.FONT_BOLD,
                 bg=theme.BG_CARD, fg=theme.TEXT_PRIMARY).grid(row=1, column=0, sticky="w", pady=2)
        self._cat_entry = tk.Entry(fields, font=theme.FONT_NORMAL, width=14,
                                    bg=theme.BG_INPUT, fg=theme.TEXT_PRIMARY,
                                    relief="flat", bd=1,
                                    highlightbackground=theme.BORDER, highlightthickness=1)
        self._cat_entry.grid(row=1, column=1, sticky="w", padx=(6, 20), pady=2)
        self._cat_entry.insert(0, datos.get("category_id", "MLA414192"))

        # ── Título ────────────────────────────────────────────────────────────
        titulo_card = tk.Frame(parent, bg=theme.BG_CARD, bd=1, relief="solid",
                               highlightbackground=theme.BORDER, highlightthickness=1)
        titulo_card.pack(fill="x", pady=(0, 6))

        titulo_header = tk.Frame(titulo_card, bg=theme.BG_CARD)
        titulo_header.pack(fill="x", padx=12, pady=(8, 4))

        tk.Label(titulo_header, text="Family Name (título)", font=theme.FONT_BOLD,
                 bg=theme.BG_CARD, fg=theme.TEXT_PRIMARY).pack(side="left")

        self._btn_gen_titulo = tk.Button(
            titulo_header, text="Generar con IA", font=theme.FONT_SMALL,
            bg=theme.BTN_SUCCESS, fg="white", relief="flat", bd=0,
            padx=8, pady=2, cursor="hand2", command=self._generar_titulo)
        self._btn_gen_titulo.pack(side="right")

        self._titulo_entry = tk.Entry(
            titulo_card, font=theme.FONT_NORMAL, bg=theme.BG_INPUT,
            fg=theme.TEXT_PRIMARY, relief="flat", bd=1,
            highlightbackground=theme.BORDER, highlightthickness=1)
        self._titulo_entry.pack(fill="x", padx=12, pady=(0, 4))

        titulo_original = datos.get("titulo", "")[:60]
        self._titulo_entry.insert(0, titulo_original)

        self._titulo_count = tk.Label(
            titulo_card, text=f"{len(titulo_original)}/60 chars", font=theme.FONT_SMALL,
            bg=theme.BG_CARD, fg=theme.TEXT_MUTED)
        self._titulo_count.pack(anchor="e", padx=12, pady=(0, 6))

        self._titulo_entry.bind("<KeyRelease>", self._update_titulo_count)

        # ── Descripción ───────────────────────────────────────────────────────
        desc_card = tk.Frame(parent, bg=theme.BG_CARD, bd=1, relief="solid",
                             highlightbackground=theme.BORDER, highlightthickness=1)
        desc_card.pack(fill="x", pady=(0, 6))

        desc_header = tk.Frame(desc_card, bg=theme.BG_CARD)
        desc_header.pack(fill="x", padx=12, pady=(8, 4))

        tk.Label(desc_header, text="Descripción", font=theme.FONT_BOLD,
                 bg=theme.BG_CARD, fg=theme.TEXT_PRIMARY).pack(side="left")

        self._btn_gen_desc = tk.Button(
            desc_header, text="Generar con IA", font=theme.FONT_SMALL,
            bg=theme.BTN_SUCCESS, fg="white", relief="flat", bd=0,
            padx=8, pady=2, cursor="hand2", command=self._generar_descripcion)
        self._btn_gen_desc.pack(side="right")

        self._desc_text = tk.Text(
            desc_card, font=theme.FONT_NORMAL, bg=theme.BG_INPUT,
            fg=theme.TEXT_PRIMARY, relief="flat", bd=1, height=5, wrap="word",
            highlightbackground=theme.BORDER, highlightthickness=1)
        self._desc_text.pack(fill="x", padx=12, pady=(0, 8))

        desc_original = datos.get("descripcion", "")
        if desc_original:
            self._desc_text.insert("1.0", desc_original)

        # ── Opciones ──────────────────────────────────────────────────────────
        opts_card = tk.Frame(parent, bg=theme.BG_CARD, bd=1, relief="solid",
                             highlightbackground=theme.BORDER, highlightthickness=1)
        opts_card.pack(fill="x", pady=(0, 6))

        opts_inner = tk.Frame(opts_card, bg=theme.BG_CARD)
        opts_inner.pack(fill="x", padx=12, pady=8)

        self._gemini_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            opts_inner, text="Regenerar fotos con Gemini (Nano Banana)",
            font=theme.FONT_NORMAL, bg=theme.BG_CARD, activebackground=theme.BG_CARD,
            variable=self._gemini_var).pack(anchor="w")

        n_fotos = len(self._fotos_descargadas)

        fotos_row = tk.Frame(opts_inner, bg=theme.BG_CARD)
        fotos_row.pack(anchor="w", pady=(4, 0))

        tk.Label(fotos_row, text="Fotos a procesar:", font=theme.FONT_NORMAL,
                 bg=theme.BG_CARD, fg=theme.TEXT_PRIMARY).pack(side="left")

        self._fotos_procesar_var = tk.StringVar(value=str(n_fotos))
        self._fotos_procesar_combo = ttk.Combobox(
            fotos_row, textvariable=self._fotos_procesar_var, state="readonly",
            values=[str(i) for i in range(1, n_fotos + 1)], width=4)
        self._fotos_procesar_combo.pack(side="left", padx=(6, 0))

        self._fotos_total_label = tk.Label(
            fotos_row, text=f"de {n_fotos}", font=theme.FONT_SMALL,
            bg=theme.BG_CARD, fg=theme.TEXT_MUTED)
        self._fotos_total_label.pack(side="left", padx=(4, 0))

        hype_row = tk.Frame(opts_inner, bg=theme.BG_CARD)
        hype_row.pack(anchor="w", pady=(4, 0))

        tk.Label(hype_row, text="Fotos con hype:", font=theme.FONT_NORMAL,
                 bg=theme.BG_CARD, fg=theme.TEXT_PRIMARY).pack(side="left")

        self._hype_var = tk.StringVar(value="0")
        self._hype_combo = ttk.Combobox(
            hype_row, textvariable=self._hype_var, state="readonly",
            values=[str(i) for i in range(n_fotos + 1)], width=4)
        self._hype_combo.pack(side="left", padx=(6, 0))

        # Cuando cambia "fotos a procesar", actualizar máximo de hype
        def _on_fotos_procesar_change(event=None):
            nuevo_max = int(self._fotos_procesar_var.get() or "1")
            self._hype_combo["values"] = [str(i) for i in range(nuevo_max + 1)]
            if int(self._hype_var.get() or "0") > nuevo_max:
                self._hype_var.set(str(nuevo_max))

        self._fotos_procesar_combo.bind("<<ComboboxSelected>>", _on_fotos_procesar_change)

        # ── Botón PUBLICAR ────────────────────────────────────────────────────
        self._btn_publicar = tk.Button(
            parent, text="Publicar en MercadoLibre", font=theme.FONT_SUBTITLE,
            bg=theme.BTN_SUCCESS, fg="white", relief="flat", bd=0,
            padx=20, pady=8, cursor="hand2", command=self._publicar)
        self._btn_publicar.pack(fill="x", pady=(8, 4))

        # Botón dry-run
        self._btn_dryrun = tk.Button(
            parent, text="Vista previa (dry-run)", font=theme.FONT_NORMAL,
            bg=theme.BG_SECONDARY, fg=theme.TEXT_PRIMARY, relief="solid", bd=1,
            padx=12, pady=4, cursor="hand2", command=self._dryrun)
        self._btn_dryrun.pack(fill="x", pady=(0, 8))

    def _update_titulo_count(self, event=None) -> None:
        n = len(self._titulo_entry.get())
        color = theme.ERROR if n > 60 else theme.TEXT_MUTED
        self._titulo_count.configure(text=f"{n}/60 chars", fg=color)

    # ══════════════════════════════════════════════════════════════════════════
    # GENERAR TÍTULO CON IA
    # ══════════════════════════════════════════════════════════════════════════

    def _generar_titulo(self) -> None:
        if self._processing:
            return
        self._set_processing(True, "Generando título con Claude AI...")
        self._log.log("Generando título...")

        def _worker():
            try:
                from app.services.ia_generation import generar_titulo
                datos = self._datos_item or {}
                producto_data = {
                    "nombre": datos.get("titulo", ""),
                    "categoria": datos.get("category_id", ""),
                    "precio": datos.get("precio", ""),
                    "descripcion": datos.get("descripcion", ""),
                    "fotos_count": len(datos.get("foto_urls", [])),
                }

                # Usar la primera foto descargada para Vision
                foto_path = None
                self._log_safe(f"Fotos descargadas: {len(self._fotos_descargadas)}")
                if self._fotos_descargadas:
                    foto_path = self._fotos_descargadas[0]
                    self._log_safe(f"Analizando foto con Vision: {foto_path} (existe: {foto_path.exists()})")

                titulo = generar_titulo("clon", producto_data, foto_path=foto_path)
                self._log_safe(f"Título: {titulo} ({len(titulo)} chars)")

                def _apply():
                    self._titulo_entry.delete(0, "end")
                    self._titulo_entry.insert(0, titulo)
                    self._update_titulo_count()
                    self._set_processing(False, "Título generado")

                self.after(0, _apply)

            except Exception as e:
                self._log_safe(f"ERROR generando título: {e}")
                self.after(0, lambda: self._set_processing(False, f"Error: {e}"))

        threading.Thread(target=_worker, daemon=True).start()

    # ══════════════════════════════════════════════════════════════════════════
    # GENERAR DESCRIPCIÓN CON IA
    # ══════════════════════════════════════════════════════════════════════════

    def _generar_descripcion(self) -> None:
        if self._processing:
            return
        self._set_processing(True, "Generando descripción con Claude AI...")
        self._log.log("Generando descripción...")

        def _worker():
            try:
                from app.services.ia_generation import generar_descripcion
                datos = self._datos_item or {}
                producto_data = {
                    "nombre": datos.get("titulo", ""),
                    "categoria": datos.get("category_id", ""),
                    "precio": datos.get("precio", ""),
                    "descripcion": datos.get("descripcion", ""),
                    "fotos_count": len(datos.get("foto_urls", [])),
                    "titulo_ml": self._titulo_entry.get().strip(),
                }

                # Usar la primera foto descargada para Vision
                foto_path = None
                if self._fotos_descargadas:
                    foto_path = self._fotos_descargadas[0]
                    self._log_safe(f"Analizando foto para descripción: {foto_path.name}")

                descripcion = generar_descripcion("clon", producto_data, foto_path=foto_path)
                self._log_safe(f"Descripción generada ({len(descripcion)} chars)")

                def _apply():
                    self._desc_text.delete("1.0", "end")
                    self._desc_text.insert("1.0", descripcion)
                    self._set_processing(False, "Descripción generada")

                self.after(0, _apply)

            except Exception as e:
                self._log_safe(f"ERROR generando descripción: {e}")
                self.after(0, lambda: self._set_processing(False, f"Error: {e}"))

        threading.Thread(target=_worker, daemon=True).start()

    # ══════════════════════════════════════════════════════════════════════════
    # DRY-RUN
    # ══════════════════════════════════════════════════════════════════════════

    def _dryrun(self) -> None:
        """Muestra un resumen de lo que se publicaría sin ejecutar nada."""
        if self._processing:
            return

        self._log.log("\n═══ VISTA PREVIA (DRY-RUN) ═══")
        family_name = self._titulo_entry.get().strip()
        precio = self._get_precio()
        stock = self._get_stock()
        category = self._cat_entry.get().strip()
        usar_gemini = self._gemini_var.get()

        colores_sel = [c for c, v in self._color_vars.items() if v.get()]
        if not colores_sel:
            colores_sel = ["Blanco"]

        self._log.log(f"Family name: {family_name} ({len(family_name)} chars)")
        self._log.log(f"Categoría: {category}")
        self._log.log(f"Precio: ${precio:,.0f} ARS")
        self._log.log(f"Stock: {stock}")
        fotos_procesar = int(self._fotos_procesar_var.get() or str(len(self._fotos_descargadas)))
        hype_count = int(self._hype_var.get() or "0")
        self._log.log(f"Fotos a procesar: {fotos_procesar} de {len(self._fotos_descargadas)}")
        self._log.log(f"Gemini: {'Sí' if usar_gemini else 'No'}")
        self._log.log(f"Fotos con hype: {hype_count}")
        self._log.log(f"Colores: {', '.join(colores_sel)}")
        self._log.log(f"\nSe publicarían {len(colores_sel)} ítem(s):")
        for color in colores_sel:
            vid = COLORES_ML.get(color, "52055")
            self._log.log(f"  - {family_name} {color} (value_id={vid})")
        self._log.log("═══ FIN DRY-RUN ═══\n")

    # ══════════════════════════════════════════════════════════════════════════
    # PUBLICAR
    # ══════════════════════════════════════════════════════════════════════════

    def _publicar(self) -> None:
        if self._processing:
            return

        family_name = self._titulo_entry.get().strip()
        if not family_name:
            self._status_label.configure(text="Falta el family name", fg=theme.WARNING)
            return

        precio = self._get_precio()
        if not precio:
            self._status_label.configure(text="Falta el precio", fg=theme.WARNING)
            return

        colores_sel = [c for c, v in self._color_vars.items() if v.get()]
        if not colores_sel:
            self._status_label.configure(text="Seleccioná al menos un color", fg=theme.WARNING)
            return

        stock = self._get_stock()
        category = self._cat_entry.get().strip() or "MLA414192"
        descripcion = self._desc_text.get("1.0", "end").strip()
        usar_gemini = self._gemini_var.get()
        cantidad_hype = int(self._hype_var.get() or "0")
        fotos_procesar = int(self._fotos_procesar_var.get() or str(len(self._fotos_descargadas)))

        self._set_processing(True, "Publicando...")
        self._log.log("\n═══ PUBLICACIÓN EN CURSO ═══")
        self._log.log(f"Family name: {family_name}")
        self._log.log(f"Colores: {', '.join(colores_sel)}")

        def _worker():
            try:
                from app.services.ml_publisher import (
                    publish_item, upload_image, clean_description, build_family_name,
                    COLOR_VALUE_IDS,
                )

                fn = build_family_name(family_name)
                desc = clean_description(descripcion)

                # Paso 0: Tomar solo las primeras N fotos
                fotos_a_usar = list(self._fotos_descargadas[:fotos_procesar])
                self._log_safe(
                    f"Usando {len(fotos_a_usar)} de {len(self._fotos_descargadas)} fotos "
                    f"(primeras {len(fotos_a_usar)} en orden)"
                )
                if usar_gemini and fotos_a_usar:
                    self._log_safe(f"Procesando {len(fotos_a_usar)} fotos con Gemini (Nano Banana)...")
                    try:
                        from app.services.gemini_images import enhance_photos_batch
                        dest = fotos_a_usar[0].parent / "gemini"
                        results = enhance_photos_batch(
                            fotos_a_usar, dest,
                            callback=lambda msg: self._log_safe(f"  Gemini: {msg}"))
                        ok_count = sum(1 for r in results if r[1])
                        fallback_count = sum(1 for r in results if not r[1])
                        fotos_gemini = [r[0] for r in results if r[0].exists()]
                        if fotos_gemini:
                            fotos_a_usar = fotos_gemini
                            self._log_safe(
                                f"Gemini resultado: {ok_count} mejoradas, "
                                f"{fallback_count} fallback, {len(fotos_gemini)} totales")
                        else:
                            self._log_safe("Gemini no devolvió fotos válidas, usando originales")
                        for r in results:
                            if not r[1]:
                                self._log_safe(f"  Gemini fallback: {r[2]}")
                    except Exception as e:
                        import traceback
                        self._log_safe(f"Gemini error: {e}")
                        self._log_safe(f"  Detalle: {traceback.format_exc().splitlines()[-1]}")
                        self._log_safe("Usando fotos originales")
                elif usar_gemini and not fotos_a_usar:
                    self._log_safe("Gemini habilitado pero no hay fotos descargadas")

                # Paso 1.5: Agregar texto hype a algunas fotos
                if cantidad_hype > 0 and fotos_a_usar:
                    self._log_safe(f"Agregando texto hype a {cantidad_hype} de {len(fotos_a_usar)} fotos...")
                    try:
                        from app.services.gemini_images import add_hype_text_batch
                        datos = self._datos_item or {}
                        producto_info = {
                            "titulo": datos.get("titulo", ""),
                            "categoria": datos.get("category_id", ""),
                            "precio": datos.get("precio", 0),
                        }
                        hype_dest = fotos_a_usar[0].parent / "hype"
                        fotos_a_usar = add_hype_text_batch(
                            fotos_a_usar, cantidad_hype, producto_info, hype_dest,
                            callback=lambda msg: self._log_safe(f"  {msg}"))
                    except Exception as e:
                        self._log_safe(f"Hype error: {e} — continuando sin hype")

                # Paso 2: Subir fotos a ML
                self._log_safe(f"Subiendo {len(fotos_a_usar)} fotos a MercadoLibre...")
                picture_urls = []
                for i, foto in enumerate(fotos_a_usar, 1):
                    try:
                        url = upload_image(foto)
                        picture_urls.append(url)
                        self._log_safe(f"  Foto {i} subida OK")
                    except Exception as e:
                        self._log_safe(f"  Foto {i} ERROR: {e}")

                if not picture_urls:
                    self._log_safe("ERROR: No se pudo subir ninguna foto")
                    self.after(0, lambda: self._set_processing(False, "Error: sin fotos"))
                    return

                # Paso 3: Publicar cada color
                items_publicados = []
                for color in colores_sel:
                    color_vid = COLORES_ML.get(color, COLOR_VALUE_IDS.get(color, "52055"))
                    self._log_safe(f"\nPublicando color: {color} (value_id={color_vid})...")

                    try:
                        item = publish_item(
                            family_name=fn,
                            category_id=category,
                            precio=precio,
                            picture_urls=picture_urls,
                            descripcion=desc,
                            stock=stock,
                            color_name=color,
                            color_value_id=color_vid,
                        )
                        mla = item.get("id", "N/A")
                        permalink = item.get("permalink", "N/A")
                        self._log_safe(f"  PUBLICADO: {mla}")
                        self._log_safe(f"  URL: {permalink}")
                        items_publicados.append({
                            "mla": mla, "color": color, "permalink": permalink,
                            "titulo": item.get("title", ""),
                        })
                    except Exception as e:
                        self._log_safe(f"  ERROR publicando {color}: {e}")
                        items_publicados.append({
                            "mla": "ERROR", "color": color, "error": str(e),
                        })

                # Resumen final
                ok = [p for p in items_publicados if p["mla"] != "ERROR"]
                err = [p for p in items_publicados if p["mla"] == "ERROR"]

                self._log_safe("\n═══ RESUMEN ═══")
                for p in ok:
                    self._log_safe(
                        f"✅ Publicado: {p['mla']} — "
                        f"Color: {p['color']} — Precio: ${precio:,.0f}")
                for p in err:
                    self._log_safe(f"❌ Error {p['color']}: {p.get('error', '?')}")
                self._log_safe("═══ FIN ═══")

                # Mostrar resumen copiable en la UI
                resumen_lines = []
                for p in ok:
                    resumen_lines.append(
                        f"✅ Publicado: {p['mla']} — "
                        f"Color: {p['color']} — Precio: ${precio:,.0f}")
                for p in err:
                    resumen_lines.append(
                        f"❌ Error {p['color']}: {p.get('error', '?')}")
                resumen_text = "\n".join(resumen_lines)

                def _show_resumen():
                    self._set_processing(
                        False,
                        f"Publicados: {len(ok)} ítems" if ok else "Error en publicación")
                    if ok:
                        self._mostrar_resumen_copiable(resumen_text)

                self.after(0, _show_resumen)

            except Exception as e:
                self._log_safe(f"ERROR FATAL: {e}")
                self.after(0, lambda: self._set_processing(False, f"Error: {e}"))

        threading.Thread(target=_worker, daemon=True).start()

    # ══════════════════════════════════════════════════════════════════════════
    # RESUMEN COPIABLE
    # ══════════════════════════════════════════════════════════════════════════

    def _mostrar_resumen_copiable(self, texto: str) -> None:
        """Muestra un Text widget con el resumen de publicación, seleccionable/copiable."""
        logger.info("Mostrando resumen copiable: %s", texto[:80])

        # Insertar en scroll_frame directamente (después de config y log)
        card = tk.Frame(self._scroll_frame, bg=theme.BG_CARD, bd=1, relief="solid",
                        highlightbackground=theme.ACCENT, highlightthickness=2)
        card.pack(fill="x", pady=(8, 6))

        tk.Label(card, text="Publicaciones creadas (seleccioná para copiar)",
                 font=theme.FONT_BOLD, bg=theme.BG_CARD, fg=theme.ACCENT
                 ).pack(anchor="w", padx=12, pady=(8, 4))

        resumen_text = tk.Text(
            card, font=theme.FONT_NORMAL, bg=theme.BG_INPUT,
            fg=theme.TEXT_PRIMARY, relief="flat", bd=1, wrap="word",
            highlightbackground=theme.BORDER, highlightthickness=1)
        resumen_text.insert("1.0", texto)
        n_lines = texto.count("\n") + 1
        resumen_text.configure(height=min(n_lines + 1, 10), state="normal")
        resumen_text.pack(fill="x", padx=12, pady=(0, 8))

        # Select all on focus
        resumen_text.bind("<FocusIn>", lambda e: resumen_text.tag_add("sel", "1.0", "end"))

        # Forzar actualización del scroll y bajar al fondo
        self._scroll_frame.update_idletasks()
        self._main_canvas.configure(scrollregion=self._main_canvas.bbox("all"))
        self._main_canvas.yview_moveto(1.0)

    # ══════════════════════════════════════════════════════════════════════════
    # HELPERS
    # ══════════════════════════════════════════════════════════════════════════

    def _get_precio(self) -> float:
        try:
            return float(self._precio_entry.get().replace(",", "").replace(".", ""))
        except (ValueError, AttributeError):
            return 0

    def _get_stock(self) -> int:
        try:
            return int(self._stock_entry.get())
        except (ValueError, AttributeError):
            return 10

    def _set_processing(self, active: bool, msg: str = "") -> None:
        self._processing = active
        if msg:
            color = theme.INFO if active else (theme.SUCCESS if "Error" not in msg else theme.ERROR)
            self._status_label.configure(text=msg, fg=color)

        state = "disabled" if active else "normal"
        self._btn_analizar.configure(state=state)
        # Config buttons only exist after analysis
        for attr in ("_btn_gen_titulo", "_btn_gen_desc", "_btn_publicar", "_btn_dryrun"):
            btn = getattr(self, attr, None)
            if btn and btn.winfo_exists():
                btn.configure(state=state)

    def refresh(self) -> None:
        """Refresh hook para AppWindow."""
        pass
