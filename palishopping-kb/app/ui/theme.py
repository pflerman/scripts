"""Tema visual de la aplicación — paleta oscura con acentos MercadoLibre."""

import customtkinter as ctk

# ── Paleta de colores ─────────────────────────────────────────────────────────

# Fondo principal y secundario
BG_PRIMARY = "#1a1a2e"
BG_SECONDARY = "#16213e"
BG_CARD = "#1f2b47"
BG_SIDEBAR = "#0f1627"
BG_INPUT = "#253350"
BG_HOVER = "#2a3f5f"

# Acentos (naranja/amber tipo MercadoLibre)
ACCENT = "#ff9500"
ACCENT_HOVER = "#ffaa33"
ACCENT_DARK = "#cc7700"

# Texto
TEXT_PRIMARY = "#e8e8e8"
TEXT_SECONDARY = "#a0a8b8"
TEXT_MUTED = "#6b7280"
TEXT_ON_ACCENT = "#1a1a2e"

# Estados
SUCCESS = "#22c55e"
WARNING = "#f59e0b"
ERROR = "#ef4444"
INFO = "#3b82f6"

# Bordes
BORDER = "#2a3f5f"
BORDER_LIGHT = "#374f73"

# ── Fuentes ───────────────────────────────────────────────────────────────────

FONT_FAMILY = "Segoe UI"  # Fallback to system default on Linux
FONT_SIZE_XS = 11
FONT_SIZE_SM = 12
FONT_SIZE_MD = 13
FONT_SIZE_LG = 15
FONT_SIZE_XL = 18
FONT_SIZE_XXL = 24
FONT_SIZE_TITLE = 20

# ── Dimensiones ───────────────────────────────────────────────────────────────

SIDEBAR_WIDTH = 200
STATUSBAR_HEIGHT = 30
PADDING_SM = 4
PADDING_MD = 8
PADDING_LG = 16
PADDING_XL = 24
BORDER_RADIUS = 8


def setup_theme() -> None:
    """Configura CustomTkinter con el tema de la app."""
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")


def font(size: int = FONT_SIZE_MD, weight: str = "normal") -> tuple:
    """Retorna tupla de fuente para CTk."""
    return (FONT_FAMILY, size, weight)


def font_bold(size: int = FONT_SIZE_MD) -> tuple:
    return font(size, "bold")


def style_card_frame(frame: ctk.CTkFrame) -> None:
    """Aplica estilo de card a un frame."""
    frame.configure(
        fg_color=BG_CARD,
        corner_radius=BORDER_RADIUS,
        border_width=1,
        border_color=BORDER,
    )


def style_accent_button(button: ctk.CTkButton) -> None:
    """Aplica estilo de botón principal con acento."""
    button.configure(
        fg_color=ACCENT,
        hover_color=ACCENT_HOVER,
        text_color=TEXT_ON_ACCENT,
        font=font_bold(FONT_SIZE_MD),
        corner_radius=6,
    )


def style_secondary_button(button: ctk.CTkButton) -> None:
    """Aplica estilo de botón secundario."""
    button.configure(
        fg_color=BG_INPUT,
        hover_color=BG_HOVER,
        text_color=TEXT_PRIMARY,
        font=font(FONT_SIZE_MD),
        corner_radius=6,
        border_width=1,
        border_color=BORDER,
    )


def style_sidebar_button(button: ctk.CTkButton, active: bool = False) -> None:
    """Aplica estilo a un botón de la sidebar."""
    if active:
        button.configure(
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            text_color=TEXT_ON_ACCENT,
            font=font_bold(FONT_SIZE_MD),
            anchor="w",
            corner_radius=6,
        )
    else:
        button.configure(
            fg_color="transparent",
            hover_color=BG_HOVER,
            text_color=TEXT_SECONDARY,
            font=font(FONT_SIZE_MD),
            anchor="w",
            corner_radius=6,
        )
