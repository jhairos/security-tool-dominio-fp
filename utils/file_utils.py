"""
utils/file_utils.py
===================
Utilidades genericas de sistema de archivos, comunes a TODAS las
rutinas: creacion de carpetas de salida con marca de tiempo, apertura de
archivos/carpetas en el explorador del sistema operativo, saneamiento de
nombres y lectura del final de un archivo de log.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable, List

from config import EXPORTS_DIR

RUN_STAMP_FMT = "%Y-%m-%d_%H%M%S"


# ---------------------------------------------------------------------
# Carpetas de salida
# ---------------------------------------------------------------------
def ensure_dir(path: Path) -> Path:
    """Crea el directorio (y sus padres) si no existe."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def routine_export_dir(routine: str) -> Path:
    """Carpeta raiz de exportaciones de una rutina: exports/<RUTINA>/."""
    return ensure_dir(EXPORTS_DIR / routine.upper())


def new_run_dir(routine: str, stamp: str | None = None) -> Path:
    """
    Crea y devuelve el directorio de una ejecucion:

        exports/<RUTINA>/YYYY-MM-DD_HHMMSS/

    Junto con su subcarpeta ``assets/``.
    """
    stamp = stamp or datetime.now().strftime(RUN_STAMP_FMT)
    run_dir = routine_export_dir(routine) / stamp
    ensure_dir(run_dir)
    ensure_dir(run_dir / "assets")
    return run_dir


def list_run_dirs(routine: str) -> List[Path]:
    """Lista las ejecuciones de una rutina, de la mas reciente a la mas
    antigua."""
    base = routine_export_dir(routine)
    if not base.exists():
        return []
    dirs = [p for p in base.iterdir() if p.is_dir()]
    return sorted(dirs, key=lambda p: p.name, reverse=True)


def last_run_dir(routine: str) -> Path | None:
    dirs = list_run_dirs(routine)
    return dirs[0] if dirs else None


# ---------------------------------------------------------------------
# Nombres y formatos
# ---------------------------------------------------------------------
def safe_slug(text: str) -> str:
    """Convierte un texto en un nombre de archivo seguro."""
    return re.sub(r"[^A-Za-z0-9_%.-]+", "_", text).strip("_") or "item"


def human_duration(seconds: float) -> str:
    """Formatea una duracion en ``MM:SS`` o ``HH:MM:SS``."""
    seconds = int(max(0, seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def human_size(num_bytes: int) -> str:
    """Formatea un tamano en unidades legibles."""
    value = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


# ---------------------------------------------------------------------
# Apertura de resultados
# ---------------------------------------------------------------------
def open_path(path: Path | str) -> bool:
    """
    Abre un archivo o carpeta con la aplicacion predeterminada del
    sistema operativo (Windows, macOS o Linux). Devuelve True si se
    lanzo el comando correctamente.
    """
    target = Path(path)
    if not target.exists():
        return False
    try:
        if os.name == "nt":
            os.startfile(str(target))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(target)])
        else:
            subprocess.Popen(["xdg-open", str(target)])
        return True
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------------
# Lectura de logs
# ---------------------------------------------------------------------
def tail_file(path: Path, max_lines: int = 400) -> str:
    """Devuelve las ultimas ``max_lines`` lineas de un archivo de texto."""
    if not Path(path).exists():
        return ""
    try:
        lines = Path(path).read_text(encoding="utf-8",
                                     errors="replace").splitlines()
    except Exception:  # noqa: BLE001
        return ""
    return "\n".join(lines[-max_lines:])


def join_lines(items: Iterable[str]) -> str:
    return "\n".join(str(i) for i in items)
