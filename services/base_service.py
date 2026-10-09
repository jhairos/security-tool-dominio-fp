"""
services/base_service.py
========================
Capa intermedia GENERICA entre la GUI y las rutinas.

Responsabilidades:

- Ejecutar la rutina en un HILO DE TRABAJO para que la GUI no se
  congele.
- Traducir los callbacks de la rutina (progreso y log) en eventos
  depositados en una ``queue.Queue`` thread-safe.
- Exponer ``poll()`` para que el hilo principal de Tkinter consuma esos
  eventos y actualice los widgets de forma segura.

El hilo de trabajo NUNCA toca widgets de Tkinter.

El servicio del analisis hereda de ``RoutineService`` e implementa
unicamente ``_execute()``.
"""
from __future__ import annotations

import queue
import threading
import traceback
from typing import Any, Callable, Dict, List, Optional, Tuple

from routines.common import RoutineResult, Status
from utils.logger import get_logger

# Tipos de evento emitidos hacia la GUI
EVT_PROGRESS = "progress"   # (EVT_PROGRESS, porcentaje:int, mensaje:str)
EVT_LOG = "log"             # (EVT_LOG, texto:str)
EVT_DONE = "done"           # (EVT_DONE, RoutineResult)
EVT_ERROR = "error"         # (EVT_ERROR, mensaje:str, traza:str)
EVT_INPUT = "input"         # (EVT_INPUT, prompt:str) -> espera respuesta

Event = Tuple[Any, ...]


class RoutineService:
    """Servicio base para la ejecucion asincrona de una rutina."""

    #: Codigo de rutina; las subclases lo sobrescriben 
    routine_code: str = "CORE"

    def __init__(self) -> None:
        self.log = get_logger(f"service.{self.routine_code.lower()}",
                              routine=self.routine_code)
        self.queue: "queue.Queue[Event]" = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._cancel = False
        self.last_result: Optional[RoutineResult] = None
        #: Canal de peticion de datos al operador (codigos OTP).
        self._input_event: Optional[threading.Event] = None
        self._input_value: Optional[str] = None
        #: Tiempo maximo de espera de la respuesta del operador.
        self.input_timeout_s: float = 300.0

    # -----------------------------------------------------------------
    # Estado
    # -----------------------------------------------------------------
    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def cancel(self) -> None:
        """Solicita la cancelacion controlada de la ejecucion en curso."""
        if self.is_running():
            self._cancel = True
            self.log.info("Cancelacion solicitada para %s.",
                          self.routine_code)

    def _cancel_requested(self) -> bool:
        return self._cancel

    # -----------------------------------------------------------------
    # Ejecucion
    # -----------------------------------------------------------------
    def start(self, **kwargs) -> bool:
        """
        Lanza la rutina en segundo plano. Devuelve False si ya hay una
        ejecucion en curso.
        """
        if self.is_running():
            self.log.warning("Ya existe una ejecucion en curso de %s.",
                             self.routine_code)
            return False

        self._cancel = False
        self.last_result = None
        self._drain_queue()

        self._thread = threading.Thread(
            target=self._worker, kwargs=kwargs,
            name=f"{self.routine_code}-worker", daemon=True)
        self._thread.start()
        self.log.info("Ejecucion de %s iniciada en segundo plano.",
                      self.routine_code)
        return True

    def _worker(self, **kwargs) -> None:
        """Cuerpo del hilo de trabajo. No toca widgets de Tkinter."""
        try:
            result = self._execute(
                progress_callback=self._emit_progress,
                log_callback=self._emit_log,
                cancel_callback=self._cancel_requested,
                input_callback=self._request_input,
                **kwargs)
            self.last_result = result
            self.queue.put((EVT_DONE, result))
        except Exception as exc:  # noqa: BLE001
            trace = traceback.format_exc()
            self.log.exception("Error no controlado en %s",
                               self.routine_code)
            self.queue.put((EVT_ERROR, str(exc), trace))

    def _execute(self, progress_callback, log_callback,
                 cancel_callback, **kwargs) -> RoutineResult:
        """Debe implementarse en cada servicio concreto."""
        raise NotImplementedError

    # -----------------------------------------------------------------
    # Emision de eventos (desde el hilo de trabajo)
    # -----------------------------------------------------------------
    def _emit_progress(self, percent: int, message: str = "") -> None:
        self.queue.put((EVT_PROGRESS, int(percent), str(message)))

    def _emit_log(self, message: str) -> None:
        self.queue.put((EVT_LOG, str(message)))

    # -----------------------------------------------------------------
    # Peticion de datos al operador (segundo factor)
    # -----------------------------------------------------------------
    def _request_input(self, prompt: str) -> Optional[str]:
        """
        Solicita un dato a la interfaz y BLOQUEA el hilo de trabajo
        hasta recibir la respuesta.

        Solo se bloquea el hilo de la rutina: el hilo principal sigue
        atendiendo la interfaz, que muestra el cuadro de dialogo.
        """
        evento = threading.Event()
        self._input_event = evento
        self._input_value = None
        self.queue.put((EVT_INPUT, str(prompt)))

        if not evento.wait(self.input_timeout_s):
            self.log.warning("Tiempo agotado esperando la respuesta del "
                             "operador: %s", prompt)
            self._input_event = None
            return None

        valor = self._input_value
        self._input_event = None
        self._input_value = None
        return valor

    def provide_input(self, value: Optional[str]) -> None:
        """Entrega a la rutina el dato ingresado por el operador."""
        self._input_value = value
        if self._input_event:
            self._input_event.set()

    def waiting_for_input(self) -> bool:
        return self._input_event is not None

    # -----------------------------------------------------------------
    # Consumo de eventos (desde el hilo principal / GUI)
    # -----------------------------------------------------------------
    def poll(self, max_events: int = 200) -> List[Event]:
        """
        Devuelve los eventos pendientes sin bloquear. Debe invocarse
        desde el hilo principal de la GUI (por ejemplo con
        ``root.after``).
        """
        events: List[Event] = []
        for _ in range(max_events):
            try:
                events.append(self.queue.get_nowait())
            except queue.Empty:
                break
        return events

    def _drain_queue(self) -> None:
        while True:
            try:
                self.queue.get_nowait()
            except queue.Empty:
                return

    # -----------------------------------------------------------------
    # Utilidades
    # -----------------------------------------------------------------
    def result_summary(self) -> Dict[str, Any]:
        if not self.last_result:
            return {"status": Status.LISTO.value}
        return self.last_result.to_dict()


#: Firma esperada de un callback de eventos, si se desea consumo directo
EventHandler = Callable[[Event], None]
