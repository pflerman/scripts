"""Vista de gestión de listings — Tkinter puro."""

import tkinter as tk

from app.models.listing import ListingManager
from app.ui import theme


class ListingsView(tk.Frame):
    def __init__(self, master: tk.Widget, listings: ListingManager, **kwargs):
        super().__init__(master, bg=theme.BG_PRIMARY, **kwargs)
        self.listings = listings
        self._build()

    def _build(self) -> None:
        tk.Label(self, text="Listings", font=theme.FONT_TITLE,
                 bg=theme.BG_PRIMARY, fg=theme.TEXT_PRIMARY).pack(
            anchor="w", padx=20, pady=(20, 10))

        if self.listings.count() == 0:
            tk.Label(self, text="No hay listings creados\n\nDisponible en Fase 2",
                     font=theme.FONT_NORMAL, bg=theme.BG_PRIMARY,
                     fg=theme.TEXT_MUTED, justify="center").pack(expand=True)
        else:
            for listing in self.listings.listings:
                card = tk.Frame(self, bg=theme.BG_CARD, bd=1, relief="solid",
                                highlightbackground=theme.BORDER, highlightthickness=1)
                card.pack(fill="x", padx=20, pady=3)

                tk.Label(card, text=listing.titulo or listing.slug,
                         font=theme.FONT_BOLD, bg=theme.BG_CARD,
                         fg=theme.TEXT_PRIMARY, anchor="w").pack(
                    anchor="w", padx=10, pady=(6, 0))

                info = (f"${listing.precio:,.0f}  |  Stock: {listing.stock}  "
                        f"|  Estado: {listing.estado}")
                tk.Label(card, text=info, font=theme.FONT_SMALL,
                         bg=theme.BG_CARD, fg=theme.TEXT_SECONDARY,
                         anchor="w").pack(anchor="w", padx=10, pady=(0, 6))

    def refresh(self) -> None:
        self.listings.reload()
        for w in self.winfo_children():
            w.destroy()
        self._build()
