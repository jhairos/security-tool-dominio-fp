#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main.py
=======
Punto de entrada de Security Tool Jairo Suntaxi C.

Responsabilidad UNICA:

    inicializar aplicacion  ->  cargar MainWindow  ->  ejecutar GUI

Este archivo no contiene logica de negocio: ni Playwright, ni login, ni
capturas, ni generacion de HTML/DOCX/ZIP. Toda la logica operativa vive
en ``routines/`` y se invoca a traves de ``services/``.

Ejecucion:
    python main.py

Ejecucion SIN interfaz grafica:
    python -m routines.dominio_fp.dominio_fp_runner --dominio ejemplo.com
"""
from __future__ import annotations

import sys
from pathlib import Path

# Permite ejecutar el archivo desde cualquier directorio (o desde Thonny).
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from config import (APP_BUILD, APP_NAME, APP_VERSION,  # noqa: E402
                    DEFAULT_THEME, MAIN_LOG_FILE)  # noqa: E402
from utils.logger import get_logger  # noqa: E402

logger = get_logger("main")


def main() -> None:
    """Inicializa y ejecuta la aplicacion."""
    try:
        from gui.main_window import MainWindow

        logger.info("Iniciando %s v%s (entrega %s)",
                    APP_NAME, APP_VERSION, APP_BUILD)
        app = MainWindow(theme=DEFAULT_THEME)
        app.run()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Error fatal al iniciar la aplicacion")
        try:
            import tkinter as tk
            from tkinter import messagebox

            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                "Error fatal",
                "No se pudo iniciar la aplicacion.\n\n"
                f"Detalle: {exc}\n\nRevise {MAIN_LOG_FILE}")
            root.destroy()
        except Exception:  # noqa: BLE001
            print(f"Error fatal: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
