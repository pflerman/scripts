"""Vista de gestión de bundles — Tkinter puro con Treeview + CRUD."""

import logging
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable

from app.config import MARGEN
from app.models.bundle import Bundle, BundleItem, BundleManager
from app.models.catalogo import Catalogo
from app.ui import theme
from app.utils.file_helpers import slugify

logger = logging.getLogger(__name__)

COLUMNS = ("nombre", "productos", "costo", "sugerido", "final")
HEADINGS = {"nombre": "Nombre", "productos": "Productos",
            "costo": "Costo Total", "sugerido": "Sugerido", "final": "Precio Final"}
WIDTHS = {"nombre": 250, "productos": 80, "costo": 120,
          "sugerido": 120, "final": 120}
ANCHORS = {"nombre": "w", "productos": "center",
           "costo": "e", "sugerido": "e", "final": "e"}


class BundlesView(tk.Frame):
    """Vista principal de bundles: Treeview + CRUD."""

    def __init__(self, master: tk.Widget, bundles: BundleManager,
                 catalogo: Catalogo, **kwargs):
        super().__init__(master, bg=theme.BG_PRIMARY, **kwargs)
        self.bundles = bundles
        self.catalogo = catalogo
        self._item_to_bundle: dict[str, Bundle] = {}
        self._build()

    def _build(self) -> None:
        # ── Header ──────────────────────────────────────────────────────────
        header = tk.Frame(self, bg=theme.BG_PRIMARY)
        header.pack(fill="x", padx=20, pady=(20, 8))

        tk.Label(header, text="Bundles", font=theme.FONT_TITLE,
                 bg=theme.BG_PRIMARY, fg=theme.TEXT_PRIMARY).pack(side="left")

        tk.Button(
            header, text="+ Nuevo bundle", font=theme.FONT_BOLD,
            bg=theme.BTN_SUCCESS, fg="white", relief="flat", bd=0,
            padx=14, pady=4, cursor="hand2",
            command=self._show_create_form,
        ).pack(side="right")

        # ── Count ───────────────────────────────────────────────────────────
        self._count_label = tk.Label(
            self, text="", font=theme.FONT_NORMAL,
            bg=theme.BG_PRIMARY, fg=theme.COUNT_LABEL_COLOR,
        )
        self._count_label.pack(anchor="e", padx=20, pady=(0, 4))

        # ── Treeview ────────────────────────────────────────────────────────
        table_frame = tk.Frame(self, bg=theme.BG_PRIMARY)
        table_frame.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        vsb = ttk.Scrollbar(table_frame, orient="vertical")
        vsb.pack(side="right", fill="y")

        self.tree = ttk.Treeview(
            table_frame, columns=COLUMNS, show="headings",
            yscrollcommand=vsb.set, height=15,
        )
        self.tree.pack(fill="both", expand=True)
        vsb.config(command=self.tree.yview)

        for col in COLUMNS:
            self.tree.heading(col, text=HEADINGS[col])
            self.tree.column(col, width=WIDTHS[col], anchor=ANCHORS[col])

        self.tree.tag_configure("even", background=theme.TAG_EVEN)
        self.tree.tag_configure("odd", background=theme.TAG_ODD)

        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<Return>", self._on_double_click)

        self._populate_tree()

    def _populate_tree(self) -> None:
        self.tree.delete(*self.tree.get_children())
        self._item_to_bundle.clear()
        bundles = self.bundles.bundles

        self._count_label.configure(text=f"{len(bundles)} bundle(s)")

        for i, bundle in enumerate(bundles):
            tag = "even" if i % 2 == 0 else "odd"
            item_id = self.tree.insert("", "end", values=(
                bundle.nombre,
                str(len(bundle.productos)),
                f"${bundle.precio_costo_total:,.0f}",
                f"${bundle.precio_venta_sugerido:,.0f}",
                f"${bundle.precio_venta_final:,.0f}",
            ), tags=(tag,))
            self._item_to_bundle[item_id] = bundle

    def _on_double_click(self, event: tk.Event) -> None:
        sel = self.tree.selection()
        if sel:
            bundle = self._item_to_bundle.get(sel[0])
            if bundle:
                self._show_edit_form(bundle)

    def _show_create_form(self) -> None:
        BundleForm(self, self.bundles, self.catalogo,
                   on_saved=self._on_saved)

    def _show_edit_form(self, bundle: Bundle) -> None:
        BundleForm(self, self.bundles, self.catalogo,
                   bundle=bundle, on_saved=self._on_saved)

    def _on_saved(self) -> None:
        self.bundles.reload()
        self._populate_tree()

    def refresh(self) -> None:
        self.bundles.reload()
        self.catalogo.reload()
        self._populate_tree()


class BundleForm(tk.Toplevel):
    """Formulario modal para crear o editar un bundle."""

    def __init__(self, master: tk.Widget, bundles: BundleManager,
                 catalogo: Catalogo, bundle: Bundle | None = None,
                 on_saved: Callable | None = None):
        super().__init__(master)
        self.bundles_mgr = bundles
        self.catalogo = catalogo
        self._bundle = bundle
        self._on_saved = on_saved
        self._editing = bundle is not None
        self._items: list[tuple[str, int]] = []  # (sku, cantidad)

        if self._editing:
            self._items = [(item.sku, item.cantidad) for item in bundle.productos]

        self.title(f"Editar: {bundle.nombre}" if self._editing else "Nuevo Bundle")
        self.geometry("580x600")
        self.configure(bg=theme.BG_PRIMARY)
        self.resizable(False, True)
        self.transient(master.winfo_toplevel())
        self.after(50, self._delayed_grab)
        self._build()

    def _delayed_grab(self) -> None:
        try:
            self.grab_set()
        except tk.TclError:
            pass

    def _build(self) -> None:
        f = tk.Frame(self, bg=theme.BG_PRIMARY)
        f.pack(fill="both", expand=True, padx=16, pady=16)

        # Nombre
        tk.Label(f, text="Nombre del bundle:", font=theme.FONT_BOLD,
                 bg=theme.BG_PRIMARY, fg=theme.TEXT_SECONDARY).pack(anchor="w")
        self._nombre_var = tk.StringVar(
            value=self._bundle.nombre if self._editing else "")
        ttk.Entry(f, textvariable=self._nombre_var, width=50).pack(
            fill="x", pady=(2, 10))

        # ── Agregar productos ───────────────────────────────────────────────
        tk.Label(f, text="Productos en el bundle:", font=theme.FONT_BOLD,
                 bg=theme.BG_PRIMARY, fg=theme.TEXT_SECONDARY).pack(anchor="w")

        add_frame = tk.Frame(f, bg=theme.BG_PRIMARY)
        add_frame.pack(fill="x", pady=(2, 4))

        skus = self.catalogo.skus
        self._add_sku_var = tk.StringVar()
        self._add_combo = ttk.Combobox(add_frame, textvariable=self._add_sku_var,
                                        values=skus, state="readonly", width=28)
        self._add_combo.pack(side="left")
        if skus:
            self._add_combo.current(0)

        tk.Label(add_frame, text="Cant:", font=theme.FONT_NORMAL,
                 bg=theme.BG_PRIMARY, fg=theme.TEXT_SECONDARY).pack(
            side="left", padx=(8, 2))
        self._add_cant_var = tk.StringVar(value="1")
        ttk.Entry(add_frame, textvariable=self._add_cant_var, width=5).pack(
            side="left")

        tk.Button(
            add_frame, text="Agregar", font=theme.FONT_NORMAL,
            bg=theme.BTN_INFO, fg="white", relief="flat", bd=0,
            padx=10, pady=2, cursor="hand2", command=self._add_item,
        ).pack(side="left", padx=(8, 0))

        # Lista de items
        items_frame = tk.Frame(f, bg=theme.BG_PRIMARY)
        items_frame.pack(fill="both", expand=True, pady=(4, 8))

        self._items_tree = ttk.Treeview(
            items_frame, columns=("sku", "nombre", "cant", "costo"),
            show="headings", height=6)
        self._items_tree.pack(fill="both", expand=True)

        self._items_tree.heading("sku", text="SKU")
        self._items_tree.heading("nombre", text="Nombre")
        self._items_tree.heading("cant", text="Cant")
        self._items_tree.heading("costo", text="Costo unit")
        self._items_tree.column("sku", width=160, anchor="w")
        self._items_tree.column("nombre", width=200, anchor="w")
        self._items_tree.column("cant", width=50, anchor="center")
        self._items_tree.column("costo", width=90, anchor="e")

        tk.Button(
            f, text="Quitar seleccionado", font=theme.FONT_SMALL,
            bg=theme.BTN_DANGER, fg="white", relief="flat", bd=0,
            padx=8, pady=2, cursor="hand2", command=self._remove_item,
        ).pack(anchor="w", pady=(0, 8))

        # ── Resumen de costos ───────────────────────────────────────────────
        cost_frame = tk.Frame(f, bg=theme.BG_SECONDARY, bd=1, relief="solid")
        cost_frame.pack(fill="x", pady=(0, 8))

        self._costo_label = tk.Label(
            cost_frame, text="Costo total: $0", font=theme.FONT_BOLD,
            bg=theme.BG_SECONDARY, fg=theme.TEXT_PRIMARY)
        self._costo_label.pack(side="left", padx=10, pady=6)

        self._sugerido_label = tk.Label(
            cost_frame, text=f"Sugerido (x{MARGEN}): $0", font=theme.FONT_NORMAL,
            bg=theme.BG_SECONDARY, fg=theme.ACCENT)
        self._sugerido_label.pack(side="left", padx=10, pady=6)

        # Precio final
        precio_row = tk.Frame(f, bg=theme.BG_PRIMARY)
        precio_row.pack(fill="x", pady=(0, 8))
        tk.Label(precio_row, text="Precio final:", font=theme.FONT_BOLD,
                 bg=theme.BG_PRIMARY, fg=theme.TEXT_SECONDARY).pack(side="left")
        default_final = str(self._bundle.precio_venta_final) if self._editing else "0"
        self._precio_var = tk.StringVar(value=default_final)
        ttk.Entry(precio_row, textvariable=self._precio_var, width=12).pack(
            side="left", padx=(8, 0))

        # ── Status + botones ────────────────────────────────────────────────
        self._status_label = tk.Label(
            f, text="", font=theme.FONT_NORMAL,
            bg=theme.BG_PRIMARY, fg=theme.TEXT_MUTED)
        self._status_label.pack(fill="x", pady=4)

        btn_row = tk.Frame(f, bg=theme.BG_PRIMARY)
        btn_row.pack(fill="x", pady=(4, 0))

        action_text = "Guardar cambios" if self._editing else "Crear bundle"
        tk.Button(
            btn_row, text=action_text, font=theme.FONT_BOLD,
            bg=theme.BTN_SUCCESS, fg="white", relief="flat", bd=0,
            padx=14, pady=4, cursor="hand2", command=self._save,
        ).pack(side="left", padx=(0, 8))

        tk.Button(
            btn_row, text="Cancelar", font=theme.FONT_NORMAL,
            bg=theme.BG_SECONDARY, fg=theme.TEXT_PRIMARY, relief="solid", bd=1,
            padx=14, pady=4, cursor="hand2", command=self.destroy,
        ).pack(side="left")

        if self._editing:
            tk.Button(
                btn_row, text="Eliminar", font=theme.FONT_BOLD,
                bg=theme.BTN_DANGER, fg="white", relief="flat", bd=0,
                padx=14, pady=4, cursor="hand2", command=self._delete,
            ).pack(side="right")

        self._refresh_items_list()

    def _add_item(self) -> None:
        sku = self._add_sku_var.get()
        if not sku:
            return
        try:
            cant = int(self._add_cant_var.get())
            if cant < 1:
                cant = 1
        except ValueError:
            cant = 1

        # Check if already exists, update quantity
        for i, (s, c) in enumerate(self._items):
            if s == sku:
                self._items[i] = (sku, c + cant)
                self._refresh_items_list()
                return

        self._items.append((sku, cant))
        self._refresh_items_list()

    def _remove_item(self) -> None:
        sel = self._items_tree.selection()
        if not sel:
            return
        idx = self._items_tree.index(sel[0])
        if 0 <= idx < len(self._items):
            self._items.pop(idx)
            self._refresh_items_list()

    def _refresh_items_list(self) -> None:
        self._items_tree.delete(*self._items_tree.get_children())
        costo_total = 0.0

        for sku, cant in self._items:
            prod = self.catalogo.get(sku)
            nombre = prod.nombre if prod else "?"
            costo = prod.precio_costo if prod else 0.0
            self._items_tree.insert("", "end", values=(
                sku, nombre, str(cant), f"${costo:,.0f}"))
            costo_total += costo * cant

        sugerido = round(costo_total * MARGEN)
        self._costo_label.configure(text=f"Costo total: ${costo_total:,.0f}")
        self._sugerido_label.configure(
            text=f"Sugerido (x{MARGEN}): ${sugerido:,.0f}")

        # Auto-fill precio final si está vacío o es 0
        if self._precio_var.get() in ("", "0"):
            self._precio_var.set(str(sugerido))

    def _save(self) -> None:
        nombre = self._nombre_var.get().strip()
        if not nombre:
            self._status_label.configure(
                text="El nombre es obligatorio", fg=theme.ERROR)
            return

        if not self._items:
            self._status_label.configure(
                text="Agregá al menos un producto", fg=theme.ERROR)
            return

        try:
            precio_final = int(self._precio_var.get().replace(".", "").replace(",", ""))
        except ValueError:
            self._status_label.configure(
                text="Precio final inválido", fg=theme.ERROR)
            return

        # Build items list: (sku, cantidad, precio_costo_unitario)
        items_data = []
        for sku, cant in self._items:
            prod = self.catalogo.get(sku)
            costo = prod.precio_costo if prod else 0.0
            items_data.append((sku, cant, costo))

        if self._editing:
            # Update existing: delete old, create new with same slug
            old_path = self._bundle.json_path
            if old_path.exists():
                old_path.unlink()

        try:
            bundle = self.bundles_mgr.crear_bundle(
                nombre=nombre,
                items=items_data,
                precio_final=precio_final,
            )
            self._status_label.configure(
                text=f"Bundle '{bundle.nombre}' guardado", fg=theme.SUCCESS)
            if self._on_saved:
                self._on_saved()
            self.after(800, self.destroy)
        except Exception as e:
            self._status_label.configure(text=f"Error: {e}", fg=theme.ERROR)

    def _delete(self) -> None:
        if not messagebox.askyesno(
            "Eliminar bundle",
            f"¿Eliminar bundle '{self._bundle.nombre}'?",
            parent=self,
        ):
            return

        path = self._bundle.json_path
        if path.exists():
            path.unlink()
        self._status_label.configure(text="Bundle eliminado", fg=theme.SUCCESS)
        if self._on_saved:
            self._on_saved()
        self.after(800, self.destroy)
