"""Widget de card de producto con miniatura."""

import customtkinter as ctk

from app.models.catalogo import Producto
from app.ui import theme


class ProductCard(ctk.CTkFrame):
    """Card compacta que muestra info de un producto."""

    def __init__(self, master: ctk.CTkBaseClass, producto: Producto, **kwargs):
        super().__init__(master, **kwargs)
        theme.style_card_frame(self)
        self.producto = producto
        self._build()

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)

        sku_label = ctk.CTkLabel(
            self,
            text=self.producto.sku,
            font=theme.font_bold(theme.FONT_SIZE_SM),
            text_color=theme.ACCENT,
            anchor="w",
        )
        sku_label.grid(row=0, column=0, sticky="w", padx=10, pady=(8, 0))

        nombre_label = ctk.CTkLabel(
            self,
            text=self.producto.nombre,
            font=theme.font(theme.FONT_SIZE_MD),
            text_color=theme.TEXT_PRIMARY,
            anchor="w",
        )
        nombre_label.grid(row=1, column=0, sticky="w", padx=10, pady=2)

        info_text = f"${self.producto.precio_costo:,.0f}  |  Stock: {self.producto.stock}"
        info_label = ctk.CTkLabel(
            self,
            text=info_text,
            font=theme.font(theme.FONT_SIZE_SM),
            text_color=theme.TEXT_SECONDARY,
            anchor="w",
        )
        info_label.grid(row=2, column=0, sticky="w", padx=10, pady=(0, 8))
