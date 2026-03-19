"""Widget de grilla de fotos (placeholder — fase 2)."""

import tkinter as tk

from app.ui import theme


class PhotoGrid(tk.Frame):
    def __init__(self, master: tk.Widget, **kwargs):
        super().__init__(master, bg=theme.BG_CARD, bd=1, relief="solid",
                         highlightbackground=theme.BORDER, highlightthickness=1,
                         **kwargs)
        tk.Label(self, text="Grilla de fotos (Fase 2)", font=theme.FONT_SMALL,
                 bg=theme.BG_CARD, fg=theme.TEXT_MUTED).pack(padx=20, pady=20)
