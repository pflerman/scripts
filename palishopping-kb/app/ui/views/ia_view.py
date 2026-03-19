"""Vista de generación con IA (placeholder — fase 2)."""

import tkinter as tk

from app.ui import theme


class IAView(tk.Frame):
    def __init__(self, master: tk.Widget, **kwargs):
        super().__init__(master, bg=theme.BG_PRIMARY, **kwargs)
        tk.Label(self, text="Inteligencia Artificial", font=theme.FONT_TITLE,
                 bg=theme.BG_PRIMARY, fg=theme.TEXT_PRIMARY).pack(
            anchor="w", padx=20, pady=(20, 10))
        tk.Label(self, text="Generación de títulos, descripciones y prompts con Claude\n\nDisponible en Fase 2",
                 font=theme.FONT_NORMAL, bg=theme.BG_PRIMARY,
                 fg=theme.TEXT_MUTED, justify="center").pack(expand=True)

    def refresh(self) -> None:
        pass
