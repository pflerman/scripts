"""Vista de gestión de bundles (placeholder — implementación completa en fase 2)."""

import customtkinter as ctk

from app.models.bundle import BundleManager
from app.ui import theme


class BundlesView(ctk.CTkFrame):
    """Creación y gestión de combos/bundles."""

    def __init__(self, master: ctk.CTkBaseClass, bundles: BundleManager, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.bundles = bundles
        self._build()

    def _build(self) -> None:
        title = ctk.CTkLabel(
            self,
            text="Bundles",
            font=theme.font_bold(theme.FONT_SIZE_XXL),
            text_color=theme.TEXT_PRIMARY,
            anchor="w",
        )
        title.pack(padx=20, pady=(20, 10), anchor="w")

        if self.bundles.count() == 0:
            placeholder = ctk.CTkLabel(
                self,
                text="No hay bundles creados\n\nDisponible en Fase 2",
                font=theme.font(theme.FONT_SIZE_LG),
                text_color=theme.TEXT_MUTED,
                justify="center",
            )
            placeholder.pack(expand=True)
        else:
            for bundle in self.bundles.bundles:
                card = ctk.CTkFrame(self, fg_color=theme.BG_CARD, corner_radius=theme.BORDER_RADIUS)
                card.pack(fill="x", padx=20, pady=4)

                name_lbl = ctk.CTkLabel(
                    card, text=bundle.nombre,
                    font=theme.font_bold(theme.FONT_SIZE_MD),
                    text_color=theme.TEXT_PRIMARY, anchor="w",
                )
                name_lbl.pack(padx=12, pady=(8, 2), anchor="w")

                info = (f"{len(bundle.productos)} productos  |  "
                        f"Costo: ${bundle.precio_costo_total:,.0f}  |  "
                        f"Venta: ${bundle.precio_venta_final:,.0f}")
                info_lbl = ctk.CTkLabel(
                    card, text=info,
                    font=theme.font(theme.FONT_SIZE_SM),
                    text_color=theme.TEXT_SECONDARY, anchor="w",
                )
                info_lbl.pack(padx=12, pady=(0, 8), anchor="w")

    def refresh(self) -> None:
        self.bundles.reload()
        for w in self.winfo_children():
            w.destroy()
        self._build()
