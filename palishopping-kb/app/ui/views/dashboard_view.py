"""Vista de dashboard / home con resumen del sistema."""

import customtkinter as ctk

from app.models.catalogo import Catalogo
from app.models.bundle import BundleManager
from app.models.listing import ListingManager
from app.ui import theme


class DashboardView(ctk.CTkFrame):
    """Vista principal con contadores, warnings y actividad reciente."""

    def __init__(self, master: ctk.CTkBaseClass, catalogo: Catalogo,
                 bundles: BundleManager, listings: ListingManager, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.catalogo = catalogo
        self.bundles = bundles
        self.listings = listings
        self._build()

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)

        # Título
        title = ctk.CTkLabel(
            self,
            text="Dashboard",
            font=theme.font_bold(theme.FONT_SIZE_XXL),
            text_color=theme.TEXT_PRIMARY,
            anchor="w",
        )
        title.grid(row=0, column=0, sticky="w", padx=20, pady=(20, 15))

        # Contadores
        counters_frame = ctk.CTkFrame(self, fg_color="transparent")
        counters_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 15))
        counters_frame.columnconfigure((0, 1, 2), weight=1)

        self._counter_productos = self._create_counter(
            counters_frame, "Productos", str(self.catalogo.count()), theme.ACCENT, 0
        )
        self._counter_bundles = self._create_counter(
            counters_frame, "Bundles", str(self.bundles.count()), theme.INFO, 1
        )
        self._counter_listings = self._create_counter(
            counters_frame, "Listings", str(self.listings.count()), theme.SUCCESS, 2
        )

        # Warnings
        warnings_frame = ctk.CTkFrame(self, fg_color="transparent")
        warnings_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 15))
        warnings_frame.columnconfigure(0, weight=1)

        sin_fotos = self.catalogo.productos_sin_fotos()
        if sin_fotos:
            self._create_warning(
                warnings_frame,
                f"{len(sin_fotos)} producto(s) sin fotos",
                ", ".join(p.sku for p in sin_fotos[:5])
                + ("..." if len(sin_fotos) > 5 else ""),
                0,
            )

        bundles_slugs = {b.slug for b in self.bundles.bundles}
        listings_slugs = self.listings.slugs_con_listing()
        sin_listing = bundles_slugs - listings_slugs
        if sin_listing:
            self._create_warning(
                warnings_frame,
                f"{len(sin_listing)} bundle(s) sin listing",
                ", ".join(sorted(sin_listing)[:5]),
                1 if sin_fotos else 0,
            )

        # Últimos productos
        recientes_frame = ctk.CTkFrame(self, fg_color=theme.BG_CARD,
                                        corner_radius=theme.BORDER_RADIUS)
        recientes_frame.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 20))
        recientes_frame.columnconfigure(0, weight=1)

        rec_title = ctk.CTkLabel(
            recientes_frame,
            text="Últimos productos",
            font=theme.font_bold(theme.FONT_SIZE_LG),
            text_color=theme.TEXT_PRIMARY,
            anchor="w",
        )
        rec_title.grid(row=0, column=0, sticky="w", padx=15, pady=(12, 8))

        ultimos = self.catalogo.ultimos_productos(5)
        if not ultimos:
            empty = ctk.CTkLabel(
                recientes_frame,
                text="No hay productos en el catálogo",
                font=theme.font(theme.FONT_SIZE_SM),
                text_color=theme.TEXT_MUTED,
                anchor="w",
            )
            empty.grid(row=1, column=0, sticky="w", padx=15, pady=(0, 12))
        else:
            for i, prod in enumerate(ultimos):
                row_frame = ctk.CTkFrame(recientes_frame, fg_color="transparent")
                row_frame.grid(row=i + 1, column=0, sticky="ew", padx=15, pady=2)
                row_frame.columnconfigure(1, weight=1)

                sku_lbl = ctk.CTkLabel(
                    row_frame,
                    text=prod.sku,
                    font=theme.font_bold(theme.FONT_SIZE_SM),
                    text_color=theme.ACCENT,
                    width=180,
                    anchor="w",
                )
                sku_lbl.grid(row=0, column=0, sticky="w")

                nombre_lbl = ctk.CTkLabel(
                    row_frame,
                    text=prod.nombre,
                    font=theme.font(theme.FONT_SIZE_SM),
                    text_color=theme.TEXT_SECONDARY,
                    anchor="w",
                )
                nombre_lbl.grid(row=0, column=1, sticky="w", padx=(10, 0))

                precio_lbl = ctk.CTkLabel(
                    row_frame,
                    text=f"${prod.precio_costo:,.0f}",
                    font=theme.font(theme.FONT_SIZE_SM),
                    text_color=theme.SUCCESS,
                    width=80,
                    anchor="e",
                )
                precio_lbl.grid(row=0, column=2, sticky="e")

            # Spacer al final
            spacer = ctk.CTkLabel(recientes_frame, text="", height=8)
            spacer.grid(row=len(ultimos) + 1, column=0)

    def _create_counter(self, parent: ctk.CTkFrame, label: str, value: str,
                        color: str, col: int) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(parent, fg_color=theme.BG_CARD,
                              corner_radius=theme.BORDER_RADIUS)
        frame.grid(row=0, column=col, sticky="ew", padx=(0 if col == 0 else 8, 0))

        val_lbl = ctk.CTkLabel(
            frame,
            text=value,
            font=theme.font_bold(theme.FONT_SIZE_XXL + 8),
            text_color=color,
        )
        val_lbl.pack(padx=20, pady=(15, 2))

        name_lbl = ctk.CTkLabel(
            frame,
            text=label,
            font=theme.font(theme.FONT_SIZE_SM),
            text_color=theme.TEXT_SECONDARY,
        )
        name_lbl.pack(padx=20, pady=(0, 12))

        return frame

    def _create_warning(self, parent: ctk.CTkFrame, title: str,
                        detail: str, row: int) -> None:
        frame = ctk.CTkFrame(parent, fg_color=theme.BG_CARD,
                              corner_radius=theme.BORDER_RADIUS,
                              border_width=1, border_color=theme.WARNING)
        frame.grid(row=row, column=0, sticky="ew", pady=(0, 8))
        frame.columnconfigure(1, weight=1)

        icon = ctk.CTkLabel(
            frame,
            text="!",
            font=theme.font_bold(theme.FONT_SIZE_LG),
            text_color=theme.WARNING,
            width=30,
        )
        icon.grid(row=0, column=0, padx=(12, 4), pady=10)

        text_frame = ctk.CTkFrame(frame, fg_color="transparent")
        text_frame.grid(row=0, column=1, sticky="ew", padx=(0, 12), pady=10)

        title_lbl = ctk.CTkLabel(
            text_frame,
            text=title,
            font=theme.font_bold(theme.FONT_SIZE_SM),
            text_color=theme.WARNING,
            anchor="w",
        )
        title_lbl.pack(anchor="w")

        detail_lbl = ctk.CTkLabel(
            text_frame,
            text=detail,
            font=theme.font(theme.FONT_SIZE_XS),
            text_color=theme.TEXT_MUTED,
            anchor="w",
        )
        detail_lbl.pack(anchor="w")

    def refresh(self) -> None:
        """Recarga los datos y reconstruye la vista."""
        self.catalogo.reload()
        self.bundles.reload()
        self.listings.reload()
        for widget in self.winfo_children():
            widget.destroy()
        self._build()
