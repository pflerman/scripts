"""Vista de gestión de fotos (placeholder — implementación completa en fase 2)."""

import customtkinter as ctk

from app.ui import theme


class FotosView(ctk.CTkFrame):
    """Pipeline de fotos completo. Implementación en fase 2."""

    def __init__(self, master: ctk.CTkBaseClass, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._build()

    def _build(self) -> None:
        title = ctk.CTkLabel(
            self,
            text="Fotos",
            font=theme.font_bold(theme.FONT_SIZE_XXL),
            text_color=theme.TEXT_PRIMARY,
            anchor="w",
        )
        title.pack(padx=20, pady=(20, 10), anchor="w")

        placeholder = ctk.CTkLabel(
            self,
            text="Pipeline de procesamiento de fotos\n\nDisponible en Fase 2",
            font=theme.font(theme.FONT_SIZE_LG),
            text_color=theme.TEXT_MUTED,
            justify="center",
        )
        placeholder.pack(expand=True)

    def refresh(self) -> None:
        pass
