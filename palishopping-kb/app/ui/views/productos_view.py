"""Vista de gestión de productos — Tkinter puro con ttk.Treeview + CRUD."""

import json
import logging
import tkinter as tk
from tkinter import ttk
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
    """Vista principal de productos: Treeview + buscador + detalle + edición."""

    def __init__(self, master: tk.Widget, catalogo: Catalogo, **kwargs):
        super().__init__(master, bg=theme.BG_PRIMARY, **kwargs)
        self.catalogo = catalogo
        self._item_to_producto: dict[str, Producto] = {}
        self._build()

    def _build(self) -> None:
        # ── Header ───────────────────────────────────────────────────────────
        header = tk.Frame(self, bg=theme.BG_PRIMARY)
        header.pack(fill="x", padx=20, pady=(20, 8))

        tk.Label(header, text="Productos", font=theme.FONT_TITLE,
                 bg=theme.BG_PRIMARY, fg=theme.TEXT_PRIMARY).pack(side="left")

        tk.Button(
            header, text="+ Nuevo producto", font=theme.FONT_BOLD,
            bg=theme.BTN_SUCCESS, fg="white", relief="flat", bd=0,
            padx=14, pady=4, cursor="hand2",
            activebackground="#43A047", activeforeground="white",
            command=self._show_create_form,
        ).pack(side="right")

        # ── Filter bar ───────────────────────────────────────────────────────
        filter_bar = tk.Frame(self, bg=theme.BG_SECONDARY, bd=1, relief="solid",
                              highlightbackground=theme.BORDER, highlightthickness=1)
        filter_bar.pack(fill="x", padx=20, pady=(0, 6))

        tk.Label(filter_bar, text="🔍 Buscar:", font=theme.FONT_NORMAL,
                 bg=theme.BG_SECONDARY, fg=theme.TEXT_SECONDARY).pack(
            side="left", padx=(10, 4), pady=6)

        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._on_filter_changed())
        ttk.Entry(filter_bar, textvariable=self._search_var, width=35).pack(
            side="left", padx=(0, 6), pady=6)

        tk.Button(
            filter_bar, text="✕", font=theme.FONT_SMALL,
            bg=theme.BG_SECONDARY, fg=theme.TEXT_MUTED, relief="flat", bd=0,
            cursor="hand2", command=self._clear_filter,
        ).pack(side="left", padx=(0, 10), pady=6)

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

        # Doble-click → formulario edición
        self.tree.bind("<Double-1>", self._on_double_click)

        self._populate_tree()

    # ── Filter ───────────────────────────────────────────────────────────────

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
        self._item_to_producto.clear()
        todos = self.catalogo.productos
        productos = self._filter_productos(todos)
        self._count_label.configure(
            text=f"Mostrando {len(productos)} de {len(todos)}")
        for i, prod in enumerate(productos):
            tag = "even" if i % 2 == 0 else "odd"
            item_id = self.tree.insert("", "end", values=(
                prod.sku, prod.nombre, prod.tipo,
                f"${prod.precio_costo:,.0f}", str(prod.stock),
            ), tags=(tag,))
            self._item_to_producto[item_id] = prod

    def _get_selected_producto(self) -> Producto | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return self._item_to_producto.get(sel[0])

    def _on_double_click(self, event: tk.Event) -> None:
        prod = self._get_selected_producto()
        if prod:
            self._show_edit_form(prod)

    # ── Create / Edit form ───────────────────────────────────────────────────

    def _show_create_form(self) -> None:
        ProductoForm(self, self.catalogo, on_saved=self._populate_tree)

    def _show_edit_form(self, producto: Producto) -> None:
        ProductoForm(self, self.catalogo, producto=producto,
                     on_saved=self._populate_tree)

    def refresh(self) -> None:
        self.catalogo.reload()
        self._populate_tree()


# ── Formulario unificado crear / editar ──────────────────────────────────────

class ProductoForm(tk.Toplevel):
    """Formulario modal para crear o editar un producto."""

    def __init__(self, master: tk.Widget, catalogo: Catalogo,
                 producto: Producto | None = None,
                 on_saved: Callable | None = None):
        super().__init__(master)
        self.catalogo = catalogo
        self._producto = producto
        self._on_saved = on_saved
        self._editing = producto is not None

        self.title(f"Editar: {producto.sku}" if self._editing else "Nuevo Producto")
        self.geometry("520x740")
        self.configure(bg=theme.BG_PRIMARY)
        self.resizable(False, True)
        self.transient(master.winfo_toplevel())
        self._build()
        self.after(50, self._delayed_grab)

    def _delayed_grab(self) -> None:
        try:
            self.grab_set()
        except tk.TclError:
            pass

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
        p = self._producto

        # ── SKU (read-only si editando) ──────────────────────────────────────
        if self._editing:
            sku_frame = tk.Frame(f, bg=theme.BG_SECONDARY, bd=1, relief="solid")
            sku_frame.pack(fill="x", pady=(0, 8))
            tk.Label(sku_frame, text=f"SKU: {p.sku}", font=theme.FONT_BOLD,
                     bg=theme.BG_SECONDARY, fg=theme.ACCENT).pack(padx=12, pady=6)

        # ── Campos ───────────────────────────────────────────────────────────
        self._nombre_var = self._add_field(f, "Nombre *",
                                           default=p.nombre if p else "")

        tipos_nombres = [nombre for _, nombre in TIPOS_PRODUCTO.values()]
        self._tipo_var = self._add_combo(f, "Tipo *", tipos_nombres,
                                         default=p.tipo if p else None)

        modelos_list = list(_catalogo_modelos_items(self.catalogo))
        self._modelos_map = {f"{cod} — {nom}": cod for cod, nom in modelos_list}
        self._modelos_map_inv = {cod: display for display, cod in self._modelos_map.items()}
        modelos_display = list(self._modelos_map.keys())
        edit_modelo_default = None
        if p:
            # Buscar el código del modelo en variante
            for cod, nom in modelos_list:
                if nom == p.modelo or cod == p.modelo:
                    edit_modelo_default = f"{cod} — {nom}"
                    break
        self._modelo_var = self._add_combo(f, "Modelo *", modelos_display,
                                           default=edit_modelo_default)

        self._color_var = self._add_field(f, "Color *",
                                          default=p.color if p else "Blanco")

        self._talle_var = self._add_field(f, "Talle",
                                          default=p.talle if p else "")

        # Dimensiones
        dim_row = tk.Frame(f, bg=theme.BG_PRIMARY)
        dim_row.pack(fill="x", pady=3)
        tk.Label(dim_row, text="Dimensiones", font=theme.FONT_BOLD,
                 bg=theme.BG_PRIMARY, fg=theme.TEXT_SECONDARY,
                 width=14, anchor="e").pack(side="left", padx=(0, 8))
        self._dim_vars: dict[str, tk.StringVar] = {}
        dims = p.dimensiones if p and p.dimensiones else {}
        for key, lbl in [("largo_cm", "L"), ("ancho_cm", "A"), ("alto_cm", "H")]:
            tk.Label(dim_row, text=lbl, font=theme.FONT_SMALL,
                     bg=theme.BG_PRIMARY, fg=theme.TEXT_MUTED).pack(side="left")
            val = str(dims.get(key, "")) if dims.get(key) else ""
            var = tk.StringVar(value=val)
            ttk.Entry(dim_row, textvariable=var, width=6).pack(side="left", padx=(2, 6))
            self._dim_vars[key] = var

        self._prov_var = self._add_combo(f, "Proveedor *", ["andres", "sao-bernardo"],
                                         default=p.proveedor if p else None)

        fob_default = ""
        if p and p.precio_fob_usd is not None:
            fob_default = str(p.precio_fob_usd)
        self._fob_var = self._add_field(f, "Precio FOB USD", default=fob_default)

        costo_default = str(p.precio_costo) if p else ""
        self._costo_var = self._add_field(f, "Precio costo ARS", default=costo_default)

        self._stock_var = self._add_field(f, "Stock",
                                          default=str(p.stock) if p else "0")

        self._titulo_ml_var = self._add_field(f, "Título ML",
                                              default=p.titulo_ml if p else "")

        kw_default = ", ".join(p.palabras_clave) if p and p.palabras_clave else ""
        self._keywords_var = self._add_field(f, "Palabras clave", default=kw_default)

        # Descripción (Text multilínea)
        desc_row = tk.Frame(f, bg=theme.BG_PRIMARY)
        desc_row.pack(fill="x", pady=3)
        tk.Label(desc_row, text="Descripción", font=theme.FONT_BOLD,
                 bg=theme.BG_PRIMARY, fg=theme.TEXT_SECONDARY,
                 width=14, anchor="ne").pack(side="left", padx=(0, 8), anchor="n")
        self._desc_text = tk.Text(
            desc_row, height=5, width=35, font=theme.FONT_NORMAL,
            bg=theme.BG_INPUT, fg=theme.TEXT_PRIMARY, relief="solid",
            bd=1, wrap="word")
        self._desc_text.pack(side="left", fill="x", expand=True)
        if p and p.descripcion:
            self._desc_text.insert("1.0", p.descripcion)

        self._notas_var = self._add_field(f, "Notas",
                                          default=p.notas if p else "")

        # ── SKU preview (solo modo creación) ─────────────────────────────────
        if not self._editing:
            sku_frame = tk.Frame(f, bg=theme.BG_SECONDARY, bd=1, relief="solid")
            sku_frame.pack(fill="x", pady=(10, 4))
            self._sku_label = tk.Label(
                sku_frame, text="SKU: (completá los campos)", font=theme.FONT_BOLD,
                bg=theme.BG_SECONDARY, fg=theme.ACCENT)
            self._sku_label.pack(padx=12, pady=6)

            self._tipo_var.trace_add("write", lambda *_: self._update_sku())
            self._modelo_var.trace_add("write", lambda *_: self._update_sku())
            self._color_var.trace_add("write", lambda *_: self._update_sku())
            self._talle_var.trace_add("write", lambda *_: self._update_sku())

        # ── Status ───────────────────────────────────────────────────────────
        self._status_label = tk.Label(
            f, text="", font=theme.FONT_NORMAL,
            bg=theme.BG_PRIMARY, fg=theme.TEXT_MUTED)
        self._status_label.pack(fill="x", pady=4)

        # ── Botones ──────────────────────────────────────────────────────────
        btn_row = tk.Frame(f, bg=theme.BG_PRIMARY)
        btn_row.pack(fill="x", pady=(6, 4))

        action_text = "Guardar cambios" if self._editing else "Crear producto"
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

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _add_field(self, parent: tk.Frame, label: str,
                   default: str = "") -> tk.StringVar:
        row = tk.Frame(parent, bg=theme.BG_PRIMARY)
        row.pack(fill="x", pady=3)
        tk.Label(row, text=label, font=theme.FONT_BOLD,
                 bg=theme.BG_PRIMARY, fg=theme.TEXT_SECONDARY,
                 width=14, anchor="e").pack(side="left", padx=(0, 8))
        var = tk.StringVar(value=default)
        ttk.Entry(row, textvariable=var, width=30).pack(
            side="left", fill="x", expand=True)
        return var

    def _add_combo(self, parent: tk.Frame, label: str,
                   values: list[str], default: str | None = None) -> tk.StringVar:
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

    # ── Save ─────────────────────────────────────────────────────────────────

    def _save(self) -> None:
        if self._editing:
            self._save_edit()
        else:
            self._save_create()

    def _save_edit(self) -> None:
        """Guarda cambios a un producto existente."""
        p = self._producto
        nombre = self._nombre_var.get().strip()
        if not nombre:
            self._status_label.configure(text="El nombre es obligatorio", fg=theme.ERROR)
            return

        tipo = self._tipo_var.get()
        modelo_display = self._modelo_var.get()
        modelo_cod = self._modelos_map.get(modelo_display, "")
        modelo_nombre = (modelo_display.split(" — ", 1)[1]
                         if " — " in modelo_display else modelo_display)
        color = self._color_var.get().strip() or "Blanco"
        talle = self._talle_var.get().strip()
        proveedor = self._prov_var.get()

        costo = validar_precio(self._costo_var.get())
        if costo is None:
            self._status_label.configure(text="Precio costo inválido", fg=theme.ERROR)
            return
        precio_costo = costo

        stock_val = validar_entero_positivo(self._stock_var.get())
        if stock_val is None:
            stock_val = 0

        dimensiones: dict[str, float] | None = {}
        for key, var in self._dim_vars.items():
            val = var.get().strip()
            if val:
                try:
                    dimensiones[key] = float(val.replace(",", "."))
                except ValueError:
                    pass
        if not dimensiones:
            dimensiones = None

        titulo_ml = self._titulo_ml_var.get().strip()
        kw_text = self._keywords_var.get().strip()
        palabras_clave = [w.strip() for w in kw_text.split(",") if w.strip()] if kw_text else []
        descripcion = self._desc_text.get("1.0", "end-1c").strip()
        notas = self._notas_var.get().strip()

        # FOB
        precio_fob_usd = None
        factor_nac = None
        tipo_cambio = None
        if proveedor == "andres":
            fob = validar_precio(self._fob_var.get())
            if fob is not None and fob > 0:
                precio_fob_usd = fob
                factor_nac = FACTOR_NACIONALIZACION
                tipo_cambio = p.tipo_cambio_usado

        campos = dict(
            nombre=nombre,
            tipo=tipo,
            variante={"modelo": modelo_nombre, "color": color, "talle": talle},
            proveedor=proveedor,
            precio_costo=precio_costo,
            stock=stock_val,
            dimensiones=dimensiones,
            titulo_ml=titulo_ml,
            palabras_clave=palabras_clave,
            descripcion=descripcion,
            notas=notas,
            precio_fob_usd=precio_fob_usd,
            factor_nacionalizacion=factor_nac,
            tipo_cambio_usado=tipo_cambio,
        )

        ok = self.catalogo.actualizar_producto(p.sku, **campos)
        if ok:
            self._status_label.configure(text=f"Producto {p.sku} actualizado", fg=theme.SUCCESS)
            if self._on_saved:
                self._on_saved()
            self.after(1000, self.destroy)
        else:
            self._status_label.configure(text="Error al guardar", fg=theme.ERROR)

    def _save_create(self) -> None:
        """Crea un producto nuevo."""
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
            if self._on_saved:
                self._on_saved()
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


def _catalogo_modelos_items(catalogo: Catalogo) -> list[tuple[str, str]]:
    return list(catalogo.modelos.items())
