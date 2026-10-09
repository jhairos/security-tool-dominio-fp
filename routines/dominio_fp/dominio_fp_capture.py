"""
routines/dominio_fp/dominio_fp_capture.py
=========================================
Consulta de las fuentes publicas de reputacion y captura de cada una.

No hay autenticacion: todas las fuentes son de acceso libre. Se abren con
el Chromium de Playwright en su configuracion normal. El unico
tratamiento especial son los avisos de cookies, que tapan el informe. Si
una fuente muestra una verificacion antimaquina, la evidencia se marca
como no obtenida: la herramienta no intenta superarla.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import List, Optional

from routines.common import Reporter
from routines.dominio_fp import dominio_fp_config as cfg
from utils.logger import get_logger
from utils.report_builder import EvidenceItem

log = get_logger("dominio_fp.capture", routine=cfg.ROUTINE_CODE)

STATUS_OK = "OK"
STATUS_ERROR = "ERROR"
STATUS_VERIFICACION = "ERROR: verificacion de seguridad pendiente"


class CaptureError(RuntimeError):
    """Error controlado durante la consulta."""


# ---------------------------------------------------------------------
def import_playwright():
    try:
        from playwright.sync_api import sync_playwright  # noqa: PLC0415
        return sync_playwright
    except ImportError as exc:  # noqa: BLE001
        raise CaptureError(
            "Playwright no esta instalado. Ejecute:\n"
            "    pip install playwright\n"
            "    python -m playwright install chromium") from exc


def open_context(playwright, headless: bool = cfg.HEADLESS):
    """Abre Chromium y devuelve ``(contexto, pagina)``."""
    try:
        browser = playwright.chromium.launch(headless=headless)
    except Exception as exc:  # noqa: BLE001
        raise CaptureError(
            "No se pudo iniciar Chromium. Verifique la instalacion:\n"
            "    python -m playwright install chromium\n"
            f"Detalle: {exc}") from exc
    contexto = browser.new_context(
        viewport=cfg.VIEWPORT,
        ignore_https_errors=cfg.IGNORE_HTTPS_ERRORS)
    contexto._browser_efimero = browser
    return contexto, contexto.new_page()


def close_context(contexto) -> None:
    """Cierra el contexto y, si lo hubiera, su navegador efimero."""
    browser = getattr(contexto, "_browser_efimero", None)
    for closable in (contexto, browser):
        try:
            if closable:
                closable.close()
        except Exception:  # noqa: BLE001
            pass


# ---------------------------------------------------------------------
def hay_modal(page) -> bool:
    for sel in cfg.MODAL_PRESENT_SELECTORS:
        try:
            for el in page.query_selector_all(sel):
                if el.is_visible():
                    caja = el.bounding_box()
                    if caja and caja["width"] > 200 and caja["height"] > 60:
                        return True
        except Exception:  # noqa: BLE001
            continue
    return False


def cerrar_modales(page, intentos: int = cfg.MODAL_ATTEMPTS) -> int:
    """Cierra los avisos de cookies que tapan el informe."""
    cerrados = 0
    for intento in range(1, max(1, intentos) + 1):
        en_pasada = 0
        if cfg.MODAL_TRY_ESCAPE:
            try:
                page.keyboard.press("Escape")
                time.sleep(cfg.MODAL_WAIT_S)
            except Exception:  # noqa: BLE001
                pass
        for sel in cfg.MODAL_SELECTORS:
            try:
                elementos = page.query_selector_all(sel)
            except Exception:  # noqa: BLE001
                continue
            for el in elementos:
                try:
                    if not el.is_visible():
                        continue
                    el.click(timeout=3000)
                    en_pasada += 1
                    log.info("Aviso cerrado con: %s", sel)
                    time.sleep(cfg.MODAL_WAIT_S)
                except Exception:  # noqa: BLE001
                    continue
        cerrados += en_pasada
        if en_pasada and not hay_modal(page):
            break
        if intento < intentos:
            time.sleep(cfg.MODAL_RETRY_WAIT_S)
    return cerrados


def hay_indicador_de_carga(page) -> bool:
    for sel in cfg.LOADING_SELECTORS:
        try:
            for el in page.query_selector_all(sel):
                if el.is_visible():
                    return True
        except Exception:  # noqa: BLE001
            continue
    return False


def hay_verificacion(page) -> bool:
    """
    Indica si la pagina muestra una verificacion antimaquina.

    En ese caso la captura no es evidencia valida y se marca como no
    obtenida; no se intenta superar la verificacion.
    """
    try:
        texto = (page.inner_text("body") or "").lower()
    except Exception:  # noqa: BLE001
        return False
    return any(t in texto for t in cfg.CHALLENGE_TEXTS)


def contenido_listo(page) -> bool:
    if not cfg.WAIT_FOR_CONTENT:
        return True
    if hay_indicador_de_carga(page) or hay_verificacion(page):
        return False
    try:
        texto = (page.inner_text("body") or "").strip()
    except Exception:  # noqa: BLE001
        return True
    if len(texto) < cfg.MIN_CONTENT_CHARS:
        bajo = texto.lower()
        if any(t in bajo for t in cfg.LOADING_TEXTS) or not texto:
            return False
    return True


def esperar_contenido(page, reporter=None, reintentos: int = None) -> bool:
    total = int(reintentos or cfg.CONTENT_RETRIES)
    for intento in range(1, total + 1):
        cerrar_modales(page, intentos=1)
        if contenido_listo(page):
            time.sleep(cfg.SETTLE_AFTER_CONTENT_S)
            if contenido_listo(page):
                return True
        log.info("Contenido aun cargando (%s de %s).", intento, total)
        if reporter:
            reporter.log(f"   ... esperando a que cargue "
                         f"({intento}/{total})")
        time.sleep(cfg.CONTENT_RETRY_WAIT_S)
    return False


def _captura_directa(page, out_png: Path, completa: bool) -> None:
    """
    Captura mediante el protocolo del navegador, sin esperar a las
    tipografias.

    Es el ultimo recurso: la captura normal aguarda a que carguen las
    fuentes remotas y, cuando el proveedor no las entrega, esa espera
    agota el tiempo y no se obtiene evidencia alguna. Esta via toma la
    imagen tal como se ve en ese momento.
    """
    import base64  # noqa: PLC0415

    sesion = page.context.new_cdp_session(page)
    try:
        datos = sesion.send("Page.captureScreenshot", {
            "format": "png",
            "captureBeyondViewport": bool(completa),
        })
        Path(out_png).write_bytes(base64.b64decode(datos["data"]))
    finally:
        try:
            sesion.detach()
        except Exception:  # noqa: BLE001
            pass


def _primer_elemento(page, selectores):
    """Devuelve el primer selector presente y visible."""
    for sel in (selectores or []):
        try:
            el = page.query_selector(sel)
        except Exception:  # noqa: BLE001
            continue
        if not el:
            continue
        try:
            if el.is_visible():
                return el, sel
        except Exception:  # noqa: BLE001
            return el, sel
    return None, ""


def _escribir_consulta(campo, valor: str) -> str:
    """
    Deja en el campo EXACTAMENTE el valor indicado.

    El buscador de MXToolbox conserva la consulta anterior y propone
    sugerencias mientras se escribe: tecleando caracter a caracter el
    texto se mezclaba y quedaba algo como "mx:bcklist:dominio", que la
    herramienta rechazaba. Se limpia el campo por teclado y se asigna el
    valor de una vez, comprobando despues que coincide.
    """
    try:
        campo.click()
        campo.press("Control+a")
        campo.press("Delete")
    except Exception:  # noqa: BLE001
        pass

    try:
        campo.fill(valor)
    except Exception:  # noqa: BLE001
        pass

    try:
        actual = (campo.input_value() or "").strip()
    except Exception:  # noqa: BLE001
        return valor

    if actual == valor:
        return actual

    # Segundo intento: vaciar y teclear sin sugerencias de por medio.
    log.warning("El campo quedo con '%s'; se vuelve a escribir.", actual)
    try:
        campo.fill("")
        campo.type(valor, delay=25)
        actual = (campo.input_value() or "").strip()
    except Exception:  # noqa: BLE001
        pass
    return actual


def _consulta_rechazada(page) -> bool:
    """Indica si la herramienta rechazo la consulta escrita."""
    try:
        texto = (page.inner_text("body") or "").lower()
    except Exception:  # noqa: BLE001
        return False
    return any(t.lower() in texto for t in cfg.CONSULTA_RECHAZADA)


def lanzar_consulta(page, formulario: dict, reporter=None) -> bool:
    """
    Escribe el dominio en el buscador de la fuente y lanza la consulta.

    Hay fuentes que no ejecutan la busqueda al cambiar el fragmento de
    la direccion: hay que rellenar su formulario. Es el caso de
    MXToolbox, cuya evidencia salia con la pagina de bienvenida.
    """
    campo, sel = _primer_elemento(page, formulario.get("campo"))
    if campo is None:
        log.warning("No se localizo el buscador de la fuente.")
        return False

    valor = formulario.get("valor", "")
    resultados = formulario.get("resultado") or []

    for intento in (1, 2):
        escrito = _escribir_consulta(campo, valor)
        if escrito != valor:
            log.warning("No se pudo dejar la consulta exacta: '%s'", escrito)
        else:
            log.info("Consulta '%s' escrita en: %s", valor, sel)

        # Enter es lo mas fiable: el prefijo ya determina la
        # comprobacion que se ejecuta.
        lanzada = False
        try:
            campo.press("Enter")
            lanzada = True
        except Exception:  # noqa: BLE001
            pass

        if not lanzada:
            boton, sel_boton = _primer_elemento(page,
                                                formulario.get("boton"))
            if boton is not None:
                try:
                    boton.click(timeout=cfg.CLICK_TIMEOUT_MS)
                    log.info("Consulta lanzada con: %s", sel_boton)
                    lanzada = True
                except Exception:  # noqa: BLE001
                    pass

        if not lanzada:
            return False

        if resultados:
            try:
                page.wait_for_selector(", ".join(resultados),
                                       timeout=cfg.FORMULARIO_TIMEOUT_MS)
            except Exception:  # noqa: BLE001
                log.warning("No aparecio el resultado esperado.")
        time.sleep(cfg.FORMULARIO_ESPERA_S)

        # La herramienta avisa cuando la consulta llega mal escrita.
        if not _consulta_rechazada(page):
            if reporter:
                reporter.log(f"   ... consulta '{valor}' ejecutada")
            return True

        log.warning("La herramienta rechazo la consulta (intento %s).",
                    intento)
        if reporter and intento == 1:
            reporter.log("   ... la consulta llego mal escrita; "
                         "se repite")
        campo, sel = _primer_elemento(page, formulario.get("campo"))
        if campo is None:
            return False

    return False


def capturar(page, out_png: Path) -> str:
    """
    Captura la pagina y devuelve el alcance de la evidencia.

    Se intentan tres vias, de mayor a menor fidelidad:

    1. Pagina completa por la via normal.
    2. Pagina completa por el protocolo del navegador, que NO espera a
       las tipografias remotas.
    3. Parte visible por esa misma via.

    Una evidencia parcial siempre es preferible a ninguna.
    """
    out_png = Path(out_png)

    try:
        page.screenshot(path=str(out_png), full_page=cfg.FULL_PAGE,
                        timeout=cfg.SCREENSHOT_TIMEOUT_MS,
                        animations="disabled")
        return "pagina completa"
    except Exception as exc:  # noqa: BLE001
        if not cfg.SCREENSHOT_REINTENTO_VIEWPORT:
            raise
        log.warning("La captura normal fallo (%s); se toma la imagen sin "
                    "esperar a las tipografias.",
                    str(exc).splitlines()[0][:70])

    try:
        _captura_directa(page, out_png, completa=True)
        return "pagina completa (sin esperar tipografias)"
    except Exception as exc:  # noqa: BLE001
        log.warning("La captura completa directa fallo (%s); se captura "
                    "la parte visible.", str(exc).splitlines()[0][:60])

    _captura_directa(page, out_png, completa=False)
    return "parte visible"


def goto_page(page, url: str, wait_s: float = None,
              consulta_hash: str = "", formulario: dict = None,
              reporter=None) -> None:
    """
    Navega a la fuente, tolerando redirecciones canceladas.

    MXToolbox responde con una redireccion que el navegador cancela
    (``ERR_ABORTED``) cuando se espera a "domcontentloaded". Se reintenta
    con "commit", que acepta la navegacion en cuanto comienza.
    """
    try:
        page.goto(url, wait_until="domcontentloaded",
                  timeout=cfg.GOTO_TIMEOUT_MS)
    except Exception as exc:  # noqa: BLE001
        motivo = str(exc)
        cancelada = any(p in motivo for p in cfg.NAVEGACION_CANCELADA)
        if not cancelada:
            raise
        log.warning("El servidor no devolvio una pagina navegable (%s); "
                    "se reintenta con 'commit'.",
                    motivo.splitlines()[0][:60])
        try:
            page.goto(url, wait_until="commit",
                      timeout=cfg.GOTO_TIMEOUT_MS)
        except Exception as exc2:  # noqa: BLE001
            if not any(p in str(exc2) for p in cfg.NAVEGACION_CANCELADA):
                raise
            raise CaptureError(
                "El servidor respondio con una descarga o cancelo la "
                "navegacion, de modo que no hay pagina que capturar. "
                "Use la direccion base de la herramienta y la consulta "
                "por fragmento (clave 'consulta_hash')."
            ) from exc2

    # Consulta por fragmento: la pagina base ya esta cargada.
    if consulta_hash:
        try:
            page.evaluate("h => { window.location.hash = h; }",
                          consulta_hash)
            time.sleep(2.0)
        except Exception:  # noqa: BLE001
            pass

    # Consulta por formulario: se escribe el dominio y se ejecuta.
    if formulario:
        lanzar_consulta(page, formulario, reporter)
    try:
        page.wait_for_selector(", ".join(cfg.LOADING_SELECTORS),
                               state="detached",
                               timeout=cfg.LOADING_WAIT_TIMEOUT_MS)
    except Exception:  # noqa: BLE001
        pass
    try:
        page.wait_for_load_state("networkidle",
                                 timeout=cfg.NETWORK_IDLE_TIMEOUT_MS)
    except Exception:  # noqa: BLE001
        pass
    time.sleep(cfg.WAIT_AFTER_NAV_S if wait_s is None else float(wait_s))


# ---------------------------------------------------------------------
def capture_sources(playwright,
                    dominio: str,
                    assets_dir: Path,
                    stamp: str,
                    headless: bool = cfg.HEADLESS,
                    reporter: Optional[Reporter] = None,
                    progress_from: int = 20,
                    progress_to: int = 70) -> List[EvidenceItem]:
    """Consulta cada fuente publica y captura su informe."""
    reporter = reporter or Reporter()
    assets_dir = Path(assets_dir)
    assets_dir.mkdir(parents=True, exist_ok=True)

    paginas = cfg.build_pages(dominio)
    items: List[EvidenceItem] = []
    total = max(1, len(paginas))
    span = max(1, progress_to - progress_from)

    context = None
    try:
        context, page = open_context(playwright, headless=headless)
        for idx, spec in enumerate(paginas, start=1):
            reporter.check_cancel()
            titulo = spec["title"]
            reporter.progress(progress_from + int(span * idx / total),
                              f"Consultando {titulo}")

            out_png = assets_dir / f"FP_{spec['key']}_{stamp}.png"
            referencia = spec.get("referencia", spec["url"])
            try:
                goto_page(page, spec["url"], spec.get("wait_s"),
                          spec.get("consulta_hash", ""),
                          spec.get("formulario"), reporter)
                cerrar_modales(page)
                esperar_contenido(page, reporter,
                                  spec.get("content_retries"))
                alcance = capturar(page, out_png)
            except Exception as exc:  # noqa: BLE001
                log.exception("Error consultando '%s'", titulo)
                items.append((titulo, None, f"{STATUS_ERROR}: {exc}",
                              referencia))
                reporter.log(f"   [X] {titulo} - {type(exc).__name__}")
                continue

            if not out_png.exists() or out_png.stat().st_size == 0:
                items.append((titulo, None,
                              f"{STATUS_ERROR}: imagen vacia",
                              referencia))
                continue

            # Una verificacion antimaquina no es evidencia valida.
            if hay_verificacion(page):
                items.append((titulo, out_png, STATUS_VERIFICACION,
                              referencia))
                reporter.log(f"   [X] {titulo} - la fuente exige "
                             f"verificacion; consultela manualmente")
                continue

            items.append((titulo, out_png, STATUS_OK, referencia))
            reporter.log(f"   [OK] {titulo} ({alcance})")
            time.sleep(cfg.DELAY_BETWEEN_PAGES_S)
    finally:
        if context is not None:
            close_context(context)

    return items
