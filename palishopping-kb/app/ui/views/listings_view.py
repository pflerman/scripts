"""Vista de gestión de listings/drafts — Tkinter puro con Treeview + CRUD."""

import logging
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from typing import Callable

from app.models.bundle import BundleManager
from app.models.catalogo import Catalogo
from app.models.listing import Listing, ListingManager
from app.ui import theme
from app.utils.file_helpers import slugify

logger = logging.getLogger(__name__)

COLUMNS = ("titulo", "bundle", "precio", "stock", "estado")
HEADINGS = {"titulo": "Título", "bundle": "Bundle", "precio": "Precio",
            "stock": "Stock", "estado": "Estado"}
WIDTHS = {"titulo": 300, "bundle": 150, "precio": 110,
          "stock": 70, "estado": 100}
ANCHORS = {"titulo": "w", "bundle": "w", "precio": "e",
           "stock": "e", "estado": "center"}

ESTADOS = ["draft", "ready", "published"]
ESTADO_COLORS = {"draft": theme.TEXT_MUTED, "ready": theme.WARNING,
                 "published": theme.SUCCESS}


class ListingsView(tk.Frame):
    """Vista principal de listings: Treeview + CRUD."""

    def __init__(self, master: tk.Widget, listings: ListingManager,
                 bundles: BundleManager, catalogo: Catalogo, **kwargs):
        super().__init__(master, bg=theme.BG_PRIMARY, **kwargs)
        self.listings = listings
        self.bundles = bundles
        self.catalogo = catalogo
        self._item_to_listing: dict[str, Listing] = {}
        self._build()

    def _build(self) -> None:
        # ── Header ──────────────────────────────────────────────────────────
        header = tk.Frame(self, bg=theme.BG_PRIMARY)
        header.pack(fill="x", padx=20, pady=(20, 8))

        tk.Label(header, text="Listings", font=theme.FONT_TITLE,
                 bg=theme.BG_PRIMARY, fg=theme.TEXT_PRIMARY).pack(side="left")

        tk.Button(
            header, text="+ Nuevo listing", font=theme.FONT_BOLD,
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
        self._item_to_listing.clear()
        listings = self.listings.listings

        self._count_label.configure(text=f"{len(listings)} listing(s)")

        for i, listing in enumerate(listings):
            tag = "even" if i % 2 == 0 else "odd"
            item_id = self.tree.insert("", "end", values=(
                listing.titulo or listing.slug,
                listing.bundle or "—",
                f"${listing.precio:,.0f}",
                str(listing.stock),
                listing.estado,
            ), tags=(tag,))
            self._item_to_listing[item_id] = listing

    def _on_double_click(self, event: tk.Event) -> None:
        sel = self.tree.selection()
        if sel:
            listing = self._item_to_listing.get(sel[0])
            if listing:
                self._show_edit_form(listing)

    def _show_create_form(self) -> None:
        ListingForm(self, self.listings, self.bundles, self.catalogo,
                    on_saved=self._on_saved)

    def _show_edit_form(self, listing: Listing) -> None:
        ListingForm(self, self.listings, self.bundles, self.catalogo,
                    listing=listing, on_saved=self._on_saved)

    def _on_saved(self) -> None:
        self.listings.reload()
        self._populate_tree()

    def refresh(self) -> None:
        self.listings.reload()
        self.bundles.reload()
        self.catalogo.reload()
        self._populate_tree()


class ListingForm(tk.Toplevel):
    """Formulario modal para crear o editar un listing."""

    def __init__(self, master: tk.Widget, listings: ListingManager,
                 bundles: BundleManager, catalogo: Catalogo,
                 listing: Listing | None = None,
                 on_saved: Callable | None = None):
        super().__init__(master)
        self.listings_mgr = listings
        self.bundles_mgr = bundles
        self.catalogo = catalogo
        self._listing = listing
        self._on_saved = on_saved
        self._editing = listing is not None

        self.title(f"Editar: {listing.slug}" if self._editing else "Nuevo Listing")
        self.geometry("560x620")
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
        canvas = tk.Canvas(self, bg=theme.BG_PRIMARY, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        form = tk.Frame(canvas, bg=theme.BG_PRIMARY)

        form.bind("<Configure>",
                  lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=form, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True, padx=12, pady=12)

        f = form
        ls = self._listing

        # ── Bundle selector (solo creación) ─────────────────────────────────
        if not self._editing:
            bundle_names = [b.nombre for b in self.bundles_mgr.bundles]
            self._bundle_var = self._add_combo(
                f, "Bundle base", bundle_names,
                default=None)
            self._bundle_var.trace_add("write", lambda *_: self._on_bundle_changed())
        else:
            # Show bundle info
            info_frame = tk.Frame(f, bg=theme.BG_SECONDARY, bd=1, relief="solid")
            info_frame.pack(fill="x", pady=(0, 8))
            tk.Label(info_frame, text=f"Slug: {ls.slug}", font=theme.FONT_BOLD,
                     bg=theme.BG_SECONDARY, fg=theme.ACCENT).pack(padx=12, pady=3)
            tk.Label(info_frame, text=f"Bundle: {ls.bundle}",
                     font=theme.FONT_SMALL,
                     bg=theme.BG_SECONDARY, fg=theme.TEXT_SECONDARY).pack(
                padx=12, pady=(0, 3))

        # Título
        self._titulo_var = self._add_field(
            f, "Título ML *", default=ls.titulo if ls else "")

        # Precio
        self._precio_var = self._add_field(
            f, "Precio *", default=str(ls.precio) if ls else "0")

        # Stock
        self._stock_var = self._add_field(
            f, "Stock", default=str(ls.stock) if ls else "0")

        # Estado
        self._estado_var = self._add_combo(
            f, "Estado", ESTADOS,
            default=ls.estado if ls else "draft")

        # Descripción
        desc_row = tk.Frame(f, bg=theme.BG_PRIMARY)
        desc_row.pack(fill="x", pady=3)
        tk.Label(desc_row, text="Descripción", font=theme.FONT_BOLD,
                 bg=theme.BG_PRIMARY, fg=theme.TEXT_SECONDARY,
                 width=14, anchor="ne").pack(side="left", padx=(0, 8), anchor="n")
        self._desc_text = tk.Text(
            desc_row, height=8, width=35, font=theme.FONT_NORMAL,
            bg=theme.BG_INPUT, fg=theme.TEXT_PRIMARY, relief="solid",
            bd=1, wrap="word")
        self._desc_text.pack(side="left", fill="x", expand=True)
        if ls and ls.descripcion:
            self._desc_text.insert("1.0", ls.descripcion)

        # ── Status ──────────────────────────────────────────────────────────
        self._status_label = tk.Label(
            f, text="", font=theme.FONT_NORMAL,
            bg=theme.BG_PRIMARY, fg=theme.TEXT_MUTED)
        self._status_label.pack(fill="x", pady=4)

        # ── Botones ─────────────────────────────────────────────────────────
        btn_row = tk.Frame(f, bg=theme.BG_PRIMARY)
        btn_row.pack(fill="x", pady=(6, 4))

        action_text = "Guardar cambios" if self._editing else "Crear listing"
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

    def _add_field(self, parent, label, default=""):
        row = tk.Frame(parent, bg=theme.BG_PRIMARY)
        row.pack(fill="x", pady=3)
        tk.Label(row, text=label, font=theme.FONT_BOLD,
                 bg=theme.BG_PRIMARY, fg=theme.TEXT_SECONDARY,
                 width=14, anchor="e").pack(side="left", padx=(0, 8))
        var = tk.StringVar(value=default)
        ttk.Entry(row, textvariable=var, width=30).pack(
            side="left", fill="x", expand=True)
        return var

    def _add_combo(self, parent, label, values, default=None):
        row = tk.Frame(parent, bg=theme.BG_PRIMARY)
        row.pack(fill="x", pady=3)
        tk.Label(row, text=label, font=theme.FONT_BOLD,
                 bg=theme.BG_PRIMARY, fg=theme.TEXT_SECONDARY,
                 width=14, anchor="e").pack(side="left", padx=(0, 8))
        var = tk.StringVar()
        combo = ttk.Combobox(row, textvariable=var, values=values,
                             state="readonly", width=28)
        combo.pack(side="left", fill="x", expand=True)
        if default and default in values:
            combo.set(default)
        elif values:
            combo.current(0)
        return var

    def _on_bundle_changed(self) -> None:
        """Auto-fill fields from selected bundle."""
        bundle_nombre = self._bundle_var.get()
        bundle = None
        for b in self.bundles_mgr.bundles:
            if b.nombre == bundle_nombre:
                bundle = b
                break
        if not bundle:
            return

        # Auto-fill precio from bundle
        self._precio_var.set(str(bundle.precio_venta_final))

        # Try to get titulo from first product in bundle
        if bundle.productos:
            prod = self.catalogo.get(bundle.productos[0].sku)
            if prod and prod.titulo_ml:
                self._titulo_var.set(prod.titulo_ml)
            if prod and prod.descripcion:
                self._desc_text.delete("1.0", "end")
                self._desc_text.insert("1.0", prod.descripcion)

    def _save(self) -> None:
        titulo = self._titulo_var.get().strip()
        if not titulo:
            self._status_label.configure(
                text="El título es obligatorio", fg=theme.ERROR)
            return

        try:
            precio = int(self._precio_var.get().replace(".", "").replace(",", ""))
        except ValueError:
            self._status_label.configure(
                text="Precio inválido", fg=theme.ERROR)
            return

        try:
            stock = int(self._stock_var.get())
        except ValueError:
            stock = 0

        estado = self._estado_var.get()
        descripcion = self._desc_text.get("1.0", "end-1c").strip()

        if self._editing:
            ls = self._listing
            ls.titulo = titulo
            ls.precio = precio
            ls.stock = stock
            ls.estado = estado
            ls.descripcion = descripcion
            ls.save()
            self._status_label.configure(
                text=f"Listing '{ls.slug}' actualizado", fg=theme.SUCCESS)
        else:
            bundle_nombre = self._bundle_var.get()
            bundle_slug = ""
            for b in self.bundles_mgr.bundles:
                if b.nombre == bundle_nombre:
                    bundle_slug = b.slug
                    break

            slug = slugify(titulo)[:50] + "-draft"
            listing = Listing(
                slug=slug,
                bundle=bundle_slug,
                titulo=titulo,
                descripcion=descripcion,
                precio=precio,
                stock=stock,
                estado=estado,
                creado_en=datetime.now().isoformat(),
            )
            listing.save()
            self._status_label.configure(
                text=f"Listing '{slug}' creado", fg=theme.SUCCESS)

        if self._on_saved:
            self._on_saved()
        self.after(800, self.destroy)

    def _delete(self) -> None:
        if not messagebox.askyesno(
            "Eliminar listing",
            f"¿Eliminar listing '{self._listing.slug}'?",
            parent=self,
        ):
            return

        path = self._listing.json_path
        if path.exists():
            path.unlink()
        self._status_label.configure(text="Listing eliminado", fg=theme.SUCCESS)
        if self._on_saved:
            self._on_saved()
        self.after(800, self.destroy)
