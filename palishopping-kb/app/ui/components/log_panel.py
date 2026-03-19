"""Panel de log/output en tiempo real."""

import customtkinter as ctk

from app.ui import theme


class LogPanel(ctk.CTkFrame):
    """Panel de texto scrolleable para logs y output de operaciones."""

    def __init__(self, master: ctk.CTkBaseClass, height: int = 150, **kwargs):
        super().__init__(master, **kwargs)
        self.configure(fg_color=theme.BG_CARD, corner_radius=theme.BORDER_RADIUS)

        self._textbox = ctk.CTkTextbox(
            self,
            height=height,
            font=theme.font(theme.FONT_SIZE_SM),
            text_color=theme.TEXT_SECONDARY,
            fg_color=theme.BG_SECONDARY,
            corner_radius=6,
            state="disabled",
        )
        self._textbox.pack(fill="both", expand=True, padx=6, pady=6)

    def log(self, mensaje: str, tag: str = "") -> None:
        """Agrega una línea al log."""
        self._textbox.configure(state="normal")
        self._textbox.insert("end", mensaje + "\n")
        self._textbox.see("end")
        self._textbox.configure(state="disabled")

    def clear(self) -> None:
        """Limpia el log."""
        self._textbox.configure(state="normal")
        self._textbox.delete("1.0", "end")
        self._textbox.configure(state="disabled")
