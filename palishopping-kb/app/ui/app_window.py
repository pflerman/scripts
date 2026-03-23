"""Ventana principal con sidebar de navegación y área de contenido — Tkinter puro."""

import logging
import tkinter as tk
from tkinter import ttk

from app.models.bundle import BundleManager
from app.models.catalogo import Catalogo
from app.models.listing import ListingManager
from app.ui import theme
from app.ui.views.bundles_view import BundlesView
from app.ui.views.dashboard_view import DashboardView
from app.ui.views.fotos_view import FotosView
from app.ui.views.ia_view import IAView
from app.ui.views.listings_view import ListingsView
from app.ui.views.productos_view import ProductosView

logger = logging.getLogger(__name__)

NAV_ITEMS = [
    ("dashboard", "Dashboard"),
    ("productos", "Productos"),
    ("fotos", "Fotos"),
    ("ia", "IA"),
    ("bundles", "Bundles"),
    ("listings", "Listings"),
]


class AppWindow(tk.Tk):
    """Ventana principal de Palishopping KB Manager."""

    def __init__(self) -> None:
        super().__init__()

        self.title("Palishopping KB Manager")
        self.geometry("1200x800")
        self.minsize(900, 600)
        self.configure(bg=theme.BG_PRIMARY)

        # Modelos de datos
        self._catalogo = Catalogo()
        self._bundles = BundleManager()
        self._listings = ListingManager()

        # Estado
        self._active_view: str = ""
        self._nav_buttons: dict[str, tk.Label] = {}
        self._current_view: tk.Frame | None = None

        self._build()
        self.navigate("dashboard")

    def _build(self) -> None:
        # ── Sidebar ──────────────────────────────────────────────────────────
        sidebar = tk.Frame(self, bg=theme.BG_SIDEBAR, width=theme.SIDEBAR_WIDTH)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        # Logo
        tk.Label(
            sidebar, text="Palishopping",
            font=theme.FONT_TITLE, bg=theme.BG_SIDEBAR,
            fg=theme.TEXT_ON_SIDEBAR_ACTIVE, anchor="w",
        ).pack(fill="x", padx=14, pady=(18, 0))

        tk.Label(
            sidebar, text="KB Manager",
            font=theme.FONT_SMALL, bg=theme.BG_SIDEBAR,
            fg=theme.TEXT_ON_SIDEBAR_MUTED, anchor="w",
        ).pack(fill="x", padx=14, pady=(0, 16))

        # Separator
        tk.Frame(sidebar, bg="#3d566e", height=1).pack(fill="x", padx=10, pady=(0, 8))

        # Nav items
        for key, label in NAV_ITEMS:
            btn = tk.Label(
                sidebar, text=f"  {label}",
                font=theme.FONT_NORMAL, bg=theme.BG_SIDEBAR,
                fg=theme.TEXT_ON_SIDEBAR_MUTED, anchor="w",
                padx=10, pady=6, cursor="hand2",
            )
            btn.pack(fill="x", padx=6, pady=1)
            btn.bind("<Button-1>", lambda e, k=key: self.navigate(k))
            btn.bind("<Enter>", lambda e, b=btn: self._on_nav_hover(b, True))
            btn.bind("<Leave>", lambda e, b=btn: self._on_nav_hover(b, False))
            self._nav_buttons[key] = btn

        # Spacer
        tk.Frame(sidebar, bg=theme.BG_SIDEBAR).pack(fill="both", expand=True)

        # Reload button
        reload_btn = tk.Label(
            sidebar, text="↻ Recargar datos",
            font=theme.FONT_SMALL, bg=theme.BG_SIDEBAR,
            fg=theme.TEXT_ON_SIDEBAR_MUTED, anchor="w",
            padx=10, pady=6, cursor="hand2",
        )
        reload_btn.pack(fill="x", padx=6, pady=(0, 12))
        reload_btn.bind("<Button-1>", lambda e: self._refresh_all())

        # ── Main area ────────────────────────────────────────────────────────
        main_area = tk.Frame(self, bg=theme.BG_PRIMARY)
        main_area.pack(side="left", fill="both", expand=True)

        # ── Statusbar (pack bottom FIRST so content gets remaining space) ──
        statusbar = tk.Frame(main_area, bg=theme.BG_SECONDARY, height=theme.STATUSBAR_HEIGHT)
        statusbar.pack(side="bottom", fill="x")
        statusbar.pack_propagate(False)

        self._content_frame = tk.Frame(main_area, bg=theme.BG_PRIMARY)
        self._content_frame.pack(fill="both", expand=True)

        tk.Frame(statusbar, bg=theme.BORDER, height=1).pack(side="top", fill="x")

        self._status_label = tk.Label(
            statusbar, text="", font=theme.FONT_SMALL,
            bg=theme.BG_SECONDARY, fg=theme.TEXT_SECONDARY, anchor="w",
        )
        self._status_label.pack(side="left", padx=12, pady=4)
        self._update_statusbar()

    def _on_nav_hover(self, btn: tk.Label, entering: bool) -> None:
        """Hover effect en sidebar items (solo si no es el activo)."""
        if btn.cget("fg") == theme.TEXT_ON_SIDEBAR_ACTIVE:
            return
        btn.configure(bg="#34495e" if entering else theme.BG_SIDEBAR)

    def navigate(self, view_name: str) -> None:
        """Navega a una vista específica."""
        if view_name == self._active_view:
            return

        # Update sidebar
        for key, btn in self._nav_buttons.items():
            if key == view_name:
                btn.configure(
                    bg="#34495e", fg=theme.TEXT_ON_SIDEBAR_ACTIVE,
                    font=theme.FONT_BOLD,
                )
            else:
                btn.configure(
                    bg=theme.BG_SIDEBAR, fg=theme.TEXT_ON_SIDEBAR_MUTED,
                    font=theme.FONT_NORMAL,
                )

        # Destroy current view
        if self._current_view:
            self._current_view.destroy()

        # Create new view
        view = self._create_view(view_name)
        if view:
            view.pack(fill="both", expand=True, in_=self._content_frame)
            self._current_view = view
            self._active_view = view_name

        self._update_statusbar()

    def _create_view(self, name: str) -> tk.Frame | None:
        match name:
            case "dashboard":
                return DashboardView(
                    self._content_frame,
                    catalogo=self._catalogo,
                    bundles=self._bundles,
                    listings=self._listings,
                )
            case "productos":
                return ProductosView(self._content_frame, catalogo=self._catalogo)
            case "fotos":
                return FotosView(self._content_frame, catalogo=self._catalogo)
            case "ia":
                return IAView(self._content_frame, catalogo=self._catalogo)
            case "bundles":
                return BundlesView(self._content_frame, bundles=self._bundles,
                                   catalogo=self._catalogo)
            case "listings":
                return ListingsView(self._content_frame, listings=self._listings,
                                     bundles=self._bundles,
                                     catalogo=self._catalogo)
            case _:
                return None

    def _update_statusbar(self) -> None:
        n_prod = self._catalogo.count()
        n_bun = self._bundles.count()
        n_list = self._listings.count()
        self._status_label.configure(
            text=f"{n_prod} productos  |  {n_bun} bundles  |  {n_list} listings"
        )

    def _refresh_all(self) -> None:
        """Recarga todos los datos y refresca la vista activa."""
        self._catalogo.reload()
        self._bundles.reload()
        self._listings.reload()
        self._update_statusbar()
        if self._current_view and hasattr(self._current_view, "refresh"):
            self._current_view.refresh()
        logger.info("Datos recargados")
