"""Ventana principal con sidebar de navegación y área de contenido."""

import logging

import customtkinter as ctk

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

# Navegación: (key, label, icon)
NAV_ITEMS = [
    ("dashboard",  "Dashboard",  "\u2302"),   # ⌂
    ("productos",  "Productos",  "\u2630"),   # ☰
    ("fotos",      "Fotos",      "\u25a3"),   # ▣
    ("ia",         "IA",         "\u2726"),   # ✦
    ("bundles",    "Bundles",    "\u229e"),   # ⊞
    ("listings",   "Listings",   "\u2197"),   # ↗
]


class AppWindow(ctk.CTk):
    """Ventana principal de Palishopping KB Manager."""

    def __init__(self) -> None:
        super().__init__()

        self.title("Palishopping KB Manager")
        self.geometry("1200x800")
        self.minsize(900, 600)
        self.configure(fg_color=theme.BG_PRIMARY)

        # Modelos de datos
        self._catalogo = Catalogo()
        self._bundles = BundleManager()
        self._listings = ListingManager()

        # Estado
        self._active_view: str = ""
        self._nav_buttons: dict[str, ctk.CTkButton] = {}
        self._current_view: ctk.CTkFrame | None = None

        self._build()
        self.navigate("dashboard")

    def _build(self) -> None:
        # Layout principal: sidebar | content | statusbar
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        # ── Sidebar ──────────────────────────────────────────────────────────
        sidebar = ctk.CTkFrame(
            self,
            width=theme.SIDEBAR_WIDTH,
            fg_color=theme.BG_SIDEBAR,
            corner_radius=0,
        )
        sidebar.grid(row=0, column=0, sticky="nsw", rowspan=2)
        sidebar.grid_propagate(False)

        # Logo / título
        logo_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        logo_frame.pack(fill="x", padx=12, pady=(20, 25))

        logo_label = ctk.CTkLabel(
            logo_frame,
            text="Palishopping",
            font=theme.font_bold(theme.FONT_SIZE_TITLE),
            text_color=theme.ACCENT,
            anchor="w",
        )
        logo_label.pack(anchor="w")

        subtitle = ctk.CTkLabel(
            logo_frame,
            text="KB Manager",
            font=theme.font(theme.FONT_SIZE_SM),
            text_color=theme.TEXT_MUTED,
            anchor="w",
        )
        subtitle.pack(anchor="w")

        # Navegación
        for key, label, icon in NAV_ITEMS:
            btn = ctk.CTkButton(
                sidebar,
                text=f"  {icon}  {label}",
                height=38,
                command=lambda k=key: self.navigate(k),
            )
            theme.style_sidebar_button(btn, active=False)
            btn.pack(fill="x", padx=10, pady=2)
            self._nav_buttons[key] = btn

        # Spacer
        spacer = ctk.CTkFrame(sidebar, fg_color="transparent")
        spacer.pack(fill="both", expand=True)

        # Refresh button
        refresh_btn = ctk.CTkButton(
            sidebar,
            text="  \u21BB  Recargar datos",
            height=34,
            command=self._refresh_all,
        )
        theme.style_secondary_button(refresh_btn)
        refresh_btn.pack(fill="x", padx=10, pady=(4, 15))

        # ── Content area ─────────────────────────────────────────────────────
        self._content_frame = ctk.CTkFrame(
            self,
            fg_color=theme.BG_PRIMARY,
            corner_radius=0,
        )
        self._content_frame.grid(row=0, column=1, sticky="nsew")
        self._content_frame.columnconfigure(0, weight=1)
        self._content_frame.rowconfigure(0, weight=1)

        # ── Statusbar ────────────────────────────────────────────────────────
        self._statusbar = ctk.CTkFrame(
            self,
            height=theme.STATUSBAR_HEIGHT,
            fg_color=theme.BG_SIDEBAR,
            corner_radius=0,
        )
        self._statusbar.grid(row=1, column=1, sticky="ew")
        self._statusbar.grid_propagate(False)

        self._status_label = ctk.CTkLabel(
            self._statusbar,
            text="",
            font=theme.font(theme.FONT_SIZE_XS),
            text_color=theme.TEXT_MUTED,
            anchor="w",
        )
        self._status_label.pack(side="left", padx=12, pady=4)
        self._update_statusbar()

    def navigate(self, view_name: str) -> None:
        """Navega a una vista específica."""
        if view_name == self._active_view:
            return

        # Update sidebar buttons
        for key, btn in self._nav_buttons.items():
            theme.style_sidebar_button(btn, active=(key == view_name))

        # Destroy current view
        if self._current_view:
            self._current_view.destroy()

        # Create new view
        view = self._create_view(view_name)
        if view:
            view.grid(row=0, column=0, sticky="nsew", in_=self._content_frame)
            self._current_view = view
            self._active_view = view_name

        self._update_statusbar()

    def _create_view(self, name: str) -> ctk.CTkFrame | None:
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
                return FotosView(self._content_frame)
            case "ia":
                return IAView(self._content_frame)
            case "bundles":
                return BundlesView(self._content_frame, bundles=self._bundles)
            case "listings":
                return ListingsView(self._content_frame, listings=self._listings)
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
