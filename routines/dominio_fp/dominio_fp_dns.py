"""
routines/dominio_fp/dominio_fp_dns.py
=====================================
Interpretacion de la salida de ``dig``.

Un REFUSED o un SERVFAIL por si solos no prueban un bloqueo. Este modulo
lee el estado (RCODE), las banderas y los Extended DNS Errors (EDE, RFC
8914) de cada respuesta y compara el resolver bajo analisis con los de
referencia para decir si el fallo se puede atribuir a una politica.

``dig`` 9.11 muestra el EDE en hexadecimal (``; OPT=15: 00 16 ...``);
las versiones recientes lo muestran ya decodificado (``; EDE: 22 (...)``).
Se leen ambos formatos.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

EDE_TEXTO = {
    0: "Other", 1: "Unsupported DNSKEY Algorithm", 2: "Unsupported DS Digest Type",
    3: "Stale Answer", 4: "Forged Answer", 5: "DNSSEC Indeterminate",
    6: "DNSSEC Bogus", 7: "Signature Expired", 8: "Signature Not Yet Valid",
    9: "DNSKEY Missing", 10: "RRSIGs Missing", 11: "No Zone Key Bit Set",
    12: "NSEC Missing", 13: "Cached Error", 14: "Not Ready", 15: "Blocked",
    16: "Censored", 17: "Filtered", 18: "Prohibited", 19: "Stale NXDOMAIN Answer",
    20: "Not Authoritative", 21: "Not Supported", 22: "No Reachable Authority",
    23: "Network Error", 24: "Invalid Data",
}
#: EDE que declaran una decision de politica del resolver.
EDE_POLITICA = {4, 15, 16, 17, 18}
#: EDE que apuntan a los servidores autoritativos del propio dominio.
EDE_AUTORIDAD = {22, 23, 24}
FALLOS = {"REFUSED", "NXDOMAIN", "SERVFAIL"}

_RE_STATUS = re.compile(r"status:\s*([A-Z]+)")
_RE_FLAGS = re.compile(r"flags:\s*([a-z ]+);")
_RE_OPT15 = re.compile(r";\s*OPT=15:\s*([0-9a-fA-F ]+?)\s*(?:\(|$)")
_RE_EDE = re.compile(r";\s*EDE:\s*(\d+)\s*(?:\(([^)]*)\))?:?\s*(.*)")
_RE_ANSWER = re.compile(r"ANSWER:\s*(\d+)")

# Atribucion
BLOQUEO_CONFIRMADO = "BLOQUEO_CONFIRMADO"
BLOQUEO_PROBABLE = "BLOQUEO_PROBABLE"
NO_ATRIBUIBLE = "NO_ATRIBUIBLE"
SIN_BLOQUEO = "SIN_BLOQUEO"
SIN_RESOLVER = "SIN_RESOLVER_ANALIZADO"


@dataclass
class EDE:
    codigo: int
    texto: str = ""

    @property
    def significado(self) -> str:
        return EDE_TEXTO.get(self.codigo, "Desconocido")

    def __str__(self) -> str:
        extra = f": {self.texto}" if self.texto else ""
        return f"EDE {self.codigo} ({self.significado}){extra}"


@dataclass
class RespuestaDig:
    dns: str
    rol: str
    estado: str = "SIN_RESPUESTA"
    banderas: List[str] = field(default_factory=list)
    respuestas: int = 0
    ede: List[EDE] = field(default_factory=list)

    @property
    def resolvio(self) -> bool:
        return self.estado == "NOERROR" and self.respuestas > 0

    @property
    def fallo(self) -> bool:
        return self.estado in FALLOS or self.estado == "SIN_RESPUESTA"

    def resumen(self) -> str:
        partes = [f"{self.dns} ({self.rol}): {self.estado}"]
        if "aa" in self.banderas and self.estado == "REFUSED":
            partes.append("con bandera AA")
        if self.resolvio:
            partes.append(f"{self.respuestas} respuesta(s)")
        if self.ede:
            partes.append("; ".join(str(e) for e in self.ede))
        return ", ".join(partes)


def _decodificar_hex(hexa: str) -> Optional[EDE]:
    try:
        datos = bytes.fromhex(hexa.replace(" ", ""))
    except ValueError:
        return None
    if len(datos) < 2:
        return None
    codigo = int.from_bytes(datos[:2], "big")
    texto = datos[2:].decode("utf-8", errors="replace").strip()
    return EDE(codigo, texto)


def leer_dig(salida: str, dns: str = "", rol: str = "") -> RespuestaDig:
    """Extrae estado, banderas, numero de respuestas y EDE de ``dig``."""
    r = RespuestaDig(dns=dns, rol=rol)
    texto = salida or ""
    m = _RE_STATUS.search(texto)
    if m:
        r.estado = m.group(1)
    m = _RE_FLAGS.search(texto)
    if m:
        r.banderas = m.group(1).split()
    m = _RE_ANSWER.search(texto)
    if m:
        r.respuestas = int(m.group(1))
    for linea in texto.splitlines():
        m = _RE_OPT15.search(linea)
        if m:
            ede = _decodificar_hex(m.group(1))
            if ede:
                r.ede.append(ede)
            continue
        m = _RE_EDE.search(linea)
        if m:
            r.ede.append(EDE(int(m.group(1)), (m.group(3) or "").strip(" ()")))
    return r


def atribuir(respuestas: List[RespuestaDig]) -> tuple:
    """
    Devuelve ``(estado, conclusion)``.

    BLOQUEO_CONFIRMADO   el resolver analizado devuelve un EDE de politica.
    BLOQUEO_PROBABLE     el analizado falla y al menos una referencia resuelve.
    NO_ATRIBUIBLE        las referencias tambien fallan: el problema esta en
                         el propio dominio (por ejemplo, delegacion rota).
    SIN_BLOQUEO          el resolver analizado devuelve respuestas.
    SIN_RESOLVER_ANALIZADO no se indico el resolver bajo analisis.
    """
    analizados = [r for r in respuestas if r.rol == "analizado"]
    referencias = [r for r in respuestas if r.rol == "referencia"]
    ref_ok = [r for r in referencias if r.resolvio]
    ref_autoridad = [r for r in referencias
                     if any(e.codigo in EDE_AUTORIDAD for e in r.ede)]

    if not analizados:
        if referencias and not ref_ok:
            detalle = (" Los resolvers de referencia reportan que no pueden "
                       "alcanzar los servidores autoritativos del dominio."
                       if ref_autoridad else "")
            return SIN_RESOLVER, (
                "No se indicó el resolver donde se observó el bloqueo, por lo "
                "que no se puede atribuir. Además, el dominio no resuelve en "
                "los resolvers públicos de referencia." + detalle)
        return SIN_RESOLVER, ("No se indicó el resolver donde se observó el "
                              "bloqueo, por lo que no se puede atribuir.")

    for r in analizados:
        if any(e.codigo in EDE_POLITICA for e in r.ede):
            return BLOQUEO_CONFIRMADO, (
                f"El resolver {r.dns} declara una decisión de política "
                f"({'; '.join(str(e) for e in r.ede)}).")

    if all(r.resolvio for r in analizados):
        return SIN_BLOQUEO, ("El resolver bajo análisis resuelve el dominio; "
                             "no se observa bloqueo en este momento.")

    if ref_ok:
        return BLOQUEO_PROBABLE, (
            "El resolver bajo análisis falla mientras al menos un resolver de "
            "referencia resuelve el dominio: el fallo es local a ese resolver.")

    detalle = (" Los resolvers de referencia reportan que no pueden alcanzar "
               "los servidores autoritativos del dominio (EDE 22/23)."
               if ref_autoridad else "")
    return NO_ATRIBUIBLE, (
        "Ningún resolver de referencia obtiene respuesta, por lo que el fallo "
        "no se puede atribuir a una política del resolver bajo análisis." + detalle)


def texto_para_reporte(respuestas: List[RespuestaDig]) -> str:
    """Parrafos que se agregan al encabezado del reporte."""
    if not respuestas:
        return ""
    estado, conclusion = atribuir(respuestas)
    lineas = ["Comparación DNS:"] + [f"- {r.resumen()}" for r in respuestas]
    return "\n".join(lineas) + f"\n\nAtribución del bloqueo: {estado}. {conclusion}"
