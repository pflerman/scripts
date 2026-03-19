"""Vista de gestión de listings (placeholder — implementación completa en fase 2)."""

import customtkinter as ctk

from app.models.listing import ListingManager
from app.ui import theme


class ListingsView(ctk.CTkFrame):
    """Drafts de publicación para MercadoLibre."""

    def __init__(self, master: ctk.CTkBaseClass, listings: ListingManager, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.listings = listings
        self._build()

    def _build(self) -> None:
        title = ctk.CTkLabel(
            self,
            text="Listings",
            font=theme.font_bold(theme.FONT_SIZE_XXL),
            text_color=theme.TEXT_PRIMARY,
            anchor="w",
        )
        title.pack(padx=20, pady=(20, 10), anchor="w")

        if self.listings.count() == 0:
            placeholder = ctk.CTkLabel(
                self,
                text="No hay listings creados\n\nDisponible en Fase 2",
                font=theme.font(theme.FONT_SIZE_LG),
                text_color=theme.TEXT_MUTED,
                justify="center",
            )
            placeholder.pack(expand=True)
        else:
            for listing in self.listings.listings:
                card = ctk.CTkFrame(self, fg_color=theme.BG_CARD, corner_radius=theme.BORDER_RADIUS)
                card.pack(fill="x", padx=20, pady=4)

                title_lbl = ctk.CTkLabel(
                    card, text=listing.titulo or listing.slug,
                    font=theme.font_bold(theme.FONT_SIZE_MD),
                    text_color=theme.TEXT_PRIMARY, anchor="w",
                )
                title_lbl.pack(padx=12, pady=(8, 2), anchor="w")

                info = f"${listing.precio:,.0f}  |  Stock: {listing.stock}  |  Estado: {listing.estado}"
                info_lbl = ctk.CTkLabel(
                    card, text=info,
                    font=theme.font(theme.FONT_SIZE_SM),
                    text_color=theme.TEXT_SECONDARY, anchor="w",
                )
                info_lbl.pack(padx=12, pady=(0, 8), anchor="w")

    def refresh(self) -> None:
        self.listings.reload()
        for w in self.winfo_children():
            w.destroy()
        self._build()
