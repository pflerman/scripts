"""Diálogos modales reutilizables."""

import customtkinter as ctk

from app.ui import theme


class InputDialog(ctk.CTkToplevel):
    """Diálogo modal para pedir un valor al usuario."""

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        title: str = "Entrada",
        prompt: str = "Ingresá un valor:",
        default: str = "",
    ):
        super().__init__(master)
        self.title(title)
        self.geometry("400x180")
        self.resizable(False, False)
        self.configure(fg_color=theme.BG_PRIMARY)

        self.result: str | None = None

        self.grab_set()
        self.transient(master.winfo_toplevel())

        label = ctk.CTkLabel(
            self,
            text=prompt,
            font=theme.font(theme.FONT_SIZE_MD),
            text_color=theme.TEXT_PRIMARY,
        )
        label.pack(padx=20, pady=(20, 10))

        self._entry = ctk.CTkEntry(
            self,
            font=theme.font(theme.FONT_SIZE_MD),
            fg_color=theme.BG_INPUT,
            text_color=theme.TEXT_PRIMARY,
            border_color=theme.BORDER,
            width=360,
        )
        self._entry.pack(padx=20, pady=5)
        self._entry.insert(0, default)
        self._entry.focus_set()
        self._entry.bind("<Return>", lambda e: self._ok())

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=15)

        ok_btn = ctk.CTkButton(btn_frame, text="Aceptar", width=100, command=self._ok)
        theme.style_accent_button(ok_btn)
        ok_btn.pack(side="left", padx=5)

        cancel_btn = ctk.CTkButton(btn_frame, text="Cancelar", width=100, command=self._cancel)
        theme.style_secondary_button(cancel_btn)
        cancel_btn.pack(side="left", padx=5)

    def _ok(self) -> None:
        self.result = self._entry.get()
        self.destroy()

    def _cancel(self) -> None:
        self.result = None
        self.destroy()


class ConfirmDialog(ctk.CTkToplevel):
    """Diálogo de confirmación Sí/No."""

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        title: str = "Confirmar",
        message: str = "¿Estás seguro?",
    ):
        super().__init__(master)
        self.title(title)
        self.geometry("400x150")
        self.resizable(False, False)
        self.configure(fg_color=theme.BG_PRIMARY)

        self.result: bool = False

        self.grab_set()
        self.transient(master.winfo_toplevel())

        label = ctk.CTkLabel(
            self,
            text=message,
            font=theme.font(theme.FONT_SIZE_MD),
            text_color=theme.TEXT_PRIMARY,
            wraplength=360,
        )
        label.pack(padx=20, pady=(25, 15))

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=10)

        yes_btn = ctk.CTkButton(btn_frame, text="Sí", width=100, command=self._yes)
        theme.style_accent_button(yes_btn)
        yes_btn.pack(side="left", padx=5)

        no_btn = ctk.CTkButton(btn_frame, text="No", width=100, command=self._no)
        theme.style_secondary_button(no_btn)
        no_btn.pack(side="left", padx=5)

    def _yes(self) -> None:
        self.result = True
        self.destroy()

    def _no(self) -> None:
        self.result = False
        self.destroy()
