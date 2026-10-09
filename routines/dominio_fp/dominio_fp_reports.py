"""
routines/dominio_fp/dominio_fp_reports.py
=========================================
Generacion de los cuatro productos del analisis DOMINIO_FP.

El dominio analizado se incorpora al titulo del reporte, de modo que la
evidencia quede identificada sin ambiguedad.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from routines.common import Reporter
from routines.dominio_fp import dominio_fp_config as cfg
from utils import report_builder
from utils.report_builder import EvidenceItem, ReportError  # noqa: F401


def build_all_reports(items: List[EvidenceItem],
                      out_dir: Path,
                      stamp: str,
                      dominio: str = "",
                      ticket: str = "",
                      fecha_str: Optional[str] = None,
                      reporter: Optional[Reporter] = None,
                      analisis_dns: str = "") -> dict:
    """Genera index.html, gmail.html, reporte_gmail.docx y el ZIP."""
    titulo = cfg.REPORT_TITLE
    plataforma = cfg.PLATFORM_LABEL
    if dominio:
        limpio = cfg.normalizar_dominio(dominio)
        titulo = f"{titulo} — {limpio}"
        plataforma = f"{plataforma} ({limpio})"

    intro = cfg.build_intro(dominio, ticket) if dominio else ""
    if analisis_dns:
        intro = (intro + "\n\n" + analisis_dns).strip()

    return report_builder.build_all_reports(
        items=items, out_dir=out_dir, stamp=stamp,
        platform=plataforma, report_title=titulo,
        zip_prefix=cfg.FILE_ZIP_PREFIX, fecha_str=fecha_str,
        reporter=reporter,
        image_width_inches=cfg.DOCX_IMAGE_WIDTH_INCHES,
        author=cfg.FOOTER_AUTHOR,
        intro=intro)
