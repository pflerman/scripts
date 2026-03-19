"""Widget de card de producto — Tkinter puro."""

import tkinter as tk

from app.models.catalogo import Producto
from app.ui import theme


class ProductCard(tk.Frame):
    """Card compacta que muestra info de un producto."""

    def __init__(self, master: tk.Widget, producto: Producto, **kwargs):
        super().__init__(master, bg=theme.BG_CARD, bd=1, relief="solid",
                         highlightbackground=theme.BORDER, highlightthickness=1,
                         **kwargs)
        self.producto = producto

        tk.Label(self, text=producto.sku, font=theme.FONT_BOLD,
                 bg=theme.BG_CARD, fg=theme.ACCENT, anchor="w").pack(
            fill="x", padx=10, pady=(6, 0))

        tk.Label(self, text=producto.nombre, font=theme.FONT_NORMAL,
                 bg=theme.BG_CARD, fg=theme.TEXT_PRIMARY, anchor="w").pack(
            fill="x", padx=10, pady=1)

        info = f"${producto.precio_costo:,.0f}  |  Stock: {producto.stock}"
        tk.Label(self, text=info, font=theme.FONT_SMALL,
                 bg=theme.BG_CARD, fg=theme.TEXT_SECONDARY, anchor="w").pack(
            fill="x", padx=10, pady=(0, 6))
