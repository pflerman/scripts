"""Widget de grilla de fotos con preview (placeholder para fase 2)."""

import customtkinter as ctk

from app.ui import theme


class PhotoGrid(ctk.CTkFrame):
    """Grilla de previews de fotos. Implementación completa en fase 2."""

    def __init__(self, master: ctk.CTkBaseClass, **kwargs):
        super().__init__(master, **kwargs)
        self.configure(fg_color=theme.BG_CARD, corner_radius=theme.BORDER_RADIUS)

        placeholder = ctk.CTkLabel(
            self,
            text="Grilla de fotos (Fase 2)",
            font=theme.font(theme.FONT_SIZE_SM),
            text_color=theme.TEXT_MUTED,
        )
        placeholder.pack(padx=20, pady=20)
