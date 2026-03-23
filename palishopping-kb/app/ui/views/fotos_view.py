"""Vista de gestión de fotos — Pipeline A (con fondo) y B (sin fondo)."""

import logging
import threading
import tkinter as tk
from tkinter import ttk, filedialog
from pathlib import Path

from app.config import IMG_EXTENSIONS, PRODUCTOS_BASE
from app.models.catalogo import Catalogo
from app.services.foto_processing import (
    contar_fotos_por_subcarpeta,
    importar_fotos,
    listar_fotos,
    optimizar_para_gemini,
    procesar_fondo_blanco,
    agregar_texto,
)
from app.ui import theme
from app.ui.components.log_panel import LogPanel

logger = logging.getLogger(__name__)

SUBCARPETAS = ["originales", "procesadas", "con_fondo",
               "listas_gemini", "con_texto", "gemini"]


class FotosView(tk.Frame):
    """Vista de gestión de fotos con pipeline A/B y grilla de thumbnails."""

    def __init__(self, master: tk.Widget, catalogo: Catalogo, **kwargs):
        super().__init__(master, bg=theme.BG_PRIMARY, **kwargs)
        self.catalogo = catalogo
        self._sku_var = tk.StringVar()
        self._photo_refs: list = []  # prevent GC
        self._processing = False
        self._build()

    def _build(self) -> None:
        # ── Header ──────────────────────────────────────────────────────────
        header = tk.Frame(self, bg=theme.BG_PRIMARY)
        header.pack(fill="x", padx=20, pady=(20, 8))

        tk.Label(header, text="Fotos", font=theme.FONT_TITLE,
                 bg=theme.BG_PRIMARY, fg=theme.TEXT_PRIMARY).pack(side="left")

        # ── Selector de producto ────────────────────────────────────────────
        sel_frame = tk.Frame(self, bg=theme.BG_SECONDARY, bd=1, relief="solid",
                             highlightbackground=theme.BORDER, highlightthickness=1)
        sel_frame.pack(fill="x", padx=20, pady=(0, 6))

        tk.Label(sel_frame, text="Producto:", font=theme.FONT_BOLD,
                 bg=theme.BG_SECONDARY, fg=theme.TEXT_SECONDARY).pack(
            side="left", padx=(10, 4), pady=6)

        skus = self.catalogo.skus
        self._combo = ttk.Combobox(sel_frame, textvariable=self._sku_var,
                                    values=skus, state="readonly", width=30)
        self._combo.pack(side="left", padx=(0, 10), pady=6)
        self._combo.bind("<<ComboboxSelected>>", lambda e: self._on_sku_changed())

        if skus:
            self._combo.current(0)

        # Botón importar fotos
        tk.Button(
            sel_frame, text="Importar fotos", font=theme.FONT_NORMAL,
            bg=theme.BTN_INFO, fg="white", relief="flat", bd=0,
            padx=10, pady=2, cursor="hand2",
            command=self._importar_fotos,
        ).pack(side="left", padx=(0, 6), pady=6)

        # ── Contadores ──────────────────────────────────────────────────────
        self._counters_frame = tk.Frame(self, bg=theme.BG_PRIMARY)
        self._counters_frame.pack(fill="x", padx=20, pady=(0, 6))

        # ── Área principal: thumbnails + controles ──────────────────────────
        main_area = tk.Frame(self, bg=theme.BG_PRIMARY)
        main_area.pack(fill="both", expand=True, padx=20, pady=(0, 6))

        # Izquierda: thumbnails con tabs
        left = tk.Frame(main_area, bg=theme.BG_PRIMARY)
        left.pack(side="left", fill="both", expand=True)

        # Notebook para subcarpetas
        self._notebook = ttk.Notebook(left)
        self._notebook.pack(fill="both", expand=True)

        self._tab_canvases: dict[str, tk.Canvas] = {}
        self._tab_inners: dict[str, tk.Frame] = {}
        for sub in SUBCARPETAS:
            tab = tk.Frame(self._notebook, bg=theme.BG_CARD)
            self._notebook.add(tab, text=sub)

            canvas = tk.Canvas(tab, bg=theme.BG_CARD, highlightthickness=0)
            scrollbar = tk.Scrollbar(tab, orient="vertical", command=canvas.yview)
            inner = tk.Frame(canvas, bg=theme.BG_CARD)

            inner.bind("<Configure>",
                       lambda e, c=canvas: c.configure(scrollregion=c.bbox("all")))
            canvas.create_window((0, 0), window=inner, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)

            scrollbar.pack(side="right", fill="y")
            canvas.pack(fill="both", expand=True)

            self._tab_canvases[sub] = canvas
            self._tab_inners[sub] = inner

        # Derecha: controles de pipeline
        right = tk.Frame(main_area, bg=theme.BG_PRIMARY, width=200)
        right.pack(side="right", fill="y", padx=(10, 0))
        right.pack_propagate(False)

        self._build_pipeline_controls(right)

        # ── Log panel ───────────────────────────────────────────────────────
        self._log = LogPanel(self, height=5)
        self._log.pack(fill="x", padx=20, pady=(0, 10))

        # ── Status ──────────────────────────────────────────────────────────
        self._status_label = tk.Label(
            self, text="", font=theme.FONT_SMALL,
            bg=theme.BG_PRIMARY, fg=theme.TEXT_MUTED)
        self._status_label.pack(fill="x", padx=20)

        # Cargar datos iniciales
        if skus:
            self._on_sku_changed()

    def _build_pipeline_controls(self, parent: tk.Frame) -> None:
        """Construye los botones de pipeline en el panel derecho."""
        tk.Label(parent, text="Pipeline A", font=theme.FONT_SUBTITLE,
                 bg=theme.BG_PRIMARY, fg=theme.ACCENT).pack(
            anchor="w", pady=(10, 4))
        tk.Label(parent, text="(con fondo original)", font=theme.FONT_SMALL,
                 bg=theme.BG_PRIMARY, fg=theme.TEXT_MUTED).pack(anchor="w")

        tk.Button(
            parent, text="Optimizar → con_fondo",
            font=theme.FONT_NORMAL, bg=theme.BTN_SUCCESS, fg="white",
            relief="flat", bd=0, padx=8, pady=3, cursor="hand2",
            command=lambda: self._run_pipeline_a_optimize(),
        ).pack(fill="x", pady=(6, 2))

        tk.Button(
            parent, text="+ Texto → con_texto",
            font=theme.FONT_NORMAL, bg=theme.BTN_SUCCESS, fg="white",
            relief="flat", bd=0, padx=8, pady=3, cursor="hand2",
            command=lambda: self._show_texto_dialog("A"),
        ).pack(fill="x", pady=2)

        ttk.Separator(parent, orient="horizontal").pack(fill="x", pady=10)

        tk.Label(parent, text="Pipeline B", font=theme.FONT_SUBTITLE,
                 bg=theme.BG_PRIMARY, fg=theme.INFO).pack(
            anchor="w", pady=(0, 4))
        tk.Label(parent, text="(sin fondo / blanco)", font=theme.FONT_SMALL,
                 bg=theme.BG_PRIMARY, fg=theme.TEXT_MUTED).pack(anchor="w")

        tk.Button(
            parent, text="Quitar fondo → procesadas",
            font=theme.FONT_NORMAL, bg=theme.BTN_INFO, fg="white",
            relief="flat", bd=0, padx=8, pady=3, cursor="hand2",
            command=lambda: self._run_pipeline_b_rembg(),
        ).pack(fill="x", pady=(6, 2))

        tk.Button(
            parent, text="Optimizar → listas_gemini",
            font=theme.FONT_NORMAL, bg=theme.BTN_INFO, fg="white",
            relief="flat", bd=0, padx=8, pady=3, cursor="hand2",
            command=lambda: self._run_pipeline_b_optimize(),
        ).pack(fill="x", pady=2)

        tk.Button(
            parent, text="+ Texto → con_texto",
            font=theme.FONT_NORMAL, bg=theme.BTN_INFO, fg="white",
            relief="flat", bd=0, padx=8, pady=3, cursor="hand2",
            command=lambda: self._show_texto_dialog("B"),
        ).pack(fill="x", pady=2)

        ttk.Separator(parent, orient="horizontal").pack(fill="x", pady=10)

        # Botón abrir carpeta
        tk.Button(
            parent, text="Abrir carpeta", font=theme.FONT_SMALL,
            bg=theme.BG_SECONDARY, fg=theme.TEXT_PRIMARY, relief="solid", bd=1,
            padx=8, pady=2, cursor="hand2",
            command=self._abrir_carpeta,
        ).pack(fill="x", pady=2)

    # ── Selección de producto ───────────────────────────────────────────────

    def _get_fotos_dir(self) -> Path:
        return PRODUCTOS_BASE / self._sku_var.get() / "fotos"

    def _on_sku_changed(self) -> None:
        sku = self._sku_var.get()
        if not sku:
            return
        self._update_counters(sku)
        self._load_thumbnails(sku)

    def _update_counters(self, sku: str) -> None:
        for w in self._counters_frame.winfo_children():
            w.destroy()

        counts = contar_fotos_por_subcarpeta(sku)
        for sub, count in counts.items():
            color = theme.SUCCESS if count > 0 else theme.TEXT_MUTED
            lbl = tk.Label(
                self._counters_frame,
                text=f"{sub}: {count}",
                font=theme.FONT_SMALL,
                bg=theme.BG_PRIMARY, fg=color,
            )
            lbl.pack(side="left", padx=(0, 12))

    def _load_thumbnails(self, sku: str) -> None:
        """Carga thumbnails en cada pestaña."""
        from PIL import Image, ImageTk
        self._photo_refs.clear()
        base = PRODUCTOS_BASE / sku / "fotos"

        for sub in SUBCARPETAS:
            inner = self._tab_inners[sub]
            for w in inner.winfo_children():
                w.destroy()

            folder = base / sub
            if not folder.exists():
                tk.Label(inner, text="Carpeta vacía",
                         font=theme.FONT_SMALL, bg=theme.BG_CARD,
                         fg=theme.TEXT_MUTED).pack(padx=10, pady=20)
                continue

            fotos = sorted(
                f for f in folder.iterdir()
                if f.is_file() and f.suffix.lower() in IMG_EXTENSIONS
            )

            if not fotos:
                tk.Label(inner, text="Sin fotos",
                         font=theme.FONT_SMALL, bg=theme.BG_CARD,
                         fg=theme.TEXT_MUTED).pack(padx=10, pady=20)
                continue

            for i, foto in enumerate(fotos):
                try:
                    img = Image.open(foto)
                    img.thumbnail((110, 110), Image.LANCZOS)
                    photo = ImageTk.PhotoImage(img)
                    self._photo_refs.append(photo)

                    cell = tk.Frame(inner, bg=theme.BG_CARD)
                    cell.grid(row=i // 6, column=i % 6, padx=3, pady=3)

                    tk.Label(cell, image=photo, bg=theme.BG_CARD,
                             bd=1, relief="solid").pack()
                    tk.Label(cell, text=foto.name, font=("Arial", 7),
                             bg=theme.BG_CARD, fg=theme.TEXT_MUTED).pack()
                    size_kb = foto.stat().st_size // 1024
                    tk.Label(cell, text=f"{size_kb} KB", font=("Arial", 7),
                             bg=theme.BG_CARD, fg=theme.TEXT_MUTED).pack()
                except Exception:
                    pass

    # ── Importar fotos ──────────────────────────────────────────────────────

    def _importar_fotos(self) -> None:
        sku = self._sku_var.get()
        if not sku:
            return

        archivos = filedialog.askopenfilenames(
            title="Seleccionar fotos para importar",
            filetypes=[
                ("Imágenes", "*.jpg *.jpeg *.png *.webp"),
                ("Todos", "*.*"),
            ],
        )

        if not archivos:
            return

        paths = [Path(f) for f in archivos]
        dir_orig = PRODUCTOS_BASE / sku / "fotos" / "originales"
        resultados = importar_fotos(paths, dir_orig)

        self._log.clear()
        for r in resultados:
            self._log.log(r)

        ok = sum(1 for r in resultados if r.startswith("OK"))
        self._status_label.configure(
            text=f"{ok} foto(s) importadas a {sku}/fotos/originales/",
            fg=theme.SUCCESS)
        self._on_sku_changed()

    # ── Pipeline A: con fondo ───────────────────────────────────────────────

    def _run_pipeline_a_optimize(self) -> None:
        """Pipeline A: originales → con_fondo (optimizar con fondo original)."""
        if self._processing:
            return
        sku = self._sku_var.get()
        if not sku:
            return

        dir_orig = PRODUCTOS_BASE / sku / "fotos" / "originales"
        dir_dest = PRODUCTOS_BASE / sku / "fotos" / "con_fondo"
        fotos = listar_fotos(dir_orig)

        if not fotos:
            self._status_label.configure(
                text="No hay fotos en originales/", fg=theme.WARNING)
            return

        self._start_processing(
            f"Pipeline A: optimizando {len(fotos)} foto(s)...",
            optimizar_para_gemini, fotos, dir_dest)

    # ── Pipeline B: sin fondo ───────────────────────────────────────────────

    def _run_pipeline_b_rembg(self) -> None:
        """Pipeline B paso 1: originales → procesadas (quitar fondo)."""
        if self._processing:
            return
        sku = self._sku_var.get()
        if not sku:
            return

        dir_orig = PRODUCTOS_BASE / sku / "fotos" / "originales"
        dir_proc = PRODUCTOS_BASE / sku / "fotos" / "procesadas"
        fotos = listar_fotos(dir_orig)

        if not fotos:
            self._status_label.configure(
                text="No hay fotos en originales/", fg=theme.WARNING)
            return

        self._start_processing(
            f"Pipeline B: procesando {len(fotos)} foto(s) (quitar fondo)...",
            procesar_fondo_blanco, fotos, dir_proc)

    def _run_pipeline_b_optimize(self) -> None:
        """Pipeline B paso 2: procesadas → listas_gemini."""
        if self._processing:
            return
        sku = self._sku_var.get()
        if not sku:
            return

        dir_proc = PRODUCTOS_BASE / sku / "fotos" / "procesadas"
        dir_gemini = PRODUCTOS_BASE / sku / "fotos" / "listas_gemini"
        fotos = listar_fotos(dir_proc)

        if not fotos:
            self._status_label.configure(
                text="No hay fotos en procesadas/. Ejecutá primero 'Quitar fondo'.",
                fg=theme.WARNING)
            return

        self._start_processing(
            f"Pipeline B: optimizando {len(fotos)} foto(s) para Gemini...",
            optimizar_para_gemini, fotos, dir_gemini)

    # ── Texto overlay ───────────────────────────────────────────────────────

    def _show_texto_dialog(self, pipeline: str) -> None:
        """Abre diálogo para pedir precio y specs antes de agregar texto."""
        if self._processing:
            return
        sku = self._sku_var.get()
        if not sku:
            return

        if pipeline == "A":
            dir_src = PRODUCTOS_BASE / sku / "fotos" / "con_fondo"
            sufijo = "_confondo"
            src_name = "con_fondo"
        else:
            dir_src = PRODUCTOS_BASE / sku / "fotos" / "listas_gemini"
            sufijo = "_sinfondo"
            src_name = "listas_gemini"

        fotos = listar_fotos(dir_src)
        if not fotos:
            self._status_label.configure(
                text=f"No hay fotos en {src_name}/. Ejecutá el paso anterior.",
                fg=theme.WARNING)
            return

        # Diálogo modal
        dialog = tk.Toplevel(self)
        dialog.title(f"Texto — Pipeline {pipeline}")
        dialog.geometry("400x200")
        dialog.configure(bg=theme.BG_PRIMARY)
        dialog.resizable(False, False)
        dialog.transient(self.winfo_toplevel())
        dialog.after(50, lambda: dialog.grab_set())

        tk.Label(dialog, text="Precio:", font=theme.FONT_BOLD,
                 bg=theme.BG_PRIMARY, fg=theme.TEXT_SECONDARY).pack(
            anchor="w", padx=20, pady=(16, 2))
        precio_var = tk.StringVar(value="$0")
        ttk.Entry(dialog, textvariable=precio_var, width=30).pack(
            padx=20, anchor="w")

        tk.Label(dialog, text="Especificaciones:", font=theme.FONT_BOLD,
                 bg=theme.BG_PRIMARY, fg=theme.TEXT_SECONDARY).pack(
            anchor="w", padx=20, pady=(8, 2))
        specs_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=specs_var, width=40).pack(
            padx=20, anchor="w")

        def _aplicar():
            precio = precio_var.get().strip() or "$0"
            specs = specs_var.get().strip()
            dialog.destroy()

            dir_texto = PRODUCTOS_BASE / sku / "fotos" / "con_texto"
            self._start_processing(
                f"Agregando texto a {len(fotos)} foto(s)...",
                agregar_texto, fotos, dir_texto, precio, specs, sufijo)

        btn_frame = tk.Frame(dialog, bg=theme.BG_PRIMARY)
        btn_frame.pack(pady=16)
        tk.Button(btn_frame, text="Aplicar", font=theme.FONT_BOLD,
                  bg=theme.BTN_SUCCESS, fg="white", relief="flat", bd=0,
                  padx=14, pady=4, cursor="hand2", command=_aplicar
                  ).pack(side="left", padx=4)
        tk.Button(btn_frame, text="Cancelar", font=theme.FONT_NORMAL,
                  bg=theme.BG_SECONDARY, fg=theme.TEXT_PRIMARY, relief="solid",
                  bd=1, padx=14, pady=4, cursor="hand2",
                  command=dialog.destroy).pack(side="left", padx=4)

    # ── Ejecución en thread ─────────────────────────────────────────────────

    def _start_processing(self, status_msg: str, func, *args) -> None:
        """Ejecuta func(*args) en un thread separado con feedback."""
        self._processing = True
        self._log.clear()
        self._status_label.configure(text=status_msg, fg=theme.INFO)
        self.update()

        def _callback(msg):
            self.after(0, lambda m=msg: self._log.log(m))

        def _worker():
            try:
                # Reemplazar el último argumento si es el sufijo con callback al final
                all_args = list(args)
                result = func(*all_args, callback=_callback)
                n_ok = result[0] if isinstance(result, tuple) else 0
                self.after(0, lambda: self._on_processing_done(n_ok))
            except Exception as e:
                self.after(0, lambda: self._on_processing_error(str(e)))

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()

    def _on_processing_done(self, n_ok: int) -> None:
        self._processing = False
        self._status_label.configure(
            text=f"Listo: {n_ok} foto(s) procesadas", fg=theme.SUCCESS)
        self._on_sku_changed()

    def _on_processing_error(self, error: str) -> None:
        self._processing = False
        self._status_label.configure(text=f"Error: {error}", fg=theme.ERROR)
        self._log.log(f"ERROR: {error}")

    # ── Abrir carpeta ───────────────────────────────────────────────────────

    def _abrir_carpeta(self) -> None:
        sku = self._sku_var.get()
        if not sku:
            return
        import subprocess
        folder = PRODUCTOS_BASE / sku / "fotos"
        try:
            subprocess.Popen(["xdg-open", str(folder)])
        except Exception:
            self._status_label.configure(
                text=f"No se pudo abrir {folder}", fg=theme.WARNING)

    # ── Refresh ─────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        self.catalogo.reload()
        skus = self.catalogo.skus
        self._combo.configure(values=skus)
        if skus and not self._sku_var.get():
            self._combo.current(0)
        self._on_sku_changed()
