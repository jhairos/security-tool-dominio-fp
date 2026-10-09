"""
utils/logger.py
===============
Logging centralizado y por rutina.

- Todos los mensajes se escriben en ``logs/security_tool.log``.
- Adicionalmente, el analisis de dominios escribe ``logs/dominio_fp.log``.

Formato registrado: fecha, hora, rutina, nivel, mensaje y excepcion.
"""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from config import (
    APP_CODE,
    LOG_BACKUP_COUNT,
    LOG_MAX_BYTES,
    LOGS_DIR,
    MAIN_LOG_FILE,
)

_FORMAT = ("%(asctime)s | %(levelname)-8s | %(routine)-10s | "
           "%(name)-24s | %(message)s")
_DATEFMT = "%Y-%m-%d %H:%M:%S"


class _RoutineFilter(logging.Filter):
    """Inyecta el campo 'routine' en cada registro."""

    def __init__(self, routine: str) -> None:
        super().__init__()
        self.routine = routine

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        if not hasattr(record, "routine"):
            record.routine = self.routine
        return True


def _file_handler(path: Path) -> RotatingFileHandler:
    handler = RotatingFileHandler(
        path, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8")
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter(_FORMAT, datefmt=_DATEFMT))
    return handler


def get_logger(name: str = APP_CODE,
               routine: Optional[str] = None) -> logging.Logger:
    """
    Devuelve un logger configurado.

    Parameters
    ----------
    name:
        Nombre logico del modulo (ej. ``"gui"``, ``"dominio_fp.runner"``).
    routine:
        Codigo de rutina (ej. ``"DOMINIO_FP"``). Si se indica, ademas del log
        central se escribe ``logs/<rutina en minuscula>.log``.
    """
    routine_code = (routine or "CORE").upper()
    logger = logging.getLogger(f"{name}")
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    logger.addFilter(_RoutineFilter(routine_code))

    # Log central de la aplicacion
    logger.addHandler(_file_handler(MAIN_LOG_FILE))

    # Log especifico de la rutina
    if routine:
        logger.addHandler(_file_handler(LOGS_DIR / f"{routine.lower()}.log"))

    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter("%(levelname)s | %(message)s"))
    logger.addHandler(console)

    logger.propagate = False
    return logger


def routine_log_file(routine: str) -> Path:
    """Ruta del archivo de log de una rutina."""
    return LOGS_DIR / f"{routine.lower()}.log"
