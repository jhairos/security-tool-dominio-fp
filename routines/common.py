"""
routines/common.py
==================
Contratos comunes del analisis:

- ``Status``          : estados visuales uniformes.
- ``RoutineResult``   : estructura de resultado devuelta por el runner.
- ``Reporter``        : envoltorio de ``progress_callback`` y
                        ``log_callback`` con implementacion vacia por
                        defecto, de modo que la rutina se pueda ejecutar
                        sin GUI (consola, scheduler, API).
- ``RoutineCancelled``: excepcion de cancelacion controlada.

Ninguna clase de este modulo conoce Tkinter ni ningun componente
grafico.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


class Status(str, Enum):
    """Estados visuales uniformes para todas las rutinas."""
    LISTO = "LISTO"
    EJECUTANDO = "EJECUTANDO"
    OK = "OK"
    ADVERTENCIA = "ADVERTENCIA"
    ERROR = "ERROR"

    def __str__(self) -> str:  # pragma: no cover - conveniencia
        return self.value


class RoutineCancelled(Exception):
    """La rutina fue cancelada por el usuario."""


# Firmas estandar de los callbacks
ProgressCallback = Callable[[int, str], None]
LogCallback = Callable[[str], None]
CancelCallback = Callable[[], bool]

#: Solicitud de un dato al operador durante la ejecucion (por ejemplo,
#: un codigo OTP). Recibe el texto de la solicitud y devuelve el valor
#: ingresado, o None si el operador cancela.
InputCallback = Callable[[str], Optional[str]]


class Reporter:
    """
    Canal de comunicacion de la rutina hacia quien la invoque.

    La rutina solo emite mensajes; quien la ejecuta decide donde
    mostrarlos (GUI, consola, archivo, API).

        reporter.progress(20, "Consultando VirusTotal")
        reporter.log("Consultando fuentes...")
        reporter.check_cancel()
    """

    def __init__(self,
                 progress_callback: Optional[ProgressCallback] = None,
                 log_callback: Optional[LogCallback] = None,
                 cancel_callback: Optional[CancelCallback] = None,
                 input_callback: Optional[InputCallback] = None,
                 echo: bool = False) -> None:
        self._progress_cb = progress_callback
        self._log_cb = log_callback
        self._cancel_cb = cancel_callback
        self._input_cb = input_callback
        self.echo = echo
        self.messages: List[str] = []
        self.last_percent = 0

    # -- Progreso ------------------------------------------------------
    def progress(self, percent: int, message: str = "") -> None:
        percent = max(0, min(100, int(percent)))
        self.last_percent = percent
        if self._progress_cb:
            try:
                self._progress_cb(percent, message)
            except Exception:  # noqa: BLE001
                pass
        if message:
            self.log(f"{percent:3d}%  {message}")

    # -- Log -----------------------------------------------------------
    def log(self, message: str) -> None:
        text = str(message)
        self.messages.append(text)
        if self._log_cb:
            try:
                self._log_cb(text)
            except Exception:  # noqa: BLE001
                pass
        if self.echo:
            print(text)

    # -- Cancelacion ---------------------------------------------------
    def cancelled(self) -> bool:
        if not self._cancel_cb:
            return False
        try:
            return bool(self._cancel_cb())
        except Exception:  # noqa: BLE001
            return False

    def check_cancel(self) -> None:
        """Lanza ``RoutineCancelled`` si se solicito cancelar."""
        if self.cancelled():
            raise RoutineCancelled("Ejecucion cancelada por el usuario.")

    # -- Entrada interactiva -------------------------------------------
    def ask_input(self, prompt: str) -> Optional[str]:
        """
        Solicita un dato al operador durante la ejecucion.

        Su uso previsto es el segundo factor de autenticacion: un codigo
        OTP no puede automatizarse sin intervencion humana, y ese es
        precisamente su proposito de seguridad. La rutina se detiene, la
        interfaz pide el codigo y la ejecucion continua al recibirlo.

        Devuelve el valor ingresado o ``None`` si no hay quien responda
        (por ejemplo, en ejecucion desatendida).
        """
        self.log(f"Solicitando al operador: {prompt}")
        if not self._input_cb:
            return None
        try:
            return self._input_cb(prompt)
        except Exception:  # noqa: BLE001
            return None

    @property
    def can_ask_input(self) -> bool:
        """Indica si hay un canal disponible para pedir datos."""
        return self._input_cb is not None


@dataclass
class RoutineResult:
    """
    Resultado estandar devuelto por el runner de cualquier rutina.

    Las rutinas futuras deben devolver esta misma estructura para que la
    GUI, el scheduler o una API puedan consumirlas sin cambios.
    """
    routine: str
    status: Status = Status.LISTO
    fecha_inicio: Optional[datetime] = None
    fecha_fin: Optional[datetime] = None
    directorio_salida: Optional[Path] = None
    items_ok: List[str] = field(default_factory=list)
    items_error: List[str] = field(default_factory=list)
    archivos: Dict[str, Optional[Path]] = field(default_factory=dict)
    errores: List[str] = field(default_factory=list)
    mensaje: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)

    @property
    def html(self) -> Optional[Path]:
        return self.archivos.get("html")

    @property
    def gmail_html(self) -> Optional[Path]:
        return self.archivos.get("gmail_html")

    @property
    def docx(self) -> Optional[Path]:
        return self.archivos.get("docx")

    @property
    def zip(self) -> Optional[Path]:
        return self.archivos.get("zip")

    @property
    def duracion_seg(self) -> float:
        if not self.fecha_inicio:
            return 0.0
        fin = self.fecha_fin or datetime.now()
        return (fin - self.fecha_inicio).total_seconds()

    # -- Utilidades ----------------------------------------------------
    def add_error(self, message: str) -> None:
        self.errores.append(str(message))

    def to_dict(self) -> dict:
        return {
            "routine": self.routine,
            "status": self.status.value,
            "fecha_inicio": (self.fecha_inicio.isoformat()
                             if self.fecha_inicio else None),
            "fecha_fin": (self.fecha_fin.isoformat()
                          if self.fecha_fin else None),
            "duracion_seg": round(self.duracion_seg, 2),
            "evidencias_ok": self.items_ok,
            "evidencias_sin_obtener": self.items_error,
            "directorio_salida": (str(self.directorio_salida)
                                  if self.directorio_salida else None),
            "html": str(self.html) if self.html else None,
            "gmail_html": str(self.gmail_html) if self.gmail_html else None,
            "docx": str(self.docx) if self.docx else None,
            "zip": str(self.zip) if self.zip else None,
            "errores": self.errores,
            "mensaje": self.mensaje,
        }
