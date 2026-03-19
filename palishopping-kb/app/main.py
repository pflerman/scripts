#!/usr/bin/env python3
"""Entry point de Palishopping KB Manager."""

import logging
import sys
from pathlib import Path

# Asegurar que el parent directory esté en sys.path para imports
app_dir = Path(__file__).resolve().parent
if str(app_dir.parent) not in sys.path:
    sys.path.insert(0, str(app_dir.parent))

from app.ui.theme import setup_theme
from app.ui.app_window import AppWindow

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)

logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("Iniciando Palishopping KB Manager")
    setup_theme()
    window = AppWindow()
    window.mainloop()


if __name__ == "__main__":
    main()
