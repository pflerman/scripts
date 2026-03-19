"""Vista de gestión de productos — Tkinter puro con ttk.Treeview."""

import json
import logging
import tkinter as tk
from tkinter import ttk, messagebox
import urllib.error
import urllib.request
from typing import Callable

from app.config import (
    BLUE_DOLLAR_API,
    FACTOR_NACIONALIZACION,
    TIPOS_PRODUCTO,
    TIPO_NOMBRE_A_PREFIJO,
)
from app.models.catalogo import Catalogo, Producto
from app.ui import theme
from app.utils.validators import generar_sku, validar_entero_positivo, validar_precio

logger = logging.getLogger(__name__)

COLUMNS = ("sku", "nombre", "tipo", "costo", "stock")
HEADINGS = {"sku": "SKU", "nombre": "Nombre", "tipo": "Tipo",
            "costo": "Costo", "stock": "Stock"}
WIDTHS = {"sku": 170, "nombre": 350, "tipo": 170, "costo": 100, "stock": 70}
ANCHORS = {"sku": "w", "nombre": "w", "tipo": "w", "costo": "e", "stock": "e"}


class ProductosView(tk.Frame):
    """Vista principal de productos: Treeview + buscador + detalle."""

    def __init__(self, master: tk.Widget, catalogo: Catalogo, **kwargs):
        super().__init__(master, bg=theme.BG_PRIMARY, **kwargs)
        self.catalogo = catalogo
        self._build()

    def _build(self) -> None:
        # ── Header ───────────────────────────────────────────────────────────
        header = tk.Frame(self, bg=theme.BG_PRIMARY)
        header.pack(fill="x", padx=20, pady=(20, 8))

        tk.Label(header, text="Productos", font=theme.FONT_TITLE,
                 bg=theme.BG_PRIMARY, fg=theme.TEXT_PRIMARY).pack(side="left")

        nuevo_btn = tk.Button(
            header, text="+ Nuevo producto", font=theme.FONT_BOLD,
            bg=theme.BTN_SUCCESS, fg="white", relief="flat", bd=0,
            padx=14, pady=4, cursor="hand2",
            activebackground="#43A047", activeforeground="white",
            command=self._show_form,
        )
        nuevo_btn.pack(side="right")

        # ── Filter bar ───────────────────────────────────────────────────────
        filter_bar = tk.Frame(self, bg=theme.BG_SECONDARY, bd=1, relief="solid",
                              highlightbackground=theme.BORDER, highlightthickness=1)
        filter_bar.pack(fill="x", padx=20, pady=(0, 6))

        tk.Label(filter_bar, text="🔍 Buscar:", font=theme.FONT_NORMAL,
                 bg=theme.BG_SECONDARY, fg=theme.TEXT_SECONDARY).pack(
            side="left", padx=(10, 4), pady=6)

        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._on_filter_changed())
        search_entry = ttk.Entry(filter_bar, textvariable=self._search_var, width=35)
        search_entry.pack(side="left", padx=(0, 6), pady=6)

        clear_btn = tk.Button(
            filter_bar, text="✕", font=theme.FONT_SMALL,
            bg=theme.BG_SECONDARY, fg=theme.TEXT_MUTED, relief="flat", bd=0,
            cursor="hand2", command=self._clear_filter,
        )
        clear_btn.pack(side="left", padx=(0, 10), pady=6)

        self._count_label = tk.Label(
            filter_bar, text="", font=theme.FONT_NORMAL,
            bg=theme.BG_SECONDARY, fg=theme.COUNT_LABEL_COLOR,
        )
        self._count_label.pack(side="right", padx=12, pady=6)

        # ── Treeview ─────────────────────────────────────────────────────────
        table_frame = tk.Frame(self, bg=theme.BG_PRIMARY)
        table_frame.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        vsb = ttk.Scrollbar(table_frame, orient="vertical")
        vsb.pack(side="right", fill="y")

        self.tree = ttk.Treeview(
            table_frame, columns=COLUMNS, show="headings",
            yscrollcommand=vsb.set, height=20,
        )
        self.tree.pack(fill="both", expand=True)
        vsb.config(command=self.tree.yview)

        for col in COLUMNS:
            self.tree.heading(col, text=HEADINGS[col])
            self.tree.column(col, width=WIDTHS[col], anchor=ANCHORS[col])

        self.tree.tag_configure("even", background=theme.TAG_EVEN)
        self.tree.tag_configure("odd", background=theme.TAG_ODD)

        self.tree.bind("<Double-1>", self._on_double_click)

        self._populate_tree()

    # ── Filter logic ─────────────────────────────────────────────────────────

    def _on_filter_changed(self) -> None:
        self._populate_tree()

    def _clear_filter(self) -> None:
        self._search_var.set("")

    def _filter_productos(self, productos: list[Producto]) -> list[Producto]:
        query = self._search_var.get().strip()
        if not query:
            return productos
        terms = query.split()
        result = []
        for prod in productos:
            searchable = " ".join([
                prod.sku, prod.nombre, prod.tipo, prod.modelo,
                prod.color, prod.notas,
            ]).lower()
            match = True
            for term in terms:
                if term.startswith("-") and len(term) > 1:
                    if term[1:].lower() in searchable:
                        match = False
                        break
                else:
                    if term.lower() not in searchable:
                        match = False
                        break
            if match:
                result.append(prod)
        return result

    # ── Tree population ──────────────────────────────────────────────────────

    def _populate_tree(self) -> None:
        self.tree.delete(*self.tree.get_children())
        self._item_to_producto: dict[str, Producto] = {}
        todos = self.catalogo.productos
        productos = self._filter_productos(todos)
        self._count_label.configure(
            text=f"Mostrando {len(productos)} de {len(todos)}")
        for i, prod in enumerate(productos):
            tag = "even" if i % 2 == 0 else "odd"
            item_id = self.tree.insert("", "end", values=(
                prod.sku,
                prod.nombre,
                prod.tipo,
                f"${prod.precio_costo:,.0f}",
                str(prod.stock),
            ), tags=(tag,))
            self._item_to_producto[item_id] = prod

    def _on_double_click(self, event: tk.Event) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        prod = self._item_to_producto.get(sel[0])
        if prod:
            self._show_detail(prod)

    # ── Detail window ────────────────────────────────────────────────────────

    def _show_detail(self, producto: Producto) -> None:
        detail = tk.Toplevel(self)
        detail.title(f"Producto: {producto.sku}")
        detail.geometry("520x560")
        detail.configure(bg=theme.BG_PRIMARY)
        detail.transient(self.winfo_toplevel())

        canvas = tk.Canvas(detail, bg=theme.BG_PRIMARY, highlightthickness=0)
        scrollbar = ttk.Scrollbar(detail, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=theme.BG_PRIMARY)

        scroll_frame.bind("<Configure>",
                          lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True, padx=12, pady=12)

        fields = [
            ("SKU", producto.sku),
            ("Nombre", producto.nombre),
            ("Tipo", producto.tipo),
            ("Modelo", producto.modelo),
            ("Color", producto.color),
            ("Talle", producto.talle or "—"),
            ("Proveedor", producto.proveedor),
        ]
        if producto.proveedor == "andres" and producto.precio_fob_usd is not None:
            fields.append(("FOB USD", f"USD {producto.precio_fob_usd:.4f}"))
            fields.append(("Factor nac.", f"x{producto.factor_nacionalizacion}"))
            fields.append(("TC Blue", f"${producto.tipo_cambio_usado:,.2f}"))
        fields.extend([
            ("Precio costo", f"${producto.precio_costo:,.2f} ARS"),
            ("Stock", str(producto.stock)),
            ("Título ML", producto.titulo_ml or "—"),
            ("Palabras clave",
             ", ".join(producto.palabras_clave) if producto.palabras_clave else "—"),
            ("Notas", producto.notas or "—"),
            ("Creado", producto.fecha_creacion),
            ("Actualizado", producto.ultima_actualizacion),
        ])
        if producto.dimensiones:
            d = producto.dimensiones
            dims = " x ".join(
                f"{d[k]}cm" for k in ("largo_cm", "ancho_cm", "alto_cm") if k in d)
            fields.insert(7, ("Dimensiones", dims))

        for label, value in fields:
            row = tk.Frame(scroll_frame, bg=theme.BG_PRIMARY)
            row.pack(fill="x", pady=2)
            fg = theme.ACCENT if label == "SKU" else theme.TEXT_PRIMARY
            tk.Label(row, text=label, font=theme.FONT_BOLD,
                     bg=theme.BG_PRIMARY, fg=theme.TEXT_SECONDARY,
                     width=16, anchor="e").pack(side="left", padx=(0, 8))
            tk.Label(row, text=value, font=theme.FONT_NORMAL,
                     bg=theme.BG_PRIMARY, fg=fg, anchor="w",
                     wraplength=340).pack(side="left", fill="x")

        if producto.descripcion:
            tk.Label(scroll_frame, text="Descripción:", font=theme.FONT_BOLD,
                     bg=theme.BG_PRIMARY, fg=theme.TEXT_SECONDARY,
                     anchor="w").pack(fill="x", padx=0, pady=(10, 4))
            desc_text = tk.Text(
                scroll_frame, height=6, font=theme.FONT_NORMAL,
                bg=theme.BG_INPUT, fg=theme.TEXT_PRIMARY, relief="solid",
                bd=1, wrap="word",
            )
            desc_text.pack(fill="x", pady=(0, 8))
            desc_text.insert("1.0", producto.descripcion)
            desc_text.configure(state="disabled")

    # ── New product form ─────────────────────────────────────────────────────

    def _show_form(self) -> None:
        NuevoProductoForm(self, self.catalogo, on_created=self._on_product_created)

    def _on_product_created(self) -> None:
        self._populate_tree()

    def refresh(self) -> None:
        self.catalogo.reload()
        self._populate_tree()


class NuevoProductoForm(tk.Toplevel):
    """Formulario modal para crear un nuevo producto."""

    def __init__(self, master: tk.Widget, catalogo: Catalogo,
                 on_created: Callable | None = None):
        super().__init__(master)
        self.catalogo = catalogo
        self._on_created = on_created
        self.title("Nuevo Producto")
        self.geometry("500x660")
        self.configure(bg=theme.BG_PRIMARY)
        self.resizable(False, True)
        self.transient(master.winfo_toplevel())
        self.grab_set()
        self._build()

    def _build(self) -> None:
        canvas = tk.Canvas(self, bg=theme.BG_PRIMARY, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self._form = tk.Frame(canvas, bg=theme.BG_PRIMARY)

        self._form.bind("<Configure>",
                        lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self._form, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True, padx=12, pady=12)

        f = self._form

        # Nombre
        self._nombre_var = self._add_field(f, "Nombre *")

        # Tipo
        tipos_nombres = [nombre for _, nombre in TIPOS_PRODUCTO.values()]
        self._tipo_var = self._add_combo(f, "Tipo *", tipos_nombres)

        # Modelo
        modelos_list = list(catalogo_modelos_items(self.catalogo))
        self._modelos_map = {f"{cod} — {nom}": cod for cod, nom in modelos_list}
        self._modelo_var = self._add_combo(f, "Modelo *", list(self._modelos_map.keys()))

        # Color
        self._color_var = self._add_field(f, "Color *", default="Blanco")

        # Talle
        self._talle_var = self._add_field(f, "Talle")

        # Dimensiones
        dim_row = tk.Frame(f, bg=theme.BG_PRIMARY)
        dim_row.pack(fill="x", pady=3)
        tk.Label(dim_row, text="Dimensiones", font=theme.FONT_BOLD,
                 bg=theme.BG_PRIMARY, fg=theme.TEXT_SECONDARY,
                 width=14, anchor="e").pack(side="left", padx=(0, 8))
        self._dim_vars: dict[str, tk.StringVar] = {}
        for key, lbl in [("largo_cm", "L"), ("ancho_cm", "A"), ("alto_cm", "H")]:
            tk.Label(dim_row, text=lbl, font=theme.FONT_SMALL,
                     bg=theme.BG_PRIMARY, fg=theme.TEXT_MUTED).pack(side="left")
            var = tk.StringVar()
            ttk.Entry(dim_row, textvariable=var, width=6).pack(side="left", padx=(2, 6))
            self._dim_vars[key] = var

        # Proveedor
        self._prov_var = self._add_combo(f, "Proveedor *", ["andres", "sao-bernardo"])

        # FOB
        self._fob_var = self._add_field(f, "Precio FOB USD")

        # Costo directo
        self._costo_var = self._add_field(f, "Precio costo ARS")

        # Stock
        self._stock_var = self._add_field(f, "Stock inicial", default="0")

        # Notas
        self._notas_var = self._add_field(f, "Notas")

        # SKU preview
        sku_frame = tk.Frame(f, bg=theme.BG_SECONDARY, bd=1, relief="solid")
        sku_frame.pack(fill="x", pady=(10, 4))
        self._sku_label = tk.Label(
            sku_frame, text="SKU: (completá los campos)", font=theme.FONT_BOLD,
            bg=theme.BG_SECONDARY, fg=theme.ACCENT,
        )
        self._sku_label.pack(padx=12, pady=6)

        # Bind for SKU preview
        self._tipo_var.trace_add("write", lambda *_: self._update_sku())
        self._modelo_var.trace_add("write", lambda *_: self._update_sku())
        self._color_var.trace_add("write", lambda *_: self._update_sku())
        self._talle_var.trace_add("write", lambda *_: self._update_sku())

        # Status
        self._status_label = tk.Label(
            f, text="", font=theme.FONT_NORMAL,
            bg=theme.BG_PRIMARY, fg=theme.TEXT_MUTED,
        )
        self._status_label.pack(fill="x", pady=4)

        # Buttons
        btn_row = tk.Frame(f, bg=theme.BG_PRIMARY)
        btn_row.pack(fill="x", pady=(6, 4))

        tk.Button(
            btn_row, text="Crear producto", font=theme.FONT_BOLD,
            bg=theme.BTN_SUCCESS, fg="white", relief="flat", bd=0,
            padx=14, pady=4, cursor="hand2", command=self._crear,
        ).pack(side="left", padx=(0, 8))

        tk.Button(
            btn_row, text="Cancelar", font=theme.FONT_NORMAL,
            bg=theme.BG_SECONDARY, fg=theme.TEXT_PRIMARY, relief="solid", bd=1,
            padx=14, pady=4, cursor="hand2", command=self.destroy,
        ).pack(side="left")

    def _add_field(self, parent: tk.Frame, label: str,
                   default: str = "") -> tk.StringVar:
        row = tk.Frame(parent, bg=theme.BG_PRIMARY)
        row.pack(fill="x", pady=3)
        tk.Label(row, text=label, font=theme.FONT_BOLD,
                 bg=theme.BG_PRIMARY, fg=theme.TEXT_SECONDARY,
                 width=14, anchor="e").pack(side="left", padx=(0, 8))
        var = tk.StringVar(value=default)
        ttk.Entry(row, textvariable=var, width=30).pack(side="left", fill="x", expand=True)
        return var

    def _add_combo(self, parent: tk.Frame, label: str,
                   values: list[str]) -> tk.StringVar:
        row = tk.Frame(parent, bg=theme.BG_PRIMARY)
        row.pack(fill="x", pady=3)
        tk.Label(row, text=label, font=theme.FONT_BOLD,
                 bg=theme.BG_PRIMARY, fg=theme.TEXT_SECONDARY,
                 width=14, anchor="e").pack(side="left", padx=(0, 8))
        var = tk.StringVar()
        combo = ttk.Combobox(row, textvariable=var, values=values,
                             state="readonly", width=28)
        combo.pack(side="left", fill="x", expand=True)
        if values:
            combo.current(0)
        return var

    def _update_sku(self) -> None:
        tipo_nombre = self._tipo_var.get()
        prefijo = TIPO_NOMBRE_A_PREFIJO.get(tipo_nombre, "???")
        modelo_display = self._modelo_var.get()
        modelo_cod = self._modelos_map.get(modelo_display, "???")
        color = self._color_var.get()
        talle = self._talle_var.get()
        sku = generar_sku(prefijo, modelo_cod, color, talle)
        existe = " (YA EXISTE)" if self.catalogo.existe(sku) else ""
        self._sku_label.configure(text=f"SKU: {sku}{existe}")

    def _crear(self) -> None:
        nombre = self._nombre_var.get().strip()
        if not nombre:
            self._status_label.configure(text="El nombre es obligatorio", fg=theme.ERROR)
            return

        tipo_nombre = self._tipo_var.get()
        prefijo = TIPO_NOMBRE_A_PREFIJO.get(tipo_nombre, "")
        if not prefijo:
            self._status_label.configure(text="Seleccioná un tipo", fg=theme.ERROR)
            return

        modelo_display = self._modelo_var.get()
        modelo_cod = self._modelos_map.get(modelo_display, "")
        modelo_nombre = (modelo_display.split(" — ", 1)[1]
                         if " — " in modelo_display else modelo_display)

        color = self._color_var.get().strip() or "Blanco"
        talle = self._talle_var.get().strip()
        proveedor = self._prov_var.get()

        precio_costo = 0.0
        precio_fob_usd = None
        factor_nac = None
        tipo_cambio = None

        if proveedor == "andres":
            fob = validar_precio(self._fob_var.get())
            if fob is None or fob <= 0:
                self._status_label.configure(text="Ingresá precio FOB válido", fg=theme.ERROR)
                return
            precio_fob_usd = fob
            factor_nac = FACTOR_NACIONALIZACION
            self._status_label.configure(text="Obteniendo dólar blue...", fg=theme.INFO)
            self.update()
            try:
                tipo_cambio = self._fetch_blue_dollar()
            except Exception as e:
                costo = validar_precio(self._costo_var.get())
                if costo and costo > 0:
                    precio_costo = costo
                    tipo_cambio = 0.0
                else:
                    self._status_label.configure(
                        text=f"Error dólar blue: {e}. Ingresá costo ARS.", fg=theme.ERROR)
                    return
            if tipo_cambio and tipo_cambio > 0:
                precio_costo = precio_fob_usd * FACTOR_NACIONALIZACION * tipo_cambio
        else:
            costo = validar_precio(self._costo_var.get())
            if costo is None or costo < 0:
                self._status_label.configure(text="Ingresá precio de costo válido", fg=theme.ERROR)
                return
            precio_costo = costo

        stock_val = validar_entero_positivo(self._stock_var.get()) or 0
        notas = self._notas_var.get().strip()

        dimensiones = {}
        for key, var in self._dim_vars.items():
            val = var.get().strip()
            if val:
                try:
                    dimensiones[key] = float(val.replace(",", "."))
                except ValueError:
                    pass

        sku = generar_sku(prefijo, modelo_cod, color, talle)

        if self.catalogo.existe(sku):
            self._status_label.configure(text=f"SKU {sku} ya existe", fg=theme.WARNING)
            return

        try:
            self.catalogo.crear_producto(
                sku=sku, nombre=nombre, tipo=tipo_nombre,
                modelo=modelo_nombre, color=color, talle=talle,
                proveedor=proveedor, precio_costo=precio_costo,
                stock=stock_val, notas=notas,
                dimensiones=dimensiones if dimensiones else None,
                precio_fob_usd=precio_fob_usd,
                factor_nacionalizacion=factor_nac,
                tipo_cambio_usado=tipo_cambio,
            )
            self._status_label.configure(
                text=f"Producto {sku} creado", fg=theme.SUCCESS)
            if self._on_created:
                self._on_created()
            self.after(1200, self.destroy)
        except Exception as e:
            logger.error("Error creando producto: %s", e)
            self._status_label.configure(text=f"Error: {e}", fg=theme.ERROR)

    @staticmethod
    def _fetch_blue_dollar() -> float:
        req = urllib.request.Request(BLUE_DOLLAR_API, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        return float(data["blue"]["value_sell"])


def catalogo_modelos_items(catalogo: Catalogo) -> list[tuple[str, str]]:
    return list(catalogo.modelos.items())
