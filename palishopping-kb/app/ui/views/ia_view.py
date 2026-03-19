"""Vista de generación con IA (placeholder — implementación completa en fase 2)."""

import customtkinter as ctk

from app.ui import theme


class IAView(ctk.CTkFrame):
    """Generación de títulos, descripciones y prompts con Claude."""

    def __init__(self, master: ctk.CTkBaseClass, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._build()

    def _build(self) -> None:
        title = ctk.CTkLabel(
            self,
            text="Inteligencia Artificial",
            font=theme.font_bold(theme.FONT_SIZE_XXL),
            text_color=theme.TEXT_PRIMARY,
            anchor="w",
        )
        title.pack(padx=20, pady=(20, 10), anchor="w")

        placeholder = ctk.CTkLabel(
            self,
            text="Generación de títulos, descripciones y prompts con Claude\n\nDisponible en Fase 2",
            font=theme.font(theme.FONT_SIZE_LG),
            text_color=theme.TEXT_MUTED,
            justify="center",
        )
        placeholder.pack(expand=True)

    def refresh(self) -> None:
        pass
