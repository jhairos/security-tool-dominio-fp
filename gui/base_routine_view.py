"""
gui/base_routine_view.py
========================
Vista base del analisis: ejecucion, progreso, log y resultados.

Implementa una sola vez todo lo que comparten las rutinas:

- boton Ejecutar / Cancelar;
- estado visual uniforme (LISTO, EJECUTANDO, OK, ADVERTENCIA, ERROR);
- barra de progreso alimentada por ``progress_callback``;
- consola de log alimentada por ``log_callback``;
- lectura de la cola del servicio mediante ``root.after`` (la GUI nunca
  se congela y el hilo de trabajo nunca toca widgets de Tkinter);
- botones para abrir los resultados generados.

``gui/dominio_fp_view.py`` hereda de esta clase y agrega los campos del
analisis.
"""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Dict, Optional

from config import GUI_POLL_MS
from gui import ui
from routines.common import RoutineResult, Status
from services.base_service import (
    EVT_DONE,
    EVT_ERROR,
    EVT_INPUT,
    EVT_LOG,
    EVT_PROGRESS,
    RoutineService,
)
from utils.file_utils import human_duration, open_path
from utils.logger import get_logger


class BaseRoutineView:
    """Panel generico de ejecucion de una rutina."""

    # --- Parametros que definen las subclases -------------------------
    routine_code: str = "CORE"
    routine_title: str = "RUTINA"
    routine_desc: str = ""

    # Botones de resultado: (texto, clave del diccionario de archivos)
    result_buttons = (
        ("Abrir reporte HTML", "html"),
        ("Abrir HTML Gmail", "gmail_html"),
        ("Abrir DOCX", "docx"),
        ("Abrir ZIP evidencias", "zip"),
    )

    # -----------------------------------------------------------------
    def __init__(self, parent: tk.Widget, app) -> None:
        self.app = app
        self.log = get_logger(f"gui.{self.routine_code.lower()}",
                              routine=self.routine_code)
        self.service: RoutineService = app.get_service(self.routine_code)
        self._polling = False
        self._result_paths: Dict[str, Optional[Path]] = {}

        self.frame = ui.frame(parent)
        self.frame.pack(fill="both", expand=True, padx=12, pady=12)
        self._build()
        self._restore_state()

    # =================================================================
    # Construccion de la interfaz
    # =================================================================
    def _build(self) -> None:
        header = ttk.Frame(self.frame)
        header.pack(fill="x")
        ui.section_title(header, self.routine_title).pack(side="left")
        self.status_badge = ui.badge(header, Status.LISTO.value,
                                     ui.status_color(Status.LISTO.value))
        self.status_badge.pack(side="right", padx=4)

        if self.routine_desc:
            ui.label(self.frame, self.routine_desc,
                     wraplength=900, justify="left").pack(anchor="w",
                                                          pady=(4, 8))

        self.build_extra_controls(self.frame)
        self._build_actions()
        self._build_progress()
        # Los resultados se anclan ABAJO antes que el log: asi quedan
        # siempre visibles y no hay que agrandar la ventana para
        # alcanzar los botones "Abrir reporte".
        self._build_results()
        self._build_log()

    # -- Acciones ------------------------------------------------------
    def _build_actions(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", pady=8)
        self.run_btn = ui.button(bar, f"Ejecutar rutina {self.routine_code}",
                                 self.start)
        self.run_btn.pack(side="left")
        self.cancel_btn = ui.button(bar, "Cancelar", self.cancel)
        self.cancel_btn.pack(side="left", padx=6)
        self.clear_btn = ui.button(bar, "Limpiar log", self.clear_log)
        self.clear_btn.pack(side="left", padx=6)
        self._set_state_buttons(running=False)

    # -- Progreso ------------------------------------------------------
    def _build_progress(self) -> None:
        box = ttk.Frame(self.frame)
        box.pack(fill="x", pady=(2, 6))
        self.progress = ui.progressbar(box)
        self.progress.pack(fill="x")
        self.progress_label = ui.label(box, "Listo")
        self.progress_label.pack(anchor="w", pady=(4, 0))

    # -- Log -----------------------------------------------------------
    def _build_log(self) -> None:
        ui.label(self.frame, "Log de ejecucion:",
                 font=("Segoe UI", 11, "bold")).pack(anchor="w")
        wrap = ttk.Frame(self.frame)
        wrap.pack(fill="both", expand=True, pady=(2, 6))
        # Altura minima reducida: el area de log cede espacio antes que
        # los botones de resultado.
        self.log_box = ui.scrolled_textbox(wrap, height=8)
        self.log_box.configure(state="disabled")

    # -- Resultados ----------------------------------------------------
    def _build_results(self) -> None:
        self.result_frame = ttk.Frame(self.frame)
        self.result_frame.pack(side="bottom", fill="x", pady=(6, 0))
        self.result_label = ui.label(self.result_frame, "",
                                     wraplength=980, justify="left")
        self.result_label.pack(anchor="w", pady=(0, 4))

        self.buttons_frame = ttk.Frame(self.result_frame)
        self.buttons_frame.pack(fill="x")
        self.result_widgets = {}

        for text, key in self.result_buttons:
            btn = ui.button(self.buttons_frame, text,
                            lambda k=key: self._open_result(k))
            btn.pack(side="left", padx=(0, 6))
            self.result_widgets[key] = btn

        folder_btn = ui.button(self.buttons_frame, "Abrir carpeta evidencias",
                               lambda: self._open_result("dir"))
        folder_btn.pack(side="left", padx=(0, 6))
        self.result_widgets["dir"] = folder_btn
        self._enable_result_buttons(False)

    # -- Gancho para subclases ----------------------------------------
    def build_extra_controls(self, parent: tk.Widget) -> None:
        """Controles adicionales especificos de la rutina (opcional)."""

    # =================================================================
    # Ejecucion
    # =================================================================
    def collect_params(self) -> Optional[dict]:
        """
        Recolecta los parametros de la GUI. Devuelve ``None`` si la
        validacion falla. Las subclases lo extienden.
        """
        return {}

    def start(self) -> None:
        if self.service.is_running():
            messagebox.showinfo(self.routine_code,
                                "La rutina ya se esta ejecutando.")
            return

        params = self.collect_params()
        if params is None:
            return

        self.clear_log()
        self._enable_result_buttons(False)
        self.result_label.configure(text="")
        self._set_status(Status.EJECUTANDO)
        self._set_state_buttons(running=True)
        ui.set_progress(self.progress, 0)
        self.progress_label.configure(text="Iniciando...")
        self.app.set_status(f"{self.routine_code}: ejecutando...")

        if not self.service.start(**params):
            self._set_state_buttons(running=False)
            return

        self._start_polling()

    def cancel(self) -> None:
        if not self.service.is_running():
            return
        self.service.cancel()
        self.append_log("Cancelacion solicitada; finalizando paso actual...")
        self.app.set_status(f"{self.routine_code}: cancelando...")

    # =================================================================
    # Lectura de la cola (hilo principal)
    # =================================================================
    def _start_polling(self) -> None:
        if self._polling:
            return
        self._polling = True
        self.app.root.after(GUI_POLL_MS, self._poll_queue)

    def _poll_queue(self) -> None:
        if not self._alive():
            self._polling = False
            return

        finished = False
        for event in self.service.poll():
            kind = event[0]
            if kind == EVT_PROGRESS:
                self._on_progress(event[1], event[2])
            elif kind == EVT_LOG:
                self.append_log(event[1])
            elif kind == EVT_INPUT:
                self._on_input_request(event[1])
            elif kind == EVT_DONE:
                self._on_done(event[1])
                finished = True
            elif kind == EVT_ERROR:
                self._on_error(event[1], event[2] if len(event) > 2 else "")
                finished = True

        if finished:
            self._polling = False
            return

        if self.service.is_running():
            self._idle_polls = 0
            self.app.root.after(GUI_POLL_MS, self._poll_queue)
            return

        # El hilo ya termino: se conceden unas pocas lecturas adicionales
        # para vaciar la cola y luego se detiene el sondeo.
        self._idle_polls = getattr(self, "_idle_polls", 0) + 1
        if self._idle_polls > 10:
            self._polling = False
            self._set_state_buttons(running=False)
            return
        self.app.root.after(GUI_POLL_MS, self._poll_queue)

    def _alive(self) -> bool:
        try:
            return bool(self.frame.winfo_exists())
        except Exception:  # noqa: BLE001
            return False

    # =================================================================
    # Manejadores de eventos
    # =================================================================
    def _on_progress(self, percent: int, message: str) -> None:
        ui.set_progress(self.progress, percent / 100.0)
        self.progress_label.configure(text=f"{percent}%  {message}")

    def _on_input_request(self, prompt: str) -> None:
        """
        Atiende una peticion de dato de la rutina en ejecucion.

        Se usa para el segundo factor de autenticacion: la rutina queda
        detenida en su propio hilo mientras el operador ingresa el
        codigo; la interfaz permanece activa.
        """
        from tkinter import simpledialog

        self.append_log(f">>> {prompt}")
        self.progress_label.configure(text="Esperando codigo del operador")
        try:
            valor = simpledialog.askstring(
                f"{self.routine_code} - autenticacion",
                f"{prompt}\n\n(Deje vacio y acepte para omitir este "
                f"portal)",
                parent=self.frame)
        except Exception:  # noqa: BLE001
            valor = None

        if valor:
            self.append_log("Codigo recibido; continuando...")
        else:
            self.append_log("No se ingreso codigo; la rutina continuara "
                            "sin este portal.")
        self.service.provide_input(valor)

    def _on_done(self, result: RoutineResult) -> None:
        self._set_state_buttons(running=False)
        self._set_status(result.status)
        ui.set_progress(self.progress, 1.0)
        self.progress_label.configure(text=f"100%  {result.status.value}")

        self._result_paths = dict(result.archivos)
        self._result_paths["dir"] = result.directorio_salida
        self._enable_result_buttons(True)

        resumen = self.build_summary(result)
        self.result_label.configure(text=resumen)
        self.append_log("")
        self.append_log(resumen)
        self.app.set_status(f"{self.routine_code}: {result.status.value} - "
                            f"{result.mensaje}")

        if result.status == Status.ERROR:
            messagebox.showerror(
                self.routine_code,
                f"La rutina finalizo con error:\n\n{result.mensaje}\n\n"
                f"El detalle esta registrado en logs/"
                f"{self.routine_code.lower()}.log")

    def _on_error(self, message: str, trace: str) -> None:
        self._set_state_buttons(running=False)
        self._set_status(Status.ERROR)
        self.progress_label.configure(text="ERROR")
        self.append_log(f"ERROR: {message}")
        if trace:
            self.log.error("Traza:\n%s", trace)
        self.app.set_status(f"{self.routine_code}: ERROR")
        messagebox.showerror(
            self.routine_code,
            f"Ocurrio un error no controlado:\n\n{message}\n\n"
            f"Revise logs/{self.routine_code.lower()}.log")

    def build_summary(self, result: RoutineResult) -> str:
        """Resumen textual del resultado. Las subclases pueden ajustarlo."""
        lineas = [
            f"Estado: {result.status.value}",
            f"Elementos correctos: {len(result.items_ok)}",
            f"Elementos con error: {len(result.items_error)}",
            f"Tiempo de ejecucion: {human_duration(result.duracion_seg)}",
            f"Directorio de salida: {result.directorio_salida}",
        ]
        if result.items_error:
            lineas.append("Con error: " + ", ".join(result.items_error))
        if result.errores:
            lineas.append("Errores: " + "; ".join(result.errores))
        return "\n".join(lineas)

    # =================================================================
    # Utilidades de interfaz
    # =================================================================
    def append_log(self, text: str) -> None:
        if not self._alive():
            return
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"{text}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def clear_log(self) -> None:
        if not self._alive():
            return
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    def _set_status(self, status: Status | str) -> None:
        text = status.value if isinstance(status, Status) else str(status)
        self.status_badge.configure(text=text, bg=ui.status_color(text))

    def _set_state_buttons(self, running: bool) -> None:
        try:
            self.run_btn.configure(state="disabled" if running else "normal")
            self.cancel_btn.configure(
                state="normal" if running else "disabled")
        except Exception:  # noqa: BLE001
            pass

    def _enable_result_buttons(self, enabled: bool) -> None:
        for key, btn in self.result_widgets.items():
            available = enabled and bool(self._result_paths.get(key))
            try:
                btn.configure(state="normal" if available else "disabled")
            except Exception:  # noqa: BLE001
                pass

    def _open_result(self, key: str) -> None:
        path = self._result_paths.get(key)
        if not path or not Path(path).exists():
            messagebox.showwarning(self.routine_code,
                                   "El archivo solicitado no esta disponible.")
            return
        if not open_path(path):
            messagebox.showinfo(self.routine_code,
                                f"No se pudo abrir automaticamente.\n\n{path}")

    # =================================================================
    # Restauracion al volver a la vista
    # =================================================================
    def _restore_state(self) -> None:
        """
        Si la rutina quedo ejecutandose mientras el usuario navegaba por
        otras pantallas, se reanuda la lectura de la cola. Si ya termino,
        se muestra el ultimo resultado disponible.
        """
        if self.service.is_running():
            self._set_status(Status.EJECUTANDO)
            self._set_state_buttons(running=True)
            self.append_log("Reanudando seguimiento de la ejecucion en "
                            "curso...")
            self._start_polling()
        elif self.service.last_result is not None:
            result = self.service.last_result
            self._result_paths = dict(result.archivos)
            self._result_paths["dir"] = result.directorio_salida
            self._set_status(result.status)
            ui.set_progress(self.progress, 1.0)
            self.progress_label.configure(
                text=f"Ultima ejecucion: {result.status.value}")
            self.result_label.configure(text=self.build_summary(result))
            self._enable_result_buttons(True)
