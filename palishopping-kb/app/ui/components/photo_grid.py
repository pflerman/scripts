"""Widget de grilla de thumbnails — Tkinter puro."""

import tkinter as tk
from pathlib import Path
from PIL import Image, ImageTk

from app.config import IMG_EXTENSIONS
from app.ui import theme


class PhotoGrid(tk.Frame):
    """Grilla scrolleable de thumbnails de fotos."""

    THUMB_SIZE = 100

    def __init__(self, master: tk.Widget, **kwargs):
        super().__init__(master, bg=theme.BG_CARD, bd=1, relief="solid",
                         highlightbackground=theme.BORDER, highlightthickness=1,
                         **kwargs)
        self._photo_refs: list[ImageTk.PhotoImage] = []  # prevent GC

        # Canvas scrolleable
        self._canvas = tk.Canvas(self, bg=theme.BG_CARD, highlightthickness=0)
        self._scrollbar = tk.Scrollbar(self, orient="vertical",
                                        command=self._canvas.yview)
        self._inner = tk.Frame(self._canvas, bg=theme.BG_CARD)

        self._inner.bind("<Configure>",
                         lambda e: self._canvas.configure(
                             scrollregion=self._canvas.bbox("all")))
        self._canvas.create_window((0, 0), window=self._inner, anchor="nw")
        self._canvas.configure(yscrollcommand=self._scrollbar.set)

        self._scrollbar.pack(side="right", fill="y")
        self._canvas.pack(fill="both", expand=True)

        # Mouse wheel scroll
        self._canvas.bind("<Enter>",
                          lambda e: self._canvas.bind_all("<Button-4>", self._on_scroll))
        self._canvas.bind("<Leave>",
                          lambda e: self._canvas.unbind_all("<Button-4>"))
        self._canvas.bind("<Enter>",
                          lambda e: (self._canvas.bind_all("<Button-4>", self._on_scroll),
                                     self._canvas.bind_all("<Button-5>", self._on_scroll)))
        self._canvas.bind("<Leave>",
                          lambda e: (self._canvas.unbind_all("<Button-4>"),
                                     self._canvas.unbind_all("<Button-5>")))

    def _on_scroll(self, event):
        if event.num == 4:
            self._canvas.yview_scroll(-3, "units")
        elif event.num == 5:
            self._canvas.yview_scroll(3, "units")

    def load_folder(self, folder: Path, label: str = "") -> int:
        """Carga thumbnails de una carpeta. Retorna cantidad de fotos."""
        # Limpiar
        for w in self._inner.winfo_children():
            w.destroy()
        self._photo_refs.clear()

        if not folder.exists():
            tk.Label(self._inner, text=f"{label}: carpeta no existe",
                     font=theme.FONT_SMALL, bg=theme.BG_CARD,
                     fg=theme.TEXT_MUTED).pack(padx=10, pady=10)
            return 0

        fotos = sorted(
            f for f in folder.iterdir()
            if f.is_file() and f.suffix.lower() in IMG_EXTENSIONS
        )

        if not fotos:
            tk.Label(self._inner, text=f"{label}: sin fotos",
                     font=theme.FONT_SMALL, bg=theme.BG_CARD,
                     fg=theme.TEXT_MUTED).pack(padx=10, pady=10)
            return 0

        # Header
        if label:
            tk.Label(self._inner, text=f"{label} ({len(fotos)})",
                     font=theme.FONT_BOLD, bg=theme.BG_CARD,
                     fg=theme.TEXT_PRIMARY).pack(anchor="w", padx=8, pady=(6, 2))

        # Grid frame
        grid = tk.Frame(self._inner, bg=theme.BG_CARD)
        grid.pack(fill="x", padx=4, pady=4)

        for i, foto in enumerate(fotos):
            try:
                img = Image.open(foto)
                img.thumbnail((self.THUMB_SIZE, self.THUMB_SIZE), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                self._photo_refs.append(photo)

                cell = tk.Frame(grid, bg=theme.BG_CARD)
                cell.grid(row=i // 5, column=i % 5, padx=3, pady=3)

                lbl = tk.Label(cell, image=photo, bg=theme.BG_CARD,
                               bd=1, relief="solid")
                lbl.pack()

                tk.Label(cell, text=foto.name, font=("Arial", 7),
                         bg=theme.BG_CARD, fg=theme.TEXT_MUTED).pack()
            except Exception:
                pass

        return len(fotos)
