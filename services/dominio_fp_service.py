"""
services/dominio_fp_service.py
==============================
Capa intermedia entre ``gui/dominio_fp_view.py`` y
``routines/dominio_fp/dominio_fp_runner.py``.

Esta rutina recibe un parametro de entrada: el dominio a analizar.
"""
from __future__ import annotations

from typing import Optional

from routines.common import RoutineResult
from routines.dominio_fp import dominio_fp_config as cfg
from routines.dominio_fp.dominio_fp_runner import run_dominio_fp
from services.base_service import RoutineService


class DominioFPService(RoutineService):
    """Servicio de ejecucion de la rutina DOMINIO_FP."""

    routine_code = cfg.ROUTINE_CODE

    # -----------------------------------------------------------------
    def _execute(self, progress_callback, log_callback, cancel_callback,
                 input_callback=None,
                 dominio: str = "",
                 ticket: str = "",
                 resolver: str = "",
                 headless: bool = cfg.HEADLESS,
                 **_ignored) -> RoutineResult:
        return run_dominio_fp(
            dominio=dominio,
            ticket=ticket,
            resolver=resolver,
            progress_callback=progress_callback,
            log_callback=log_callback,
            cancel_callback=cancel_callback,
            input_callback=input_callback,
            headless=headless,
        )

    # -----------------------------------------------------------------
    @staticmethod
    def dominio_valido(dominio: str) -> bool:
        return cfg.dominio_valido(dominio)

    @staticmethod
    def resolver_valido(valor: str) -> bool:
        return cfg.resolver_valido(valor)

    @staticmethod
    def normalizar(dominio: str) -> str:
        return cfg.normalizar_dominio(dominio)

    @staticmethod
    def estado_cli() -> tuple:
        """Indica si el equipo puede ejecutar la resolucion por consola."""
        from routines.dominio_fp import dominio_fp_cli
        return dominio_fp_cli.wsl_disponible()
