"""Vista de gestión de bundles — Tkinter puro."""

import tkinter as tk

from app.models.bundle import BundleManager
from app.ui import theme


class BundlesView(tk.Frame):
    def __init__(self, master: tk.Widget, bundles: BundleManager, **kwargs):
        super().__init__(master, bg=theme.BG_PRIMARY, **kwargs)
        self.bundles = bundles
        self._build()

    def _build(self) -> None:
        tk.Label(self, text="Bundles", font=theme.FONT_TITLE,
                 bg=theme.BG_PRIMARY, fg=theme.TEXT_PRIMARY).pack(
            anchor="w", padx=20, pady=(20, 10))

        if self.bundles.count() == 0:
            tk.Label(self, text="No hay bundles creados\n\nDisponible en Fase 2",
                     font=theme.FONT_NORMAL, bg=theme.BG_PRIMARY,
                     fg=theme.TEXT_MUTED, justify="center").pack(expand=True)
        else:
            for bundle in self.bundles.bundles:
                card = tk.Frame(self, bg=theme.BG_CARD, bd=1, relief="solid",
                                highlightbackground=theme.BORDER, highlightthickness=1)
                card.pack(fill="x", padx=20, pady=3)

                tk.Label(card, text=bundle.nombre, font=theme.FONT_BOLD,
                         bg=theme.BG_CARD, fg=theme.TEXT_PRIMARY,
                         anchor="w").pack(anchor="w", padx=10, pady=(6, 0))

                info = (f"{len(bundle.productos)} productos  |  "
                        f"Costo: ${bundle.precio_costo_total:,.0f}  |  "
                        f"Venta: ${bundle.precio_venta_final:,.0f}")
                tk.Label(card, text=info, font=theme.FONT_SMALL,
                         bg=theme.BG_CARD, fg=theme.TEXT_SECONDARY,
                         anchor="w").pack(anchor="w", padx=10, pady=(0, 6))

    def refresh(self) -> None:
        self.bundles.reload()
        for w in self.winfo_children():
            w.destroy()
        self._build()
