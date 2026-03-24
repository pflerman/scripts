"""Ventana principal — Palishopping Clonar."""

import logging
import tkinter as tk

from app.ui import theme
from app.ui.views.clonar_view import ClonarView

logger = logging.getLogger(__name__)


class AppWindow(tk.Tk):
    """Ventana principal de Palishopping Clonar."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

        self.title("Palishopping Clonar")
        self.geometry("1100x800")
        self.minsize(800, 600)
        self.configure(bg=theme.BG_PRIMARY)

        self._build()

    def _build(self) -> None:
        self._view = ClonarView(self)
        self._view.pack(fill="both", expand=True)
