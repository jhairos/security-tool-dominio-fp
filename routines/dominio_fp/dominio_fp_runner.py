"""
routines/dominio_fp/dominio_fp_runner.py
========================================
ORQUESTADOR de la rutina DOMINIO_FP.

Flujo:

    run_dominio_fp(dominio)
        -> validar el dominio recibido
        -> consultar las fuentes publicas de reputacion y capturarlas
        -> resolver con dig (resolver analizado y referencias) e interpretar
        -> generar ZIP, index.html, gmail.html y DOCX
        -> devolver RoutineResult

Recibe el dominio a analizar (obligatorio) y, opcionalmente, el resolver
DNS donde se observo el bloqueo.

Ejecutable sin interfaz grafica:

    python -m routines.dominio_fp.dominio_fp_runner --dominio ejemplo.com
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from routines.common import (
    CancelCallback,
    InputCallback,
    LogCallback,
    ProgressCallback,
    Reporter,
    RoutineCancelled,
    RoutineResult,
    Status,
)
from routines.dominio_fp import (
    dominio_fp_capture,
    dominio_fp_cli,
    dominio_fp_dns,
    dominio_fp_reports,
)
from routines.dominio_fp import dominio_fp_config as cfg
from utils.file_utils import RUN_STAMP_FMT, new_run_dir
from utils.logger import get_logger

log = get_logger("dominio_fp.runner", routine=cfg.ROUTINE_CODE)


def run_dominio_fp(dominio: str = "",
                   ticket: str = "",
                   resolver: str = "",
                   progress_callback: Optional[ProgressCallback] = None,
                   log_callback: Optional[LogCallback] = None,
                   cancel_callback: Optional[CancelCallback] = None,
                   input_callback: Optional[InputCallback] = None,
                   headless: bool = cfg.HEADLESS,
                   output_dir: Optional[Path] = None,
                   echo: bool = False) -> RoutineResult:
    """
    Ejecuta el analisis de posible falso positivo para un dominio.

    Parameters
    ----------
    dominio:
        Dominio a analizar. Es obligatorio. Si no se indica y hay un
        canal de entrada disponible, se solicita al operador.
    ticket:
        Referencia de ticket o caso. Si se indica, se incorpora al
        encabezado del reporte.
    resolver:
        IP del resolver DNS donde se observo el bloqueo. Si se omite, solo
        se consultan los resolvers de referencia y el bloqueo no se puede
        atribuir.

    Returns
    -------
    RoutineResult
    """
    reporter = Reporter(progress_callback, log_callback, cancel_callback,
                        input_callback, echo=echo)

    inicio = datetime.now()
    stamp = inicio.strftime(RUN_STAMP_FMT)
    result = RoutineResult(routine=cfg.ROUTINE_CODE,
                           status=Status.EJECUTANDO,
                           fecha_inicio=inicio)

    # -- Parametro obligatorio -----------------------------------------
    if not dominio and reporter.can_ask_input:
        dominio = reporter.ask_input(
            "Ingrese el dominio a analizar:") or ""

    dominio = cfg.normalizar_dominio(dominio)
    if not dominio:
        return _fail(result, "No se indico el dominio a analizar.")
    if not cfg.dominio_valido(dominio):
        return _fail(result, f"El dominio indicado no es valido: {dominio}")

    result.extra["dominio"] = dominio
    result.extra["ticket"] = (ticket or "").strip()
    resolver = (resolver or "").strip()
    if resolver and not cfg.resolver_valido(resolver):
        return _fail(result, f"El resolver indicado no es una IP valida: {resolver}")
    result.extra["resolver"] = resolver

    # -- Carpeta de salida ---------------------------------------------
    try:
        out_dir = Path(output_dir) if output_dir else new_run_dir(
            cfg.ROUTINE_CODE, stamp)
        assets_dir = out_dir / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        result.directorio_salida = out_dir
    except Exception as exc:  # noqa: BLE001
        log.exception("No se pudo crear la carpeta de salida")
        return _fail(result, f"No se pudo crear la carpeta de salida: {exc}")

    log.info("=== Inicio rutina DOMINIO_FP === dominio=%s salida: %s",
             dominio, out_dir)
    reporter.progress(5, f"Analizando el dominio {dominio}")
    reporter.log(f"Dominio a analizar: {dominio}")

    fecha_text = inicio.strftime("%d-%b-%Y").upper()
    items = []

    # -- Fuentes publicas ----------------------------------------------
    try:
        reporter.check_cancel()
        reporter.progress(10, "Abriendo navegador Chromium")
        sync_playwright = dominio_fp_capture.import_playwright()

        with sync_playwright() as p:
            reporter.progress(15, f"{len(cfg.FUENTES)} fuentes de "
                                  f"reputacion por consultar")
            items = dominio_fp_capture.capture_sources(
                p, dominio, assets_dir=assets_dir, stamp=stamp,
                headless=headless, reporter=reporter,
                progress_from=20, progress_to=70)

    except RoutineCancelled as exc:
        log.warning("Rutina DOMINIO_FP cancelada por el usuario.")
        result.status = Status.ADVERTENCIA
        result.mensaje = str(exc)
        result.fecha_fin = datetime.now()
        reporter.log("Ejecucion cancelada.")
        return result
    except dominio_fp_capture.CaptureError as exc:
        log.error("Error controlado en DOMINIO_FP: %s", exc)
        return _fail(result, str(exc))
    except Exception as exc:  # noqa: BLE001
        log.exception("Error inesperado consultando las fuentes")
        return _fail(result, f"Error inesperado: {exc}")

    # -- Resolucion por linea de comandos -------------------------------
    respuestas: list = []
    try:
        reporter.check_cancel()
        reporter.progress(75, "Resolviendo con dig y comparando resolvers")
        items.extend(dominio_fp_cli.capturar_comandos(
            dominio, assets_dir=assets_dir, stamp=stamp,
            reporter=reporter, resolver=resolver, respuestas=respuestas))
    except RoutineCancelled:
        raise
    except Exception as exc:  # noqa: BLE001
        log.exception("Error en la evidencia de linea de comandos")
        items.append(("CLI dig", None, f"ERROR: {exc}"))

    # -- Interpretacion DNS ----------------------------------------------
    analisis_dns = dominio_fp_dns.texto_para_reporte(respuestas)
    if respuestas:
        estado_dns, conclusion = dominio_fp_dns.atribuir(respuestas)
        result.extra["atribucion"] = estado_dns
        reporter.log(f"Atribución del bloqueo: {estado_dns}")
        reporter.log(f"   {conclusion}")

    # -- Clasificacion --------------------------------------------------
    from utils.report_builder import desglosar
    desglosados = [desglosar(i) for i in items]
    result.items_ok = [t for t, png, st, _r in desglosados
                       if png and st.startswith("OK")]
    result.items_error = [f"{t} ({st})" for t, png, st, _r in desglosados
                          if not png or not st.startswith("OK")]
    omitidos = [t for t, _png, st, _r in desglosados
                if st.startswith("OMITIDO")]
    result.extra["omitidos"] = omitidos

    reporter.log(f"Evidencias obtenidas: {len(result.items_ok)} de "
                 f"{len(items)}")

    # -- Reportes -------------------------------------------------------
    try:
        archivos = dominio_fp_reports.build_all_reports(
            items, out_dir=out_dir, stamp=stamp, dominio=dominio,
            ticket=ticket, fecha_str=fecha_text, reporter=reporter,
            analisis_dns=analisis_dns)
    except Exception as exc:  # noqa: BLE001
        log.exception("Error generando reportes DOMINIO_FP")
        return _fail(result, f"Error generando reportes: {exc}")

    for err in archivos.pop("errores", []):
        result.add_error(err)
    result.archivos = archivos

    # -- Estado final ---------------------------------------------------
    result.fecha_fin = datetime.now()
    if result.errores or result.items_error:
        result.status = Status.ADVERTENCIA
        result.mensaje = (
            f"Analisis de {dominio} finalizado con observaciones. "
            f"Evidencias: {len(result.items_ok)} de {len(items)}.")
    else:
        result.status = Status.OK
        result.mensaje = (f"Analisis de {dominio} completado. "
                          f"Evidencias: {len(result.items_ok)}.")

    reporter.progress(100, "Finalizado")
    reporter.log(result.mensaje)
    reporter.log(f"Salida: {out_dir}")
    log.info("=== Fin rutina DOMINIO_FP === estado=%s duracion=%.1fs",
             result.status.value, result.duracion_seg)
    return result


def _fail(result: RoutineResult, message: str) -> RoutineResult:
    """Marca el resultado como ERROR conservando la informacion parcial."""
    result.status = Status.ERROR
    result.mensaje = message
    result.add_error(message)
    result.fecha_fin = datetime.now()
    return result


# ---------------------------------------------------------------------
# Ejecucion sin GUI
# ---------------------------------------------------------------------
def main() -> int:  # pragma: no cover
    """Ejecuta la rutina desde la linea de comandos."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Analiza un posible falso positivo de dominio "
                    "bloqueado.")
    parser.add_argument("--dominio", required=True,
                        help="Dominio a analizar")
    parser.add_argument("--ticket", default="",
                        help="Referencia del ticket (opcional)")
    parser.add_argument("--resolver", default="",
                        help="IP del resolver donde se observo el bloqueo")
    parser.add_argument("--no-headless", action="store_true",
                        help="Mostrar la ventana de Chromium")
    args = parser.parse_args()

    resultado = run_dominio_fp(dominio=args.dominio, ticket=args.ticket,
                               resolver=args.resolver,
                               headless=not args.no_headless, echo=True)

    print("\n===== RESULTADO =====")
    for key, value in resultado.to_dict().items():
        print(f"{key:22}: {value}")
    return 0 if resultado.status in (Status.OK, Status.ADVERTENCIA) else 1


if __name__ == "__main__":  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    raise SystemExit(main())
