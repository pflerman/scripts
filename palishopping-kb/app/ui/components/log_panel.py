"""Panel de log/output en tiempo real — Tkinter puro."""

import tkinter as tk
from tkinter import scrolledtext

from app.ui import theme


class LogPanel(tk.Frame):
    """Panel de texto scrolleable para logs y output de operaciones."""

    def __init__(self, master: tk.Widget, height: int = 8, **kwargs):
        super().__init__(master, bg=theme.BG_CARD, bd=1, relief="solid",
                         highlightbackground=theme.BORDER, highlightthickness=1,
                         **kwargs)
        self._text = scrolledtext.ScrolledText(
            self, height=height, font=theme.FONT_NORMAL,
            bg=theme.BG_INPUT, fg=theme.TEXT_PRIMARY, relief="flat",
            state="disabled", wrap="word",
        )
        self._text.pack(fill="both", expand=True, padx=4, pady=4)

    def log(self, mensaje: str) -> None:
        self._text.configure(state="normal")
        self._text.insert("end", mensaje + "\n")
        self._text.see("end")
        self._text.configure(state="disabled")

    def clear(self) -> None:
        self._text.configure(state="normal")
        self._text.delete("1.0", "end")
        self._text.configure(state="disabled")
