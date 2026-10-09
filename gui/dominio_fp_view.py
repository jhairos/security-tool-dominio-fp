"""
gui/dominio_fp_view.py
======================
Pantalla del analisis de dominio bloqueado.

Recibe el dominio (obligatorio), el resolver donde se observo el bloqueo
(opcional, pero necesario para atribuirlo) y una referencia de ticket.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from gui import ui
from gui.base_routine_view import BaseRoutineView
from routines.common import RoutineResult
from routines.dominio_fp import dominio_fp_config as cfg
from utils.file_utils import human_duration


class DominioFPView(BaseRoutineView):
    """Vista de ejecucion del analisis de falso positivo."""

    routine_code = cfg.ROUTINE_CODE
    routine_title = "DOMINIO BLOQUEADO FP — INVESTIGACIÓN OSINT"
    routine_desc = (f"Consulta {len(cfg.FUENTES)} fuentes publicas de "
                    f"reputacion (VirusTotal, MXToolbox, Whois y Google "
                    f"Safe Browsing) y compara la resolucion DNS del "
                    f"resolver bajo analisis con los resolvers publicos "
                    f"{' y '.join(cfg.DNS_REFERENCIA)}. No requiere "
                    f"credenciales.")

    # -----------------------------------------------------------------
    def build_extra_controls(self, parent: tk.Widget) -> None:
        # --- Parametro de entrada -------------------------------------
        caja = ttk.Frame(parent)
        caja.pack(fill="x", pady=(4, 6))

        ui.label(caja, "Dominio a analizar:",
                 font=("Segoe UI", 11, "bold")).pack(side="left")

        self.dominio_var = tk.StringVar()
        self.dominio_entry = ui.entry(
            caja, placeholder=cfg.DOMINIO_EJEMPLO,
            textvariable=self.dominio_var, width=360, width_chars=42)
        self.dominio_entry.pack(side="left", padx=8)

        ui.button(caja, "Limpiar",
                  lambda: self.dominio_var.set("")).pack(side="left")

        # Ejecutar tambien con la tecla Enter
        try:
            self.dominio_entry.bind("<Return>", lambda _e: self.start())
        except Exception:  # noqa: BLE001
            pass

        # --- Resolver bajo analisis -----------------------------------
        caja_dns = ttk.Frame(parent)
        caja_dns.pack(fill="x", pady=(0, 6))
        ui.label(caja_dns, "Resolver bajo análisis:").pack(side="left")
        self.resolver_var = tk.StringVar()
        ui.entry(caja_dns, placeholder="IP del DNS donde se observó el bloqueo",
                 textvariable=self.resolver_var, width=300,
                 width_chars=36).pack(side="left", padx=8)
        ui.button(caja_dns, "Limpiar",
                  lambda: self.resolver_var.set("")).pack(side="left")

        # --- Ticket opcional -----------------------------------------
        caja_ticket = ttk.Frame(parent)
        caja_ticket.pack(fill="x", pady=(0, 6))
        ui.label(caja_ticket, "Ticket (opcional):").pack(side="left")
        self.ticket_var = tk.StringVar(value=cfg.TICKET_EJEMPLO)
        ui.entry(caja_ticket, placeholder="Número o referencia del ticket (opcional)",
                 textvariable=self.ticket_var, width=520,
                 width_chars=62).pack(side="left", padx=8)
        ui.button(caja_ticket, "Limpiar",
                  lambda: self.ticket_var.set("")).pack(side="left")

        # --- Opciones -------------------------------------------------
        opciones = ttk.Frame(parent)
        opciones.pack(fill="x", pady=(0, 4))
        self.headless_var = tk.IntVar(value=1 if cfg.HEADLESS else 0)
        ui.checkbox(opciones,
                    "Ejecutar Chromium en segundo plano (headless)",
                    self.headless_var).pack(side="left")

        disponible, motivo = self.service.estado_cli()
        estado_cli = ("resolucion por consola disponible" if disponible
                      else f"consola no disponible: {motivo}")
        ui.label(opciones, f"   Referencia {' y '.join(cfg.DNS_REFERENCIA)} — {estado_cli}").pack(
            side="left", padx=10)

        # --- Fuentes --------------------------------------------------
        ui.label(parent,
                 "El reporte incluye la validación OSINT, la comparación DNS y su interpretación.\n"
                 "Fuentes consultadas: " + ", ".join(cfg.fuente_titulos()),
                 wraplength=980, justify="left").pack(anchor="w",
                                                      pady=(2, 0))

    # -----------------------------------------------------------------
    def collect_params(self) -> dict | None:
        params = super().collect_params()
        if params is None:
            return None

        dominio = self.service.normalizar(self.dominio_var.get())
        if not dominio:
            messagebox.showwarning(
                self.routine_code,
                "Ingrese el dominio a analizar antes de ejecutar.")
            return None
        if not self.service.dominio_valido(dominio):
            messagebox.showwarning(
                self.routine_code,
                f"El dominio indicado no parece valido:\n\n{dominio}\n\n"
                f"Ejemplo: {cfg.DOMINIO_EJEMPLO}")
            return None

        resolver = self.resolver_var.get().strip()
        if resolver and not self.service.resolver_valido(resolver):
            messagebox.showwarning(
                self.routine_code,
                f"El resolver debe ser una dirección IP:\n\n{resolver}")
            return None
        if not resolver and not messagebox.askyesno(
                self.routine_code,
                "No se indicó el resolver donde se observó el bloqueo.\n\n"
                "Solo se consultarán los resolvers de referencia y el "
                "bloqueo no se podrá atribuir. ¿Continuar?"):
            return None

        self.dominio_var.set(dominio)
        params["dominio"] = dominio
        params["resolver"] = resolver
        params["ticket"] = self.ticket_var.get().strip()
        params["headless"] = bool(self.headless_var.get())
        return params

    # -----------------------------------------------------------------
    def build_summary(self, result: RoutineResult) -> str:
        total = len(result.items_ok) + len(result.items_error)
        omitidos = result.extra.get("omitidos", [])
        dominio = result.extra.get("dominio", "")
        cabecera = ("Analisis completado"
                    if not result.items_error and not result.errores
                    else "Analisis finalizado con observaciones")

        lineas = [
            f"{cabecera}  [{result.status.value}]",
            f"Dominio analizado:    {dominio}",
            f"Atribucion DNS:       {result.extra.get('atribucion', '-')}",
            f"Evidencias obtenidas: {len(result.items_ok)} de {total}",
            f"Sin evidencia:        {len(result.items_error)}",
            f"Tiempo de ejecucion:  {human_duration(result.duracion_seg)}",
            f"Directorio de salida: {result.directorio_salida}",
        ]
        if omitidos:
            lineas.append("Omitidas: " + ", ".join(omitidos))
        if result.items_error:
            lineas.append("Con error: " + ", ".join(result.items_error))
        return "\n".join(lineas)
