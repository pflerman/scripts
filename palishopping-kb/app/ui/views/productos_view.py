"""Vista de gestión de productos — lista, detalle y formulario de alta."""

import json
import logging
import threading
import urllib.error
import urllib.request
from typing import Callable

import customtkinter as ctk

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


class ProductosView(ctk.CTkFrame):
    """Vista principal de productos: tabla + panel de detalle/creación."""

    def __init__(self, master: ctk.CTkBaseClass, catalogo: Catalogo, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.catalogo = catalogo
        self._current_detail: ctk.CTkFrame | None = None
        self._build()

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))
        header.columnconfigure(0, weight=1)

        title = ctk.CTkLabel(
            header,
            text="Productos",
            font=theme.font_bold(theme.FONT_SIZE_XXL),
            text_color=theme.TEXT_PRIMARY,
            anchor="w",
        )
        title.grid(row=0, column=0, sticky="w")

        nuevo_btn = ctk.CTkButton(
            header, text="+ Nuevo producto", width=160,
            command=self._show_form,
        )
        theme.style_accent_button(nuevo_btn)
        nuevo_btn.grid(row=0, column=1, sticky="e")

        # Content area (scrollable)
        self._content = ctk.CTkScrollableFrame(
            self, fg_color="transparent",
        )
        self._content.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 10))
        self._content.columnconfigure(0, weight=1)

        self._render_table()

    def _render_table(self) -> None:
        """Renderiza la tabla de productos."""
        for widget in self._content.winfo_children():
            widget.destroy()

        productos = self.catalogo.productos
        if not productos:
            empty = ctk.CTkLabel(
                self._content,
                text="No hay productos en el catálogo",
                font=theme.font(theme.FONT_SIZE_MD),
                text_color=theme.TEXT_MUTED,
            )
            empty.grid(row=0, column=0, pady=40)
            return

        # Header row
        header_frame = ctk.CTkFrame(self._content, fg_color=theme.BG_SECONDARY, corner_radius=6)
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        self._table_row(header_frame, "SKU", "Nombre", "Tipo", "Costo", "Stock",
                        is_header=True)

        for i, prod in enumerate(productos):
            row_frame = ctk.CTkFrame(
                self._content,
                fg_color=theme.BG_CARD if i % 2 == 0 else theme.BG_SECONDARY,
                corner_radius=4,
                cursor="hand2",
            )
            row_frame.grid(row=i + 1, column=0, sticky="ew", pady=1)
            self._table_row(
                row_frame,
                prod.sku,
                prod.nombre,
                prod.tipo,
                f"${prod.precio_costo:,.0f}",
                str(prod.stock),
            )
            # Click to show detail
            row_frame.bind("<Button-1>", lambda e, p=prod: self._show_detail(p))
            for child in row_frame.winfo_children():
                child.bind("<Button-1>", lambda e, p=prod: self._show_detail(p))

    def _table_row(self, parent: ctk.CTkFrame, sku: str, nombre: str,
                   tipo: str, costo: str, stock: str, is_header: bool = False) -> None:
        parent.columnconfigure(1, weight=1)
        fnt = theme.font_bold(theme.FONT_SIZE_SM) if is_header else theme.font(theme.FONT_SIZE_SM)
        color = theme.TEXT_SECONDARY if is_header else theme.TEXT_PRIMARY
        sku_color = theme.TEXT_SECONDARY if is_header else theme.ACCENT

        ctk.CTkLabel(parent, text=sku, font=fnt, text_color=sku_color, width=180, anchor="w"
                     ).grid(row=0, column=0, padx=(12, 4), pady=6, sticky="w")
        ctk.CTkLabel(parent, text=nombre, font=fnt, text_color=color, anchor="w"
                     ).grid(row=0, column=1, padx=4, pady=6, sticky="w")
        ctk.CTkLabel(parent, text=tipo, font=fnt, text_color=color, width=160, anchor="w"
                     ).grid(row=0, column=2, padx=4, pady=6, sticky="w")
        ctk.CTkLabel(parent, text=costo, font=fnt, text_color=theme.SUCCESS if not is_header else color,
                     width=80, anchor="e"
                     ).grid(row=0, column=3, padx=4, pady=6, sticky="e")
        ctk.CTkLabel(parent, text=stock, font=fnt, text_color=color, width=60, anchor="e"
                     ).grid(row=0, column=4, padx=(4, 12), pady=6, sticky="e")

    def _show_detail(self, producto: Producto) -> None:
        """Muestra panel de detalle de un producto."""
        self._clear_detail()

        detail = ctk.CTkToplevel(self)
        detail.title(f"Producto: {producto.sku}")
        detail.geometry("550x600")
        detail.configure(fg_color=theme.BG_PRIMARY)
        detail.transient(self.winfo_toplevel())
        self._current_detail = detail

        scroll = ctk.CTkScrollableFrame(detail, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=15, pady=15)
        scroll.columnconfigure(1, weight=1)

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
            ("Palabras clave", ", ".join(producto.palabras_clave) if producto.palabras_clave else "—"),
            ("Notas", producto.notas or "—"),
            ("Creado", producto.fecha_creacion),
            ("Actualizado", producto.ultima_actualizacion),
        ])

        if producto.dimensiones:
            d = producto.dimensiones
            dims = " x ".join(f"{d[k]}cm" for k in ("largo_cm", "ancho_cm", "alto_cm") if k in d)
            fields.insert(7, ("Dimensiones", dims))

        for i, (label, value) in enumerate(fields):
            lbl = ctk.CTkLabel(
                scroll, text=label, font=theme.font_bold(theme.FONT_SIZE_SM),
                text_color=theme.TEXT_SECONDARY, width=120, anchor="e",
            )
            lbl.grid(row=i, column=0, sticky="ne", padx=(0, 10), pady=3)

            val_color = theme.ACCENT if label == "SKU" else theme.TEXT_PRIMARY
            val = ctk.CTkLabel(
                scroll, text=value, font=theme.font(theme.FONT_SIZE_SM),
                text_color=val_color, anchor="w", wraplength=350,
            )
            val.grid(row=i, column=1, sticky="w", pady=3)

        # Descripción aparte si es larga
        if producto.descripcion:
            sep = ctk.CTkLabel(scroll, text="Descripción:", font=theme.font_bold(theme.FONT_SIZE_SM),
                               text_color=theme.TEXT_SECONDARY, anchor="w")
            sep.grid(row=len(fields), column=0, columnspan=2, sticky="w", pady=(12, 4))
            desc = ctk.CTkTextbox(scroll, height=120, font=theme.font(theme.FONT_SIZE_SM),
                                  fg_color=theme.BG_INPUT, text_color=theme.TEXT_PRIMARY,
                                  state="normal", corner_radius=6)
            desc.grid(row=len(fields) + 1, column=0, columnspan=2, sticky="ew", pady=(0, 10))
            desc.insert("1.0", producto.descripcion)
            desc.configure(state="disabled")

    def _clear_detail(self) -> None:
        if self._current_detail and self._current_detail.winfo_exists():
            self._current_detail.destroy()
        self._current_detail = None

    def _show_form(self) -> None:
        """Abre el formulario de nuevo producto."""
        form = NuevoProductoForm(self, self.catalogo, on_created=self._on_product_created)
        form.grab_set()

    def _on_product_created(self) -> None:
        """Callback cuando se crea un producto exitosamente."""
        self._render_table()

    def refresh(self) -> None:
        self.catalogo.reload()
        self._render_table()


class NuevoProductoForm(ctk.CTkToplevel):
    """Formulario modal para crear un nuevo producto."""

    def __init__(self, master: ctk.CTkBaseClass, catalogo: Catalogo,
                 on_created: Callable | None = None):
        super().__init__(master)
        self.catalogo = catalogo
        self._on_created = on_created
        self.title("Nuevo Producto")
        self.geometry("520x700")
        self.configure(fg_color=theme.BG_PRIMARY)
        self.resizable(False, True)
        self.transient(master.winfo_toplevel())
        self._build()

    def _build(self) -> None:
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=15, pady=15)
        scroll.columnconfigure(1, weight=1)

        row = 0

        # Nombre
        row = self._add_field(scroll, row, "Nombre *")
        self._nombre_entry = self._last_entry

        # Tipo
        tipos_nombres = [nombre for _, nombre in TIPOS_PRODUCTO.values()]
        row = self._add_dropdown(scroll, row, "Tipo *", tipos_nombres)
        self._tipo_menu = self._last_menu

        # Modelo
        modelos_list = list(catalogo_modelos_items(self.catalogo))
        self._modelos_map = {f"{cod} — {nom}": cod for cod, nom in modelos_list}
        modelos_display = list(self._modelos_map.keys())
        row = self._add_dropdown(scroll, row, "Modelo *", modelos_display)
        self._modelo_menu = self._last_menu

        # Color
        row = self._add_field(scroll, row, "Color *", default="Blanco")
        self._color_entry = self._last_entry

        # Talle
        row = self._add_field(scroll, row, "Talle", default="")
        self._talle_entry = self._last_entry

        # Dimensiones
        dim_lbl = ctk.CTkLabel(scroll, text="Dimensiones", font=theme.font_bold(theme.FONT_SIZE_SM),
                                text_color=theme.TEXT_SECONDARY, anchor="e", width=120)
        dim_lbl.grid(row=row, column=0, sticky="ne", padx=(0, 10), pady=6)
        dim_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        dim_frame.grid(row=row, column=1, sticky="ew", pady=6)
        row += 1

        self._dim_entries = {}
        for i, (key, label) in enumerate([("largo_cm", "Largo"), ("ancho_cm", "Ancho"), ("alto_cm", "Alto")]):
            ctk.CTkLabel(dim_frame, text=label, font=theme.font(theme.FONT_SIZE_XS),
                         text_color=theme.TEXT_MUTED).grid(row=0, column=i * 2, padx=(0, 2))
            entry = ctk.CTkEntry(dim_frame, width=60, font=theme.font(theme.FONT_SIZE_SM),
                                 fg_color=theme.BG_INPUT, text_color=theme.TEXT_PRIMARY,
                                 border_color=theme.BORDER, placeholder_text="cm")
            entry.grid(row=0, column=i * 2 + 1, padx=(0, 8))
            self._dim_entries[key] = entry

        # Proveedor
        row = self._add_dropdown(scroll, row, "Proveedor *", ["andres", "sao-bernardo"])
        self._prov_menu = self._last_menu
        self._prov_menu.set("andres")

        # Precio FOB (solo Andrés)
        row = self._add_field(scroll, row, "Precio FOB USD", default="")
        self._fob_entry = self._last_entry

        # Precio costo directo (São Bernardo)
        row = self._add_field(scroll, row, "Precio costo ARS", default="")
        self._costo_entry = self._last_entry

        # Stock
        row = self._add_field(scroll, row, "Stock inicial", default="0")
        self._stock_entry = self._last_entry

        # Notas
        row = self._add_field(scroll, row, "Notas", default="")
        self._notas_entry = self._last_entry

        # SKU preview
        sku_frame = ctk.CTkFrame(scroll, fg_color=theme.BG_SECONDARY, corner_radius=6)
        sku_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(12, 4))
        self._sku_label = ctk.CTkLabel(
            sku_frame, text="SKU: (completá los campos)",
            font=theme.font_bold(theme.FONT_SIZE_MD), text_color=theme.ACCENT,
        )
        self._sku_label.pack(padx=15, pady=8)
        row += 1

        # Status
        self._status_label = ctk.CTkLabel(
            scroll, text="", font=theme.font(theme.FONT_SIZE_SM),
            text_color=theme.TEXT_MUTED,
        )
        self._status_label.grid(row=row, column=0, columnspan=2, sticky="w", pady=4)
        row += 1

        # Botones
        btn_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        btn_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(8, 4))

        crear_btn = ctk.CTkButton(btn_frame, text="Crear producto", width=160,
                                   command=self._crear)
        theme.style_accent_button(crear_btn)
        crear_btn.pack(side="left", padx=(0, 10))

        cancel_btn = ctk.CTkButton(btn_frame, text="Cancelar", width=100,
                                    command=self.destroy)
        theme.style_secondary_button(cancel_btn)
        cancel_btn.pack(side="left")

        # Bind updates for SKU preview
        self._tipo_menu.configure(command=lambda _: self._update_sku_preview())
        self._modelo_menu.configure(command=lambda _: self._update_sku_preview())
        self._color_entry.bind("<KeyRelease>", lambda _: self._update_sku_preview())
        self._talle_entry.bind("<KeyRelease>", lambda _: self._update_sku_preview())

    def _add_field(self, parent: ctk.CTkFrame, row: int, label: str,
                   default: str = "") -> int:
        lbl = ctk.CTkLabel(parent, text=label, font=theme.font_bold(theme.FONT_SIZE_SM),
                            text_color=theme.TEXT_SECONDARY, width=120, anchor="e")
        lbl.grid(row=row, column=0, sticky="ne", padx=(0, 10), pady=6)
        entry = ctk.CTkEntry(parent, font=theme.font(theme.FONT_SIZE_SM),
                              fg_color=theme.BG_INPUT, text_color=theme.TEXT_PRIMARY,
                              border_color=theme.BORDER)
        entry.grid(row=row, column=1, sticky="ew", pady=6)
        if default:
            entry.insert(0, default)
        self._last_entry = entry
        return row + 1

    def _add_dropdown(self, parent: ctk.CTkFrame, row: int, label: str,
                      values: list[str]) -> int:
        lbl = ctk.CTkLabel(parent, text=label, font=theme.font_bold(theme.FONT_SIZE_SM),
                            text_color=theme.TEXT_SECONDARY, width=120, anchor="e")
        lbl.grid(row=row, column=0, sticky="ne", padx=(0, 10), pady=6)
        menu = ctk.CTkOptionMenu(
            parent, values=values, font=theme.font(theme.FONT_SIZE_SM),
            fg_color=theme.BG_INPUT, button_color=theme.ACCENT,
            button_hover_color=theme.ACCENT_HOVER,
            text_color=theme.TEXT_PRIMARY,
        )
        menu.grid(row=row, column=1, sticky="ew", pady=6)
        self._last_menu = menu
        return row + 1

    def _update_sku_preview(self) -> None:
        tipo_nombre = self._tipo_menu.get()
        prefijo = TIPO_NOMBRE_A_PREFIJO.get(tipo_nombre, "???")
        modelo_display = self._modelo_menu.get()
        modelo_cod = self._modelos_map.get(modelo_display, "???")
        color = self._color_entry.get()
        talle = self._talle_entry.get()
        sku = generar_sku(prefijo, modelo_cod, color, talle)
        existe = " (YA EXISTE)" if self.catalogo.existe(sku) else ""
        self._sku_label.configure(text=f"SKU: {sku}{existe}")

    def _crear(self) -> None:
        """Valida y crea el producto."""
        nombre = self._nombre_entry.get().strip()
        if not nombre:
            self._status_label.configure(text="El nombre es obligatorio", text_color=theme.ERROR)
            return

        tipo_nombre = self._tipo_menu.get()
        prefijo = TIPO_NOMBRE_A_PREFIJO.get(tipo_nombre, "")
        if not prefijo:
            self._status_label.configure(text="Seleccioná un tipo", text_color=theme.ERROR)
            return

        modelo_display = self._modelo_menu.get()
        modelo_cod = self._modelos_map.get(modelo_display, "")
        modelo_nombre = modelo_display.split(" — ", 1)[1] if " — " in modelo_display else modelo_display

        color = self._color_entry.get().strip() or "Blanco"
        talle = self._talle_entry.get().strip()

        proveedor = self._prov_menu.get()

        # Calcular precio
        precio_costo = 0.0
        precio_fob_usd = None
        factor_nac = None
        tipo_cambio = None

        if proveedor == "andres":
            fob = validar_precio(self._fob_entry.get())
            if fob is None or fob <= 0:
                self._status_label.configure(text="Ingresá precio FOB válido", text_color=theme.ERROR)
                return
            precio_fob_usd = fob
            factor_nac = FACTOR_NACIONALIZACION
            # Fetch blue dollar in background
            self._status_label.configure(text="Obteniendo dólar blue...", text_color=theme.INFO)
            self.update()
            try:
                tipo_cambio = self._fetch_blue_dollar()
            except Exception as e:
                # Try manual costo entry
                costo = validar_precio(self._costo_entry.get())
                if costo and costo > 0:
                    precio_costo = costo
                    tipo_cambio = 0.0
                else:
                    self._status_label.configure(
                        text=f"Error dólar blue: {e}. Ingresá precio costo ARS.",
                        text_color=theme.ERROR,
                    )
                    return
            if tipo_cambio and tipo_cambio > 0:
                precio_costo = precio_fob_usd * FACTOR_NACIONALIZACION * tipo_cambio
        else:
            costo = validar_precio(self._costo_entry.get())
            if costo is None or costo < 0:
                self._status_label.configure(text="Ingresá precio de costo válido", text_color=theme.ERROR)
                return
            precio_costo = costo

        stock_val = validar_entero_positivo(self._stock_entry.get()) or 0
        notas = self._notas_entry.get().strip()

        # Dimensiones
        dimensiones = {}
        for key, entry in self._dim_entries.items():
            val = entry.get().strip()
            if val:
                try:
                    dimensiones[key] = float(val.replace(",", "."))
                except ValueError:
                    pass

        sku = generar_sku(prefijo, modelo_cod, color, talle)

        if self.catalogo.existe(sku):
            self._status_label.configure(text=f"SKU {sku} ya existe", text_color=theme.WARNING)
            return

        try:
            self.catalogo.crear_producto(
                sku=sku,
                nombre=nombre,
                tipo=tipo_nombre,
                modelo=modelo_nombre,
                color=color,
                talle=talle,
                proveedor=proveedor,
                precio_costo=precio_costo,
                stock=stock_val,
                notas=notas,
                dimensiones=dimensiones if dimensiones else None,
                precio_fob_usd=precio_fob_usd,
                factor_nacionalizacion=factor_nac,
                tipo_cambio_usado=tipo_cambio,
            )
            self._status_label.configure(
                text=f"Producto {sku} creado exitosamente", text_color=theme.SUCCESS,
            )
            if self._on_created:
                self._on_created()
            self.after(1500, self.destroy)
        except Exception as e:
            logger.error("Error creando producto: %s", e)
            self._status_label.configure(text=f"Error: {e}", text_color=theme.ERROR)

    @staticmethod
    def _fetch_blue_dollar() -> float:
        req = urllib.request.Request(BLUE_DOLLAR_API, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        return float(data["blue"]["value_sell"])


def catalogo_modelos_items(catalogo: Catalogo) -> list[tuple[str, str]]:
    """Retorna lista de (codigo, nombre) de modelos."""
    return list(catalogo.modelos.items())
