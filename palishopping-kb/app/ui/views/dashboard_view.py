"""Vista de dashboard / home con resumen del sistema — Tkinter puro."""

import tkinter as tk
from tkinter import ttk

from app.models.catalogo import Catalogo
from app.models.bundle import BundleManager
from app.models.listing import ListingManager
from app.ui import theme


class DashboardView(tk.Frame):
    """Vista principal con contadores, warnings y actividad reciente."""

    def __init__(self, master: tk.Widget, catalogo: Catalogo,
                 bundles: BundleManager, listings: ListingManager, **kwargs):
        super().__init__(master, bg=theme.BG_PRIMARY, **kwargs)
        self.catalogo = catalogo
        self.bundles = bundles
        self.listings = listings
        self._build()

    def _build(self) -> None:
        # Título
        ttk.Label(self, text="Dashboard", style="Title.TLabel").pack(
            anchor="w", padx=20, pady=(20, 12))

        # ── Contadores ───────────────────────────────────────────────────────
        counters = tk.Frame(self, bg=theme.BG_PRIMARY)
        counters.pack(fill="x", padx=20, pady=(0, 12))
        counters.columnconfigure((0, 1, 2), weight=1)

        self._counter_card(counters, "Productos", str(self.catalogo.count()),
                           "Counter.TLabel", 0)
        self._counter_card(counters, "Bundles", str(self.bundles.count()),
                           "CounterBlue.TLabel", 1)
        self._counter_card(counters, "Listings", str(self.listings.count()),
                           "CounterGreen.TLabel", 2)

        # ── Warnings ─────────────────────────────────────────────────────────
        sin_fotos = self.catalogo.productos_sin_fotos()
        if sin_fotos:
            self._warning_card(
                f"⚠ {len(sin_fotos)} producto(s) sin fotos",
                ", ".join(p.sku for p in sin_fotos[:5])
                + ("..." if len(sin_fotos) > 5 else ""),
            )

        bundles_slugs = {b.slug for b in self.bundles.bundles}
        listings_slugs = self.listings.slugs_con_listing()
        sin_listing = bundles_slugs - listings_slugs
        if sin_listing:
            self._warning_card(
                f"⚠ {len(sin_listing)} bundle(s) sin listing",
                ", ".join(sorted(sin_listing)[:5]),
            )

        # ── Últimos productos ────────────────────────────────────────────────
        card = tk.Frame(self, bg=theme.BG_CARD, bd=1, relief="solid",
                        highlightbackground=theme.BORDER, highlightthickness=1)
        card.pack(fill="x", padx=20, pady=(0, 20))

        ttk.Label(card, text="Últimos productos", style="CardTitle.TLabel").pack(
            anchor="w", padx=14, pady=(10, 6))

        ultimos = self.catalogo.ultimos_productos(5)
        if not ultimos:
            ttk.Label(card, text="No hay productos en el catálogo",
                      style="CardMuted.TLabel").pack(anchor="w", padx=14, pady=(0, 10))
        else:
            for prod in ultimos:
                row = tk.Frame(card, bg=theme.BG_CARD)
                row.pack(fill="x", padx=14, pady=2)

                tk.Label(row, text=prod.sku, font=theme.FONT_BOLD,
                         bg=theme.BG_CARD, fg=theme.ACCENT, width=22,
                         anchor="w").pack(side="left")
                tk.Label(row, text=prod.nombre, font=theme.FONT_NORMAL,
                         bg=theme.BG_CARD, fg=theme.TEXT_SECONDARY,
                         anchor="w").pack(side="left", fill="x", expand=True)
                tk.Label(row, text=f"${prod.precio_costo:,.0f}", font=theme.FONT_NORMAL,
                         bg=theme.BG_CARD, fg=theme.SUCCESS, width=10,
                         anchor="e").pack(side="right")

            tk.Frame(card, bg=theme.BG_CARD, height=6).pack()

    def _counter_card(self, parent: tk.Frame, label: str, value: str,
                      value_style: str, col: int) -> None:
        card = tk.Frame(parent, bg=theme.BG_CARD, bd=1, relief="solid",
                        highlightbackground=theme.BORDER, highlightthickness=1)
        card.grid(row=0, column=col, sticky="ew",
                  padx=(0 if col == 0 else 6, 0), pady=0)

        ttk.Label(card, text=value, style=value_style).pack(padx=16, pady=(12, 0))
        ttk.Label(card, text=label, style="CardMuted.TLabel").pack(padx=16, pady=(0, 10))

    def _warning_card(self, title: str, detail: str) -> None:
        card = tk.Frame(self, bg="#fff3cd", bd=1, relief="solid",
                        highlightbackground="#ffc107", highlightthickness=1)
        card.pack(fill="x", padx=20, pady=(0, 8))

        ttk.Label(card, text=title, style="Warning.TLabel").pack(
            anchor="w", padx=12, pady=(8, 2))
        ttk.Label(card, text=detail, style="WarningDetail.TLabel").pack(
            anchor="w", padx=12, pady=(0, 8))

    def refresh(self) -> None:
        self.catalogo.reload()
        self.bundles.reload()
        self.listings.reload()
        if not self.winfo_exists():
            return
        for w in self.winfo_children():
            try:
                w.destroy()
            except tk.TclError:
                pass
        self._build()
