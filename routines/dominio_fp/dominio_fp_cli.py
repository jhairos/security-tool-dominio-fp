"""
routines/dominio_fp/dominio_fp_cli.py
=====================================
Evidencia de LINEA DE COMANDOS.

Ejecuta la resolucion ``dig`` contra el resolver bajo analisis (si se
indico) y contra los resolvers publicos de referencia, guarda la salida en
texto, la compone como imagen para el reporte y la interpreta con
``dominio_fp_dns``.

En Windows el comando se ejecuta dentro de **WSL 2** (``wsl.exe -- dig
...``), porque ``dig`` no forma parte de Windows. Si la rutina se
ejecuta sobre Linux, el comando corre directamente.

Se compone la salida como imagen en lugar de fotografiar una ventana de
consola: el resultado es legible, reproducible y no depende de que haya
una terminal abierta ni del tema del escritorio.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from routines.common import Reporter
from routines.dominio_fp import dominio_fp_config as cfg
from routines.dominio_fp import dominio_fp_dns
from utils.logger import get_logger

log = get_logger("dominio_fp.cli", routine=cfg.ROUTINE_CODE)


class CLIError(RuntimeError):
    """Error controlado al ejecutar el comando."""


# ---------------------------------------------------------------------
# Ejecucion
# ---------------------------------------------------------------------
def construir_comando(comando: str) -> Tuple[List[str], str]:
    """
    Devuelve ``(argumentos, descripcion)`` segun el sistema.

    En Windows se antepone ``wsl.exe --``; en Linux se ejecuta tal cual.
    """
    partes = comando.split()
    if sys.platform == "win32" and cfg.USAR_WSL:
        return list(cfg.WSL_COMANDO) + partes, f"wsl -- {comando}"
    return partes, comando


def wsl_disponible() -> Tuple[bool, str]:
    """Comprueba que se pueda ejecutar el comando en este equipo."""
    if sys.platform == "win32":
        if not cfg.USAR_WSL:
            return False, "La ejecucion por WSL esta desactivada."
        if shutil.which("wsl.exe") is None:
            return False, ("WSL no esta disponible en este equipo. "
                           "Instale WSL 2 y el paquete dnsutils "
                           "(sudo apt install dnsutils).")
        return True, ""
    if shutil.which("dig") is None:
        return False, ("El comando 'dig' no esta disponible. Instale "
                       "dnsutils / bind-utils.")
    return True, ""


def ejecutar(comando: str,
             timeout_s: int = cfg.DIG_TIMEOUT_S) -> Tuple[int, str]:
    """
    Ejecuta el comando y devuelve ``(codigo_de_salida, salida)``.

    La salida de error se incorpora al texto para que el reporte refleje
    tambien los fallos de resolucion, que son informacion util.
    """
    argumentos, descripcion = construir_comando(comando)
    log.info("Ejecutando: %s", descripcion)
    try:
        proceso = subprocess.run(
            argumentos, capture_output=True, text=True,
            timeout=timeout_s, check=False)
    except FileNotFoundError as exc:
        raise CLIError(f"No se encontro el ejecutable: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise CLIError(
            f"El comando supero {timeout_s} s sin responder.") from exc
    except Exception as exc:  # noqa: BLE001
        raise CLIError(f"No se pudo ejecutar el comando: {exc}") from exc

    salida = (proceso.stdout or "")
    if proceso.stderr:
        salida += ("\n" if salida else "") + proceso.stderr
    return proceso.returncode, salida.rstrip()


# ---------------------------------------------------------------------
# Composicion de la imagen
# ---------------------------------------------------------------------
def _fuente(tamano: int):
    """Carga una fuente monoespaciada; recurre a la de Pillow si falta."""
    from PIL import ImageFont  # noqa: PLC0415

    candidatas = [
        "consola.ttf", "cour.ttf",                       # Windows
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/Library/Fonts/Menlo.ttc",                      # macOS
    ]
    for ruta in candidatas:
        try:
            return ImageFont.truetype(ruta, tamano)
        except Exception:  # noqa: BLE001
            continue
    return ImageFont.load_default()


def componer_imagen(titulo: str, comando: str, salida: str,
                    out_png: Path) -> Path:
    """
    Compone la salida del comando como imagen con aspecto de terminal.
    """
    from PIL import Image, ImageDraw  # noqa: PLC0415

    out_png = Path(out_png)
    fuente = _fuente(cfg.CLI_IMG_FUENTE_PX)

    cabecera = [
        titulo,
        f"$ {comando}",
        f"Ejecutado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
    ]
    cuerpo = (salida or "(sin salida)").splitlines()
    if len(cuerpo) > cfg.CLI_MAX_LINEAS:
        recortadas = len(cuerpo) - cfg.CLI_MAX_LINEAS
        cuerpo = cuerpo[:cfg.CLI_MAX_LINEAS]
        cuerpo.append(f"... ({recortadas} lineas adicionales omitidas)")

    lineas = cabecera + cuerpo

    alto_linea = cfg.CLI_IMG_FUENTE_PX + cfg.CLI_IMG_INTERLINEA
    alto = cfg.CLI_IMG_MARGEN * 2 + alto_linea * max(1, len(lineas))
    imagen = Image.new("RGB", (cfg.CLI_IMG_ANCHO, alto), cfg.CLI_IMG_FONDO)
    lapiz = ImageDraw.Draw(imagen)

    y = cfg.CLI_IMG_MARGEN
    for indice, linea in enumerate(lineas):
        color = cfg.CLI_IMG_TITULO if indice < 3 else cfg.CLI_IMG_TEXTO
        lapiz.text((cfg.CLI_IMG_MARGEN, y), linea, font=fuente, fill=color)
        y += alto_linea

    imagen.save(str(out_png))
    log.info("Evidencia de consola compuesta: %s", out_png.name)
    return out_png


# ---------------------------------------------------------------------
# Recorrido de los comandos
# ---------------------------------------------------------------------
def capturar_comandos(dominio: str,
                      assets_dir: Path,
                      stamp: str,
                      reporter: Optional[Reporter] = None,
                      resolver: str = "",
                      respuestas: Optional[list] = None) -> list:
    """
    Ejecuta los comandos configurados y devuelve sus evidencias.

    Si se entrega ``respuestas``, se agrega la lectura de cada salida
    (``dominio_fp_dns.RespuestaDig``) para la comparacion.

    Returns
    -------
    Lista de tuplas ``(titulo, ruta_png | None, estado, referencia)``.
    """
    reporter = reporter or Reporter()
    assets_dir = Path(assets_dir)
    assets_dir.mkdir(parents=True, exist_ok=True)

    disponible, motivo = wsl_disponible()
    items = []

    for spec in cfg.build_comandos(dominio, resolver):
        titulo = spec["title"]
        if not disponible:
            reporter.log(f"   [!] {titulo} - {motivo}")
            items.append((titulo, None, f"OMITIDO: {motivo}",
                          spec["comando"]))
            continue

        reporter.log(f"Ejecutando: {spec['comando']}")
        try:
            codigo, salida = ejecutar(spec["comando"])
        except CLIError as exc:
            log.error("Fallo el comando: %s", exc)
            reporter.log(f"   [X] {titulo} - {exc}")
            items.append((titulo, None, f"ERROR: {exc}",
                          spec["comando"]))
            continue

        if respuestas is not None:
            respuestas.append(dominio_fp_dns.leer_dig(
                salida, spec["dns"], spec["rol"]))
        try:
            (assets_dir / f"FP_{spec['key']}_{stamp}.txt").write_text(
                f"$ {spec['comando']}\n\n{salida}\n", encoding="utf-8")
        except OSError:
            log.warning("No se pudo guardar la salida en texto.")

        out_png = assets_dir / f"FP_{spec['key']}_{stamp}.png"
        try:
            componer_imagen(titulo, spec["comando"], salida, out_png)
        except Exception as exc:  # noqa: BLE001
            log.exception("No se pudo componer la evidencia de consola")
            items.append((titulo, None, f"ERROR: {exc}",
                          spec["comando"]))
            continue

        # Un codigo distinto de cero sigue siendo evidencia valida: la
        # ausencia de resolucion es, en si misma, un dato del analisis.
        estado = "OK" if codigo == 0 else f"OK (codigo {codigo})"
        items.append((titulo, out_png, estado, spec["comando"]))
        reporter.log(f"   [OK] {titulo}")

    return items
