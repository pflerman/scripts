"""Tema visual — Tkinter puro + ttk, estilo Analisis_ML."""

import tkinter as tk
from tkinter import ttk

# ── Paleta de colores (estilo Analisis_ML — fondo claro, Material Design) ────

BG_PRIMARY = "#f0f4f8"
BG_SECONDARY = "#f5f5f5"
BG_CARD = "#ffffff"
BG_SIDEBAR = "#2c3e50"
BG_INPUT = "#ffffff"
BG_HOVER = "#e8edf2"

# Texto
TEXT_PRIMARY = "#2c3e50"
TEXT_SECONDARY = "#7f8c8d"
TEXT_MUTED = "#95a5a6"
TEXT_ON_SIDEBAR = "#ecf0f1"
TEXT_ON_SIDEBAR_ACTIVE = "#ffffff"
TEXT_ON_SIDEBAR_MUTED = "#95a5a6"

# Acentos
ACCENT = "#ff9500"
ACCENT_HOVER = "#e08600"

# Botones Material Design
BTN_SUCCESS = "#4CAF50"
BTN_INFO = "#2196F3"
BTN_WARNING = "#FF9800"
BTN_DANGER = "#f44336"

# Estados
SUCCESS = "#27ae60"
WARNING = "#f39c12"
ERROR = "#e74c3c"
INFO = "#2980b9"

# Bordes
BORDER = "#dcdde1"
BORDER_DARK = "#bdc3c7"

# Tags de Treeview
TAG_EVEN = "#ffffff"
TAG_ODD = "#f8f9fa"
TAG_SELECTED = "#d4edda"
COUNT_LABEL_COLOR = "#0066cc"

# ── Fuentes (Arial, como Analisis_ML) ────────────────────────────────────────

FONT_FAMILY = "Arial"
FONT_NORMAL = (FONT_FAMILY, 10)
FONT_BOLD = (FONT_FAMILY, 10, "bold")
FONT_SMALL = (FONT_FAMILY, 9)
FONT_SMALL_BOLD = (FONT_FAMILY, 9, "bold")
FONT_TITLE = (FONT_FAMILY, 14, "bold")
FONT_SUBTITLE = (FONT_FAMILY, 12, "bold")
FONT_LARGE = (FONT_FAMILY, 18, "bold")
FONT_COUNTER = (FONT_FAMILY, 28, "bold")

# ── Dimensiones ──────────────────────────────────────────────────────────────

SIDEBAR_WIDTH = 180
STATUSBAR_HEIGHT = 28
PADDING_SM = 4
PADDING_MD = 8
PADDING_LG = 16


def setup_theme() -> None:
    """Configura el estilo ttk global."""
    style = ttk.Style()
    style.theme_use("clam")

    # Treeview
    style.configure("Treeview",
                     background=BG_CARD,
                     foreground=TEXT_PRIMARY,
                     fieldbackground=BG_CARD,
                     font=FONT_NORMAL,
                     rowheight=26)
    style.configure("Treeview.Heading",
                     background=BG_SECONDARY,
                     foreground=TEXT_PRIMARY,
                     font=FONT_BOLD,
                     relief="flat")
    style.map("Treeview.Heading",
              background=[("active", BORDER)])
    style.map("Treeview",
              background=[("selected", "#cde4f7")],
              foreground=[("selected", TEXT_PRIMARY)])

    # Buttons
    style.configure("TButton",
                     font=FONT_NORMAL,
                     padding=(12, 4))

    # Accent button
    style.configure("Accent.TButton",
                     font=FONT_BOLD,
                     padding=(14, 5))

    # Entry
    style.configure("TEntry",
                     font=FONT_NORMAL,
                     padding=4)

    # Labels
    style.configure("TLabel",
                     font=FONT_NORMAL,
                     background=BG_PRIMARY,
                     foreground=TEXT_PRIMARY)

    style.configure("Title.TLabel",
                     font=FONT_TITLE,
                     background=BG_PRIMARY,
                     foreground=TEXT_PRIMARY)

    style.configure("Subtitle.TLabel",
                     font=FONT_SUBTITLE,
                     background=BG_PRIMARY,
                     foreground=TEXT_PRIMARY)

    style.configure("Muted.TLabel",
                     font=FONT_SMALL,
                     background=BG_PRIMARY,
                     foreground=TEXT_MUTED)

    style.configure("Count.TLabel",
                     font=FONT_NORMAL,
                     background=BG_SECONDARY,
                     foreground=COUNT_LABEL_COLOR)

    style.configure("Card.TLabel",
                     font=FONT_NORMAL,
                     background=BG_CARD,
                     foreground=TEXT_PRIMARY)

    style.configure("CardTitle.TLabel",
                     font=FONT_BOLD,
                     background=BG_CARD,
                     foreground=TEXT_PRIMARY)

    style.configure("CardAccent.TLabel",
                     font=FONT_BOLD,
                     background=BG_CARD,
                     foreground=ACCENT)

    style.configure("CardSuccess.TLabel",
                     font=FONT_NORMAL,
                     background=BG_CARD,
                     foreground=SUCCESS)

    style.configure("CardMuted.TLabel",
                     font=FONT_SMALL,
                     background=BG_CARD,
                     foreground=TEXT_MUTED)

    # Counter labels (dashboard)
    style.configure("Counter.TLabel",
                     font=FONT_COUNTER,
                     background=BG_CARD,
                     foreground=ACCENT)

    style.configure("CounterBlue.TLabel",
                     font=FONT_COUNTER,
                     background=BG_CARD,
                     foreground=INFO)

    style.configure("CounterGreen.TLabel",
                     font=FONT_COUNTER,
                     background=BG_CARD,
                     foreground=SUCCESS)

    # Warning frame
    style.configure("Warning.TLabel",
                     font=FONT_BOLD,
                     background="#fff3cd",
                     foreground="#856404")

    style.configure("WarningDetail.TLabel",
                     font=FONT_SMALL,
                     background="#fff3cd",
                     foreground="#856404")

    # Frames
    style.configure("Card.TFrame",
                     background=BG_CARD,
                     relief="solid",
                     borderwidth=1)

    style.configure("TFrame",
                     background=BG_PRIMARY)

    # Separator
    style.configure("TSeparator",
                     background=BORDER)
