"""Diálogos modales reutilizables — Tkinter puro."""

import tkinter as tk
from tkinter import ttk

from app.ui import theme


class InputDialog(tk.Toplevel):
    """Diálogo modal para pedir un valor al usuario."""

    def __init__(self, master: tk.Widget, title: str = "Entrada",
                 prompt: str = "Ingresá un valor:", default: str = ""):
        super().__init__(master)
        self.title(title)
        self.geometry("400x160")
        self.resizable(False, False)
        self.configure(bg=theme.BG_PRIMARY)
        self.transient(master.winfo_toplevel())
        self.grab_set()

        self.result: str | None = None

        tk.Label(self, text=prompt, font=theme.FONT_NORMAL,
                 bg=theme.BG_PRIMARY, fg=theme.TEXT_PRIMARY).pack(
            padx=20, pady=(18, 8))

        self._var = tk.StringVar(value=default)
        entry = ttk.Entry(self, textvariable=self._var, width=45)
        entry.pack(padx=20, pady=4)
        entry.focus_set()
        entry.bind("<Return>", lambda e: self._ok())

        btn_frame = tk.Frame(self, bg=theme.BG_PRIMARY)
        btn_frame.pack(pady=12)

        tk.Button(btn_frame, text="Aceptar", font=theme.FONT_BOLD,
                  bg=theme.BTN_SUCCESS, fg="white", relief="flat", bd=0,
                  padx=16, pady=3, command=self._ok).pack(side="left", padx=4)
        tk.Button(btn_frame, text="Cancelar", font=theme.FONT_NORMAL,
                  bg=theme.BG_SECONDARY, fg=theme.TEXT_PRIMARY, relief="solid", bd=1,
                  padx=16, pady=3, command=self._cancel).pack(side="left", padx=4)

    def _ok(self) -> None:
        self.result = self._var.get()
        self.destroy()

    def _cancel(self) -> None:
        self.result = None
        self.destroy()


class ConfirmDialog(tk.Toplevel):
    """Diálogo de confirmación Sí/No."""

    def __init__(self, master: tk.Widget, title: str = "Confirmar",
                 message: str = "¿Estás seguro?"):
        super().__init__(master)
        self.title(title)
        self.geometry("400x140")
        self.resizable(False, False)
        self.configure(bg=theme.BG_PRIMARY)
        self.transient(master.winfo_toplevel())
        self.grab_set()

        self.result: bool = False

        tk.Label(self, text=message, font=theme.FONT_NORMAL,
                 bg=theme.BG_PRIMARY, fg=theme.TEXT_PRIMARY,
                 wraplength=360).pack(padx=20, pady=(20, 12))

        btn_frame = tk.Frame(self, bg=theme.BG_PRIMARY)
        btn_frame.pack(pady=8)

        tk.Button(btn_frame, text="Sí", font=theme.FONT_BOLD,
                  bg=theme.BTN_SUCCESS, fg="white", relief="flat", bd=0,
                  padx=20, pady=3, command=self._yes).pack(side="left", padx=4)
        tk.Button(btn_frame, text="No", font=theme.FONT_NORMAL,
                  bg=theme.BG_SECONDARY, fg=theme.TEXT_PRIMARY, relief="solid", bd=1,
                  padx=20, pady=3, command=self._no).pack(side="left", padx=4)

    def _yes(self) -> None:
        self.result = True
        self.destroy()

    def _no(self) -> None:
        self.result = False
        self.destroy()
